# 🎬 Jellyseerr Notes

Use the web UI at `https://requests.krapulax.dev`.

Recommended first settings:

-   Media server:
    -   Jellyfin URL: `http://jellyfin.media.svc.cluster.local:8096`
    -   use your Jellyfin admin account to complete setup
-   Services:
    -   Sonarr URL: `http://sonarr.media.svc.cluster.local:8989`
    -   Radarr URL: `http://radarr.media.svc.cluster.local:7878`
    -   API keys: copy from the Sonarr and Radarr UIs
-   Root folders:
    -   Sonarr: `/media/tv`
    -   Radarr: `/media/movies`

The pod mounts:

-   `/app/config` on the retained Longhorn ReadWriteOnce PVC `jellyseerr-longhorn`; see the [migration record](../../../../../docs/operations/local-path-to-longhorn.md#jellyseerr-cutover-completed-2026-11-10). The previous local-path claim was deleted; restore from Backrest if needed.

The config tree is owned by UID/GID 1000, verified on 2026-11-15. The former recursive ownership init container was removed: it could not traverse the Longhorn ext4 volume's `lost+found` directory, preventing startup. `fsGroup: 1000` remains configured. After restoring a backup, preserve UID/GID 1000 and verify the pod reaches Ready and `/api/v1/status` responds. If permissions prevent startup, inspect ownership without logging config contents; correct restored files offline before restarting. Do not reintroduce a recursive chown of the volume root.
