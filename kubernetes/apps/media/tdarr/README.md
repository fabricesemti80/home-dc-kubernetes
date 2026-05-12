# Tdarr Notes

Use the web UI at `https://tdarr.krapulax.dev`.

Initial setup:

-   Add libraries using paths under `/media`.
-   Use `/temp` as the transcode cache path.
-   The server pod has its built-in internal node disabled.
-   Three Kubernetes `tdarr_node` worker pods are pinned one per control-plane node.
-   The worker on `k8s-ctrl-01` shares the node with the server and is capped at 3.5 CPU with 3 CPU transcode workers.
-   The workers on `k8s-ctrl-02` and `k8s-ctrl-03` are capped at 4 CPU with 4 CPU transcode workers each.
-   The total in-cluster Tdarr CPU limit is 12 CPU, roughly 50% of the three 8-core Kubernetes nodes.

The pod mounts:

-   `/app/server`, `/app/configs`, and `/app/logs` on a CephFS-backed config PVC
-   `/media` from the shared `media-library-pvc`
-   `/temp` from the shared `media-library-pvc` subpath `tdarr-cache`

Rollback:

-   Disable or delete the `tdarr` Argo CD application.
-   Remove the generated `tdarr` PVC after confirming no Tdarr state needs to be kept.
