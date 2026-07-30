# Copyparty Media File Manager

## Decision

Date: 2026-07-30

Deploy Copyparty on the app cluster as a small web file manager for the existing media NFS export at `10.0.40.2:/media`.

## Assumptions

-   Public access uses `files.krapulax.dev`.
-   The NFS export allows root from app-cluster nodes to delete watched media files.
-   The app-cluster media NFS PV/PVC is already proven by Jellyfin and the media automation apps.
-   Copyparty config can use the app-cluster default CephFS storage.
-   The app-cluster Cloudflare tunnel terminates public HTTPS for `files.krapulax.dev`.
-   Doppler `apps` config contains `COPYPARTY_MEDIA_PASSWORD`.

## Security Impact

-   Copyparty is delete-capable by design and mounts the media library read/write.
-   The pod runs as UID `0` because the existing media stack uses root for NFS permissions.
-   Authentication is handled by Copyparty with a Doppler-managed password; Cloudflare can add Access later without changing the workload.
-   Command execution is not enabled.

## Rollback

-   Delete or disable `kubernetes/argo/apps/app-cluster/media/copyparty.yaml`.
-   Remove the `files.krapulax.dev` HTTPRoute annotations if the DNS record should be withdrawn.
-   The static NFS PV uses `Retain`, so the media export is not deleted.
