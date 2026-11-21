# FileBrowser Quantum

FileBrowser Quantum provides authenticated browser access to the QNAP media share from [files.krapulax.home](http://files.krapulax.home) and the Media group on Homepage. The app runs in the app cluster's `media` namespace behind the internal Envoy HTTP listener.

The app mounts the existing `media-library-pvc` (`10.0.40.2:/media`) at `/media` with write access. It runs as UID and GID 1000, matching Chaptarr. Uploading and editing require the NAS to grant appropriate write access. Renaming and deleting require write and search access on the containing directory. Check the QNAP export mapping and directory ACLs if access differs between folders.

The app generates a one-time password for `admin` during the first startup. Retrieve it from the initial pod's logs (`kubectl -n media logs deploy/filebrowser | grep -i 'initial admin password'`) and set a new password when prompted. The retained Longhorn claim stores the user database and app state. Backrest protects that state. Media files remain on the NAS, and deleting them in FileBrowser affects the shared library directly.

## Validation

- Confirm Argo sync, a ready deployment, and an accepted internal HTTPRoute. Check that `files.krapulax.home` resolves to the internal gateway and opens from Homepage.
- Sign in and in each media directory you intend to manage, upload a disposable file, overwrite it, rename it, and delete it. Confirm the changes on the NAS. A newly created test directory alone does not validate permissions on existing library folders.
- Check the `app-filebrowser` Backrest plan after the first scheduled export.

## Rollback

Revert the deployment PR and sync the app-of-apps. Remove any remaining FileBrowser workload, Service, and HTTPRoute if Argo leaves them orphaned. Keep the Longhorn claim for redeployment or restore. The existing NFS claim is owned independently of this app.
