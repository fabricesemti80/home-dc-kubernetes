# Prowlarr Notes

Use the web UI at `https://prowlarr.krapulax.dev`.

Recommended first settings:

-   Applications:
    -   add `Sonarr`
    -   Prowlarr server: `http://sonarr.media.svc.cluster.local:8989`
    -   Sonarr URL base: empty
    -   Sonarr API key: copy from the Sonarr UI at `Settings -> General`
    -   Sync level: `Full Sync`
    -   Tags: empty unless you want indexer scoping
    -   Test the connection before saving
-   Download clients:
    -   if needed later, add SABnzbd at `http://sabnzbd.media.svc.cluster.local:8080`
-   Indexers:
    -   add your Usenet indexers here and sync them to Sonarr

The pod mounts:

-   `/config` on CephFS
