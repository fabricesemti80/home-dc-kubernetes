# FileBrowser Quantum

FileBrowser Quantum provides authenticated browser access to the QNAP media share from [files.krapulax.home](http://files.krapulax.home) and the Media group on Homepage. The app runs in the app cluster's `media` namespace behind the internal Envoy HTTP listener.

The app mounts the existing `media-library-pvc` (`10.0.40.2:/media`) at `/media` with write access. It runs as UID and GID 1000, matching Chaptarr. Uploading and editing require the NAS to grant appropriate write access. Renaming and deleting require write and search access on the containing directory. Check the QNAP export mapping and directory ACLs if access differs between folders.

The app requests 256 MiB of memory and has a 1 GiB limit. The previous 512 MiB limit was reached by the 2.0.1 pod; the precise allocation responsible was not retained. The higher limit provides headroom rather than proving the cause is fixed. Startup indexes the media source, so monitor memory and OOM restarts after upgrades and large library changes.

NAS permissions are independent of Git and must be maintained on QNAP. On 2026-11-21, the directory for `Avatar - Fire and Ash (2025)` was owned by UID 99, GID 100, mode 0755; FileBrowser could not delete its contents. The NAS rejected a targeted POSIX ACL as unsupported. Its directory group was changed to GID 1000 and group write enabled (mode 0775), leaving UID 99 as owner and other-user read/search unchanged. A disposable file was created, renamed, and deleted as UID 1000; the movie was not deleted.

Other existing or newly imported folders may have different owners and modes. Before changing one, inspect its numeric owner, group and mode, consider the access needed by its writers, and test using a disposable file. Do not recursively change the share or make it world-writable. A directory group change grants write access to all members of that group; GID 1000 is the FileBrowser group. File deletion depends on its parent directory, not just the file's mode.

Sign in as `admin` with `FILEBROWSER_ADMIN_PASSWORD` from Doppler (`home-dc-kubernetes/apps`). The Doppler operator syncs the key to `media/filebrowser-admin`. FileBrowser reapplies the configured password on startup. To rotate it, update the key in Doppler, wait for the Kubernetes Secret to sync, then restart the deployment.

The retained Longhorn claim stores the user database and app state. Backrest protects that state. Media files remain on the NAS, and deleting them in FileBrowser affects the shared library directly.

## Validation

-   Confirm Argo sync, a ready deployment, and an accepted internal HTTPRoute. Check that `files.krapulax.home` resolves to the internal gateway and opens from Homepage.
-   Sign in and in each media directory you intend to manage, upload a disposable file, overwrite it, rename it, and delete it. Confirm the changes on the NAS. A newly created test directory alone does not validate permissions on existing library folders.
-   After a restart and a representative library scan, inspect `kubectl -n media describe pod -l app.kubernetes.io/name=filebrowser` and memory metrics; verify there are no new OOM kills and that peak usage stays below the limit.
-   Check the `app-filebrowser` Backrest plan after the first scheduled export.

## Rollback

Revert the deployment PR and sync the app-of-apps. Remove any remaining FileBrowser workload, Service, and HTTPRoute if Argo leaves them orphaned. Keep the Longhorn claim for redeployment or restore. The existing NFS claim is owned independently of this app.

To undo the 2026-11-21 permission change, a NAS administrator can restore GID 100 and mode 0755 on that movie directory; doing so prevents UID 1000 from deleting files inside it again. Reverting the resource limit restores the previous 512 MiB cap and its OOM risk.
