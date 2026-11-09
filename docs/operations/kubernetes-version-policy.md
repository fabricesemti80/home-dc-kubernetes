# Kubernetes version policy

Talos 1.13.8 supports Kubernetes 1.31.0 through 1.36.99. Keep the app cluster and its generation template on Kubernetes 1.36.x; the reviewed patch target is 1.36.6. Renovate caps `ghcr.io/siderolabs/kubelet` below 1.37.0 to prevent incompatible independent minor upgrades.

Source: [Talos 1.13.8 compatibility constants](https://github.com/siderolabs/talos/blob/v1.13.8/pkg/machinery/compatibility/talos113/talos113.go).

Status: deployed on the app-cluster on 2026-11-09. All four nodes run Kubernetes 1.36.6 and Talos 1.13.12 (previously 1.36.3 and 1.13.8).

Assumption: Talos remains on the 1.13 minor. Review the Renovate cap against upstream compatibility whenever upgrading the Talos minor, and update both `talos/app/talenv.yaml` and `templates/config/talos/talenv.yaml.j2` together.

Validation: run the CI lint and manifest workflows, including `talhelper validate talconfig talconfig.yaml` from `talos/app`. Passing configuration validation does not perform or verify a live cluster upgrade. Before deploying, verify running node versions and follow the Talos Kubernetes upgrade procedure.

Rollback: the version bump is deployed (see Status), so a Git revert is not a Kubernetes downgrade; use the supported recovery procedure and backups (an etcd snapshot for the control plane, `talosctl rollback` for a Talos OS upgrade). Before it was deployed the instruction was to restore both version files to the 1.36.3 baseline and keep the compatibility cap.

## Upgrading the app-cluster nodes

The procedure used on 2026-11-09 (Talos 1.13.8 to 1.13.12 and Kubernetes 1.36.3 to 1.36.6). It is one node at a time, with a health gate in between.

1.  **Gate.** Every node `Ready` and uncordoned, no unhealthy pods, every Longhorn volume `healthy` (or `detached`), every Argo Application `Synced` and `Healthy`.
2.  **etcd snapshot.** `task talos:app:etcd-snapshot`, or `talosctl -n <control-plane-ip> etcd snapshot <file>`. There is a single etcd member, so the snapshot is the only way back for the control plane. It contains every Kubernetes Secret: keep it in a git-ignored private directory with mode `600`, and delete it once the upgrade is accepted.
3.  **Talos OS, per node:** `task talos:app:upgrade-node IP=<ip>`. `talosctl upgrade` cordons, drains, reboots and uncordons the node. Observed: the control plane took about 100 s (the API is unavailable meanwhile; workloads keep running), each worker 2.5 to 4.5 min, and the cluster needed a further 2.5 min or so to settle after each worker. Pods pinned to that node by a `local-path` volume (the media apps, Immich) are unavailable until it is back; freqtrade, which is on Longhorn, moved to another node by itself. On 2026-11-09 the order was control plane, `k8s-wrkr-03`, `k8s-wrkr-02`, then the GPU worker last.
4.  **Do not use `task talos:app:longhorn-node` for an OS upgrade.** It only upgrades a node whose schematic differs from `talconfig.yaml` and otherwise skips the upgrade; it exists for the Longhorn schematic change.
5.  **GPU worker check.** After its upgrade confirm the NVIDIA modules (`talosctl -n 10.0.40.95 read /proc/modules`), `nvidia-smi` inside the Jellyfin pod, and a real NVENC transcode (for example `ffmpeg -f lavfi -i testsrc2=duration=5:size=1920x1080:rate=30 -c:v h264_nvenc -f null -` with the Jellyfin ffmpeg).
6.  **Kubernetes:** from `talos/app` run `talosctl upgrade-k8s --to v1.36.x --nodes <control-plane-ip> --dry-run`, then the same command without `--dry-run` (`task talos:upgrade-k8s` wraps it). It restarts the API server, controller manager, scheduler and kubelet on the control plane (about 5 min) and leaves worker kubelets alone when they already run the target version. Some API-dependent pods (Envoy Gateway, metrics-server, kube-state-metrics, the VictoriaMetrics operator and others) crash-looped for about 2 min while the API restarted and recovered on their own. Keep `kubernetesVersion` in `talenv.yaml` equal to the target.
