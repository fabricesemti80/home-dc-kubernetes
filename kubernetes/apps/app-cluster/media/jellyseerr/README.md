# Jellyseerr Notes

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

-   `/app/config` on CephFS
