# Tdarr Notes

Use the web UI at `https://tdarr.krapulax.dev`.

Initial setup:

-   Add libraries using paths under `/media`.
-   Use `/temp` as the transcode cache path.
-   The built-in internal node is enabled as `tdarr-internal`.
-   Start with the single configured CPU transcode worker and increase only after watching node CPU, memory, and transcode cache pressure.

The pod mounts:

-   `/app/server`, `/app/configs`, and `/app/logs` on a CephFS-backed config PVC
-   `/media` from the shared `media-library-pvc`
-   `/temp` as pod-local `emptyDir` transcode cache

Rollback:

-   Disable or delete the `tdarr` Argo CD application.
-   Remove the generated `tdarr` PVC after confirming no Tdarr state needs to be kept.
