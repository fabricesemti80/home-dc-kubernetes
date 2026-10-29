# 🎬 Prowlarr Notes

Use the web UI at `https://prowlarr.krapulax.dev`.

Recommended first settings:

-   Applications:
    -   add `Sonarr`
    -   Prowlarr Server: `http://prowlarr.media.svc.cluster.local:9696`
    -   Sonarr Server: `http://sonarr.media.svc.cluster.local:8989`
    -   Sonarr API key: copy from the Sonarr UI at `Settings -> General`
    -   Sync level: `Full Sync`
    -   Tags: empty unless you want indexer scoping
    -   Test the connection before saving
    -   add `Radarr` separately with Radarr Server `http://radarr.media.svc.cluster.local:7878` and its own API key
-   Download clients:
    -   if needed later, add SABnzbd at `http://sabnzbd.media.svc.cluster.local:8080`
-   Indexers:
    -   add your Usenet/torrent indexers here and sync them to Sonarr and Radarr

For download categories, library paths and the full connection order, see [the media app setup runbook](../../../../../docs/plan/media-app-setup.md).

The pod mounts:

-   `/config` on a local-path ReadWriteOnce PVC
