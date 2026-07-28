# qBittorrent Notes

Use the web UI at `https://qbittorrent.krapulax.dev`.

Recommended first settings:

-   Downloads:
    -   Default save path: `/downloads`
    -   Keep incomplete torrents in: enabled
    -   Incomplete torrents path: `/incomplete-downloads`
-   Categories:
    -   `tv`
    -   `movies`
-   WebUI:
    -   keep the application credentials enabled
-   Arr integration:
    -   Sonarr or Radarr host: `qbittorrent.media.svc.cluster.local`
    -   port: `8080`
    -   URL base: empty

The pod mounts:

-   `/config` on CephFS
-   `/downloads` on the shared NFS completed-downloads path
-   `/incomplete-downloads` on the shared NFS incomplete-downloads path

Note:

-   the cluster now exposes a dedicated peer `LoadBalancer` service at `10.0.40.104` for `6881/TCP` and `6881/UDP`
-   add a router port forward from your WAN on `6881/TCP` and `6881/UDP` to `10.0.40.104:6881`
-   once that forward is in place, qBittorrent should be connectable and seed much more effectively
