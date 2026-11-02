# 📥 SABnzbd Notes

Use the web UI at `https://sabnzbd.krapulax.dev`.

Recommended first settings:

-   Folders:
    -   completed download folder: `/downloads`
    -   temporary download folder: `/incomplete-downloads`
    -   if SABnzbd shows paths under `/config/Downloads/...`, update them to the two paths above and restart the job or retry it
-   Post-processing:
    -   in the current SABnzbd UI, unpacking is typically controlled under `Settings -> Switches -> Post processing`
    -   `Enable recursive unpacking` should be enabled
    -   `Post-Process Only Verified Jobs` should usually stay enabled
    -   Sonarr can only import real video files such as `.mkv` or `.mp4`
    -   if a completed job only contains `.rar`, `.r00`, `.par2`, or `.nfo` files, Sonarr will report `No files found are eligible for import`
    -   if unpacking is enabled but Sonarr still cannot import, inspect the SABnzbd history entry:
        -   incomplete or aborted downloads will not unpack into importable media
        -   failed repair or post-processing will also leave only archive files behind
-   API:
    -   enable the API
    -   keep the API key handy for Sonarr and later Prowlarr
-   Security:
    -   add a SABnzbd username/password in the UI

Usenet server details can be added in the UI for now.

The pod mounts:

-   `/config` on a local-path ReadWriteOnce PVC
-   `/media` on the shared NFS library
-   `/downloads` on `downloads/complete`
-   `/incomplete-downloads` on `downloads/incomplete`

## Memory sizing

SABnzbd's article cache (`cache_limit`) is anonymous memory on top of a ~250 MiB baseline, per-connection buffers and unpacking. In November 2026 a `cache_limit` of 1G inside a 1Gi container limit caused a ~4 day OOMKilled crash loop (the pod passed readiness for ~30 s between kills, so a plain "deployment unavailable" alert kept resetting).

-   Container limit: `2Gi`, request `512Mi` (`values.yaml`).
-   The init container caps `cache_limit` at `CACHE_LIMIT_MAX_MB` (512). It only rewrites the value when it is **missing or higher than the cap**, so a lower value chosen in the UI is kept. Keep the cap at or below about a quarter of the memory limit.
-   To use a bigger cache, raise the container memory limit **and** `CACHE_LIMIT_MAX_MB` together; changing only the UI value is reverted to the cap on the next restart.
-   Fewer Usenet connections also lower buffer memory; 50 connections are configured for Eweka in the UI (the provider allows it), so tune this in the UI if memory is tight.
-   `KubernetesContainerOOMKilled` and `KubernetesPodCrashLooping` alert on this class of problem. Memory headroom before a kill cannot be alerted on yet because cAdvisor metrics are not collected (see `docs/architecture/victoriametrics.md`).
