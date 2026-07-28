# SABnzbd Notes

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

-   `/config` on CephFS
-   `/media` on the shared NFS library
-   `/downloads` on `downloads/complete`
-   `/incomplete-downloads` on `downloads/incomplete`
