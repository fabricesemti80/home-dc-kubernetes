# Tdarr Notes

Use the web UI at `https://tdarr.krapulax.dev`.

Initial setup:

-   Add libraries using paths under `/media`.
-   Use `/temp` as the transcode cache path.
-   The server pod has its built-in internal node disabled.
-   Kubernetes `tdarr_node` worker pods are pinned per node. The `k8s-ctrl-02` worker is temporarily set to `replicas: 0` after the June 21, 2026 reboot because it was contributing heavy IO pressure during control-plane recovery.
-   The worker on `k8s-ctrl-01` shares the node with the server and is capped at 3.5 CPU with 3 CPU transcode workers.
-   The worker on `k8s-ctrl-02` is capped at 4 CPU with 4 CPU transcode workers when enabled.
-   With `k8s-ctrl-02` disabled, the active in-cluster Tdarr CPU limit is 4 CPU.

The pod mounts:

-   `/app/server`, `/app/configs`, and `/app/logs` on a CephFS-backed config PVC
-   `/media` from the shared `media-library-pvc`
-   `/temp` from the shared `media-library-pvc` subpath `tdarr-cache`

Rollback:

-   Re-enable the `k8s-ctrl-02` worker by setting `controllers.worker-k8s-ctrl-02.replicas` back to `1` after node IO pressure clears.
-   Disable or delete the `tdarr` Argo CD application.
-   Remove the generated `tdarr` PVC after confirming no Tdarr state needs to be kept.
