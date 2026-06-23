# Media Management Stack

## Objective

Add media-management services that feed Jellyfin while preserving the existing storage split:

-   CephFS for application-owned config and state
-   NFS for shared media library and download paths
-   small, reversible rollout starting with `sabnzbd` and `sonarr`

## Scope

Initial rollout includes:

-   `sabnzbd`
-   `qbittorrent`
-   `sonarr`
-   `prowlarr`
-   `recyclarr`
-   `radarr`
-   `jellyseerr`
-   `tdarr`

Deferred until the first two apps are stable:

-   API-key automation between services

## Namespace Decision

-   Reuse the existing `media` namespace

Rationale:

-   these services ultimately exist to source content for Jellyfin
-   the namespace already contains the shared media-library claim and routing patterns
-   it avoids cross-namespace duplication for the first rollout

## Storage Model

-   Each app gets its own CephFS-backed PVC for `/config`
-   Shared media content remains on the NFS export at `10.0.40.2:/media`
-   The existing `media-library-pvc` remains the shared claim for the full library mount
-   Download paths are mounted from the same NFS claim using subpaths under `/media/downloads`

Planned pod paths:

-   `sonarr`
    -   `/config` on CephFS
    -   `/media` on NFS
    -   `/downloads` on NFS subpath `downloads/complete`
    -   `PATH` includes `/app/sonarr/bin` so the bundled `ffprobe` is available during completed-download sample detection
-   `sabnzbd`
    -   `/config` on CephFS
    -   `/media` on NFS
    -   `/downloads` on NFS subpath `downloads/complete`
    -   `/incomplete-downloads` on NFS subpath `downloads/incomplete`
-   `qbittorrent`
    -   `/config` on CephFS
    -   `/downloads` on NFS subpath `downloads/complete`
    -   `/incomplete-downloads` on NFS subpath `downloads/incomplete`
    -   peer traffic exposed through a dedicated `LoadBalancer` service on `6881/TCP` and `6881/UDP`
-   `prowlarr`
    -   `/config` on CephFS
-   `recyclarr`
    -   `/config` on CephFS
    -   reads API keys from Kubernetes secrets synced from Doppler
-   `radarr`
    -   `/config` on CephFS
    -   `/media` on NFS
    -   `/downloads` on NFS subpath `downloads/complete`
-   `jellyseerr`
    -   `/app/config` on CephFS
-   `tdarr`
    -   `/app/server`, `/app/configs`, and `/app/logs` on CephFS
    -   `/media` on NFS
    -   `/temp` on NFS subpath `tdarr-cache` for shared transient transcode cache
    -   server/UI runs as a single pod with its internal node disabled
    -   three `tdarr_node` worker pods are pinned one per Kubernetes node, with a total CPU limit of 12 cores across the 24-core cluster

## API-Key Automation Direction

The long-term goal is to automate cross-service integration, especially for Prowlarr, Sonarr, and Radarr.

For the initial rollout, do not assume app API keys can be cleanly injected through environment variables. Many of these applications generate and own their API keys internally.

Recyclarr is the first exception to that rule because it is an API client rather than an API server. It is a good fit for Doppler-backed secrets because it only needs to consume Sonarr and later Radarr API keys.

Recommended future pattern:

-   deploy apps first
-   add a bootstrap or reconciliation job that:
    -   waits for app readiness
    -   discovers or rotates API keys through supported APIs
    -   configures downstream integrations

This avoids coupling runtime app internals to guessed static secrets in Doppler.

## Security Notes

-   Public ingress is acceptable temporarily for test access, but each app still needs its own application authentication enabled in the UI
-   SABnzbd server credentials should not be committed; if later automated, source them from Doppler
-   qBittorrent WebUI credentials should remain application-managed; if later automated, source them from Doppler
-   qBittorrent peer efficiency depends on a manual router forward to the peer `LoadBalancer` IP and is not handled by Cloudflare
-   Recyclarr API credentials should be sourced from Doppler rather than committed into Git
-   Tdarr is deployed with UI auth disabled initially; enable application authentication in the UI before exposing it beyond trusted admin access
-   Tdarr transcode cache is intentionally disposable and isolated under `/media/tdarr-cache`; do not store source media or retained outputs under `/temp`
-   Tdarr workers are Kubernetes-only; external Docker workers are not part of this rollout
-   The NFS-backed media library remains shared state and should be treated as retained data

## Assumptions

-   `/media/downloads`
-   `/media/downloads/complete`
-   `/media/downloads/incomplete`

already exist or can be created on the NFS server before workloads start.

## Validation

-   Argo sync succeeds for the deployed apps
-   PVCs bind on CephFS
-   pods mount both CephFS config and NFS library paths
-   `sabnzbd` serves its UI and can write test files under `/downloads`
-   `qbittorrent` serves its UI and can write test files under `/downloads` and `/incomplete-downloads`
-   `sonarr` serves its UI and can see both `/media` and `/downloads`
-   `sonarr` can resolve `ffprobe` from the container `PATH`
-   `prowlarr` serves its UI and can reach Sonarr over the in-cluster service
-   `recyclarr` can run against Sonarr without authentication failures
-   `radarr` serves its UI and can see both `/media` and `/downloads`
-   `jellyseerr` serves its UI and can reach Jellyfin, Sonarr, and Radarr over the configured URLs
-   `tdarr` serves its UI, creates its internal node, can see `/media`, and can write temporary transcode data under `/temp`

## Rollback

-   Delete the `sabnzbd`, `qbittorrent`, `sonarr`, `prowlarr`, `recyclarr`, `radarr`, `jellyseerr`, and `tdarr` Argo applications
-   Remove their HTTPRoutes
-   Delete their CephFS PVCs if app config should be discarded
-   Retain NFS media content and download directories
