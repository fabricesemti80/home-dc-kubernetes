# FileBrowser Quantum

FileBrowser Quantum provides authenticated browser access to the QNAP media share from [files.krapulax.home](http://files.krapulax.home) and the Media group on Homepage. The app runs in the app cluster's `media` namespace behind the internal Envoy HTTP listener.

The app mounts the existing `media-library-pvc` (`10.0.40.2:/media`) at `/media` with write access. It runs as UID and GID 0 with `DAC_OVERRIDE` so it can manage files and directories owned by different NAS users without rewriting their permissions. The NFS export must permit root access; a root-squashed export, read-only filesystem, immutable file or NAS-managed snapshot may still prevent changes.

The app requests 256 MiB of memory and has a 1 GiB limit. The previous 512 MiB limit was reached by the 2.0.1 pod; the precise allocation responsible was not retained. The higher limit provides headroom rather than proving the cause is fixed. Startup indexes the media source, so monitor memory and OOM restarts after upgrades and large library changes.

### Media access and security

This is a deliberate increase in privilege: anyone with FileBrowser write access, or anyone who compromises it, can modify or delete data across the media share, including Immich data and downloads. Deleting files may leave other applications' databases inconsistent. The process also has root access to its mounted application state and container filesystem. Keep the service internal and protect its admin password; the internal HTTP route is not encrypted.

The container drops all capabilities except `DAC_OVERRIDE`, disables privilege escalation and service-account token mounting, and uses the runtime-default seccomp profile. It is not a privileged container. These controls reduce but do not eliminate the additional risk of running as root.

QNAP QTS 5.2.9 currently mounts the filesystem with `noacl`, and a POSIX ACL attempt failed. QTS warns that enabling Advanced Folder Permissions sets subfolder permissions to match their root folders. Do not enable that setting or recursively change share ownership as part of this deployment. QNAP's documentation does not establish whether the setting remounts this volume or requires a reboot. Representative pre-change modes and numeric owners: share root 0755 1000:100; movies and tv 0775 1000:100; downloads 0775 0:0; immich 0755 1000:1000; books and audiobooks 0777 1000:100; `_library` 0755 99:100. These samples are not a complete permissions backup.

On 2026-11-21, before this change, the `Avatar - Fire and Ash (2025)` directory was granted GID 1000 group write so FileBrowser could delete its contents. The movie was subsequently deleted by the user. The root-based deployment does not change the permissions of other NAS files.

Sign in as `admin` with `FILEBROWSER_ADMIN_PASSWORD` from Doppler (`home-dc-kubernetes/apps`). The Doppler operator syncs the key to `media/filebrowser-admin`. FileBrowser reapplies the configured password on startup. To rotate it, update the key in Doppler, wait for the Kubernetes Secret to sync, then restart the deployment.

The retained Longhorn claim stores the user database and app state. Backrest protects that state. Media files remain on the NAS, and deleting them in FileBrowser affects the shared library directly.

## Validation

-   Confirm Argo sync, a ready deployment, and an accepted internal HTTPRoute. Check that `files.krapulax.home` resolves to the internal gateway and opens from Homepage.
-   Sign in and in each media directory you intend to manage, upload a disposable file, overwrite it, rename it, and delete it. Confirm the changes on the NAS. A newly created test directory alone does not validate permissions on existing library folders.
-   Verify the running pod is UID 0 and has only the intended added capability. In an existing directory owned by another UID, create, rename and delete a disposable file through FileBrowser; also test a newly created directory. Do not modify media files or QNAP-managed snapshots for validation.
-   After a restart and a representative library scan, inspect `kubectl -n media describe pod -l app.kubernetes.io/name=filebrowser` and memory metrics; verify there are no new OOM kills and that peak usage stays below the limit.
-   Check the `app-filebrowser` Backrest plan after the first scheduled export.

## Rollback

Revert the deployment PR and sync the app-of-apps. Remove any remaining FileBrowser workload, Service, and HTTPRoute if Argo leaves them orphaned. Keep the Longhorn claim for redeployment or restore. The existing NFS claim is owned independently of this app.

To roll back share-wide access, revert the UID/GID and capability changes and sync FileBrowser. It will again be unable to delete files in directories that do not grant UID/GID 1000 write access. Files created while running as root, including application state, may require their ownership or permissions to be corrected before the non-root pod can use them; inspect and correct only the affected files. NAS ACL settings and existing ownership are not changed by this deployment.

Reverting the resource limit restores the previous 512 MiB cap and its OOM risk.
