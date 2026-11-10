# Longhorn operations (app-cluster)

Design, assumptions and limits: [docs/architecture/longhorn.md](../architecture/longhorn.md).

> **Status:** rolled out on 2026-11-09 (steps 1-5 done; step 6, automated sync, still open). Every step that changes the live host, VMs or cluster is an explicit operator action.

## What you get, and what you do not

-   Replicated block storage (3 replicas) on the three passed-through 500 GB SSDs, StorageClass `longhorn` (default, `Retain`).
-   **Single failure domain:** all SSDs and all three workers live on `pve-00`. Losing the host, its power or its SATA controller loses every replica at once.
-   **Longhorn volumes are not a backup.** Backrest remains the backup; enroll any app that moves to Longhorn in `app-protect`/Backrest as described in [backrest.md](backrest.md#protecting-and-opting-out-apps). Replication also copies deletions and corruption.
-   **Existing local-path claims do not move by changing a StorageClass.** All app-cluster app claims were migrated one app at a time on 2026-11-10 with a quiesced offline copy ([runbook](local-path-to-longhorn.md)); the old local-path claims are retained for rollback. Backrest's own state is on Longhorn, so its management depends on it (the repository and key do not).

## Rollout order

Do not skip or reorder. Each step has a verification below. Merging a PR changes nothing live except where stated.

1.  **Proxmox PR (`home-dc-proxmox`)** — prepare the SSDs on `pve-00` (optional, guarded signature wipe: explicit by-id list, explicit opt-in variable, refuses mounted/swap/ZFS/VM-referenced disks). Run its `--check` first, then the apply as that PR documents. The SSDs must be blank before Talos sees them.
2.  **Terraform PR (`home-dc-terraform`)** — attach each SSD as `scsi2`: 4095 `k8s-wrkr-01-gpu` ← `…2344E8836BF7`, 4096 `k8s-wrkr-02` ← `…2344E8836D00`, 4097 `k8s-wrkr-03` ← `…2349E8875927`. Follow that PR for the root-credential constraint and the VM stop/start required to attach a disk (one worker at a time; the local-path volumes on that worker are unavailable during its restart).
3.  **Merge this PR.** Safe: the Longhorn Argo Application has no automated sync, so Argo only registers it (`OutOfSync`). If your Argo settings auto-sync new Applications, stop and check before merging.
4.  **Talos, one worker at a time.** First, locally: update your git-ignored `nodes.yaml` schematic IDs to match the Git change (workers `613e1592…1245`, GPU worker `fb73a192…01c2`, control plane unchanged) so `task template:configure` does not revert them, and regenerate: `task talos:app:generate-config`. Then run the guarded tasks (they do not touch the control plane):
    ```sh
    task talos:app:longhorn-rollout          # etcd snapshot, then k8s-wrkr-03, k8s-wrkr-02, k8s-wrkr-01-gpu (GPU last); stops at the first failure
    # or step by step:
    task talos:app:etcd-snapshot             # saved under .private/app-cluster/, outside Git
    task talos:app:longhorn-node IP=10.0.40.97   # then 10.0.40.96, then 10.0.40.95
    ```
    Per worker, `longhorn-node` runs: **preflight** (worker, exactly one blank ~500 GB disk, schematic change pending, node `Ready`), `kubectl cordon`, **upgrade** to the new schematic image pinned to the node's running Talos version so the extension change is not mixed with a version bump (skipped if the node already runs the target schematic), **apply** the machine config (adds the `longhorn` volume and kubelet bind mount), wait for `Ready`, **verify** (extensions, both volumes, shared mount, kubelet), `kubectl uncordon`. A failure leaves the node cordoned; fix the cause and re-run the same task (it is idempotent). The read-only parts are available alone: `task talos:app:longhorn-preflight IP=<ip>` and `task talos:app:longhorn-verify IP=<ip>`. The SSD must be attached and blank first (steps 1-2); applying the bind mount while `/var/mnt/longhorn` does not exist is the failure mode the preflight prevents. After the GPU worker, verify a Jellyfin transcode.
5.  **Argo sync (manual).** Preview, then sync only the Longhorn Application:
    ```sh
    argocd app diff longhorn      # or the Argo CD UI: Diff
    argocd app sync longhorn      # or the UI: Sync
    ```
    This creates `longhorn-system`, the Helm release, the HTTPRoute and the `longhorn` StorageClass, and **makes it the default class** from that moment (see [default class](#default-storageclass-impact)). The HTTPRoute (`longhorn.krapulax.home` on `envoy-internal`) is picked up by the Technitium ExternalDNS instance, which publishes the DNS record automatically within about a minute: no manual record and no Cloudflare record. Check with `dig +short longhorn.krapulax.home` (it must equal `kubernetes.krapulax.home`, `10.0.40.102`).
6.  **Follow-up PR** (after the checks pass and soak): add the `automated` sync block to `kubernetes/argo/apps/app-cluster/storage/longhorn.yaml`, matching the other storage apps.

## Verification

Read-only, in this order.

```sh
# Talos (per worker)
talosctl -n <ip> get extensions                     # iscsi-tools, util-linux-tools (and the NVIDIA pair on 01-gpu)
talosctl -n <ip> get disks                          # ~465 GiB SSD, plus 100 GiB data and 55 GiB system disks
talosctl -n <ip> get volumestatus u-longhorn u-local-path-provisioner
talosctl -n <ip> get mountstatus | grep -E 'longhorn|local-path'
#   u-longhorn must be on the ~465 GiB disk (xfs, /var/mnt/longhorn);
#   u-local-path-provisioner must still be on the SAME 100 GiB disk as before. Do not compare /dev/sdX names: the kernel
#   may swap them across the reboot (observed 2026-11-09: the 100 GiB disk went from sdb to sdc). Compare size and the
#   xfs partition label instead: `talosctl -n <ip> get discoveredvolumes | grep u-local-path-provisioner` (xfs, ~97 GB).
talosctl -n <ip> service kubelet                    # Running, no errors about extraMounts
talosctl -n <ip> read /proc/mounts | grep longhorn  # shared mount present
kubectl get nodes -o wide                           # all Ready

# Existing local-path workloads unaffected
kubectl get pvc -A                                  # unchanged, all Bound
kubectl get pods -A | grep -v -E 'Running|Completed'

# Longhorn
kubectl -n argo-system get application longhorn
kubectl -n longhorn-system get pods -o wide         # manager, instance-manager, csi on all three workers only
kubectl -n longhorn-system get nodes.longhorn.io    # 3 nodes Ready/Schedulable
kubectl -n longhorn-system get nodes.longhorn.io -o jsonpath='{range .items[*]}{.metadata.name} {.spec.disks}{"\n"}{end}'   # path /var/mnt/longhorn
kubectl -n longhorn-system get settings.longhorn.io default-data-path default-replica-count
kubectl get sc                                      # longhorn (default), local-path (not default)
kubectl get sc -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}{"\n"}{end}'
dig +short longhorn.krapulax.home                  # internal DNS record, same answer as kubernetes.krapulax.home (10.0.40.102)
curl -sI http://longhorn.krapulax.home              # internal route (LAN only)
```

Disposable smoke test (creates and deletes one throwaway PVC and pod; use the `default` namespace; with `Retain`, also delete the leftover PV and its Longhorn volume afterwards):

```sh
kubectl -n default apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: longhorn-smoke}
spec: {accessModes: [ReadWriteOnce], storageClassName: longhorn, resources: {requests: {storage: 1Gi}}}
---
apiVersion: v1
kind: Pod
metadata: {name: longhorn-smoke}
spec:
  containers: [{name: t, image: busybox, command: [sh, -c, "echo ok > /d/f && sync && sleep 3600"], volumeMounts: [{name: d, mountPath: /d}]}]
  volumes: [{name: d, persistentVolumeClaim: {claimName: longhorn-smoke}}]
EOF
kubectl -n longhorn-system get volumes.longhorn.io          # 1 Gi, 3 replicas on 3 different nodes, healthy
kubectl -n default delete pod/longhorn-smoke pvc/longhorn-smoke
```

## Default StorageClass impact

`local-path` is **already** not a default class (`defaultClass: false`; verified live 2026-11-08), so only the addition of `longhorn` as default changes behaviour.

-   Unaffected: all existing PVCs; every app with an explicit `storageClass`/`storageClassName` (all app-cluster apps in Git use `local-path`, or `""` for the static NFS claims `media-library-pvc` and `k8s-backup`).
-   Changed: any PVC or StatefulSet `volumeClaimTemplate` created **without** a class from now on (future apps, chart upgrades that add persistence, an operator creating claims) is provisioned by Longhorn — 3 replicas, `Retain`, up to ~one SSD of capacity — instead of staying `Pending`. A claim already `Pending` without a class is assigned `longhorn` retroactively. Before syncing, list candidates: `kubectl get pvc -A -o custom-columns=NS:.metadata.namespace,N:.metadata.name,SC:.spec.storageClassName,ST:.status.phase | grep -v local-path`.
-   To undo only this effect: set `persistence.defaultClass: false` in `kubernetes/apps/app-cluster/storage/longhorn/values.yaml` (the StorageClass is recreated by the chart; StorageClass fields are immutable, so Argo may need to delete and recreate it — safe while no PVC is being provisioned).

## Day-2 notes

-   **Node maintenance:** drain one worker at a time and wait for all Longhorn volumes to be `healthy` again before the next; with 3 replicas on 3 nodes a drained node's replicas go stale and rebuild after it returns. Longhorn blocks drains that would take the last healthy replica (`node-drain-policy`, default `block-if-contains-last-replica`).
-   **Talos upgrades:** the data volume is on its own disk and survives `talosctl upgrade`. Never `talosctl reset` a worker without evicting its Longhorn replicas first (UI → Node → disable scheduling → evict) and confirming the volumes are healthy on the other two.
-   **Capacity:** keep volumes well below one SSD in total; Longhorn stops scheduling replicas on a disk below its minimal-available threshold. Failing SSD: the pending-sector SSD is the likeliest first failure; watch Node → Disk status and the SMART data of the SSD that reported 3 pending sectors (see the Proxmox PR's host inventory).
-   **Upgrades:** Renovate bumps the chart version in `kubernetes/argo/apps/app-cluster/storage/longhorn.yaml`. Longhorn supports upgrades one minor at a time and requires healthy volumes; read the release notes, and upgrade engines afterwards.
-   **First rollout (2026-11-09), what to expect:** each worker drained, upgraded (reboot) and then applied the config without a second reboot. After the apply the `u-longhorn` volume appears within seconds and the kubelet restarts once (extraMounts), so pods on that node restart again briefly; `longhorn-verify` therefore waits for the volumes, the mount and a healthy kubelet. The apps pinned to a worker by local-path volumes (Immich database on `k8s-wrkr-02`, Jellyfin on the GPU worker, the media managers on `k8s-wrkr-03`) were unavailable for the duration of that worker's reboot, a few minutes each. After the GPU worker's reboot the NVIDIA operator pods needed about two minutes to republish `nvidia.com/gpu`; Jellyfin stays `Pending` until then. Longhorn also creates a second, non-default `longhorn-static` StorageClass (reclaim `Delete`); it is chart-created and unused.

### A worker is down (unplanned)

`node-down-pod-deletion-policy` is `do-nothing` ([decision](../architecture/longhorn.md#node-down-pod-deletion-policy-decision-2026-11-10)): a pod with a Longhorn volume on a lost worker stays `Terminating` and its replacement waits in `ContainerCreating` until you act. Not tested yet on this cluster.

1.  `KubernetesNodeNotReady` fires. Find the affected pods: `kubectl get pods -A -o wide --field-selector spec.nodeName=<node>`; Longhorn consumers are the claims with storage class `longhorn`.
2.  **Fence first.** On `pve-00`, confirm the VM is stopped (`qm status <vmid>`: 4095 `k8s-wrkr-01-gpu`, 4096 `k8s-wrkr-02`, 4097 `k8s-wrkr-03`), or stop it. Do not continue while the VM may still be running: two writers corrupt the filesystem.
3.  Force-delete only the stuck pod: `kubectl -n <ns> delete pod <pod> --force --grace-period=0`. The volume is reattached on a healthy worker and the replacement pod starts with the same data. The volume runs `degraded` on two replicas until the worker returns.
4.  Start the VM, wait for the node to be `Ready` and the volume to return to `healthy` (the replica rebuilds).

## Rollback

Pick the earliest point that applies. Nothing here should be done while apps use Longhorn volumes unless their data has been restored elsewhere (Backrest) first.

1.  **Before the Argo sync (steps 1-4 only):** the Longhorn pieces are inert. Undo in reverse: revert the Talos change and apply it (`task talos:app:apply-node`) to remove the `longhorn` volume and bind mount, optionally `talosctl upgrade` back to the old schematic IDs (`3765…` plain, `af8eb82…` GPU) and `VERSION=v1.13.8`; detach `scsi2` via the Terraform PR revert; leave the Proxmox PR's wipe in place (it only removed old signatures).
2.  **After the sync, no Longhorn PVCs in use:** `argocd app delete longhorn` (the namespace has `Delete=false`, so remove it manually only after `kubectl get volumes.longhorn.io -A` is empty and you have set the `deleting-confirmation-flag` setting as Longhorn requires for uninstall), then step 1. Remove the default class first or at the same time; `local-path` needs no change.
3.  **Longhorn PVCs in use:** restore each app's data from Backrest into a new `local-path` PVC, repoint the app, then continue with 2. Retained PVs keep data on the SSDs; wipe the SSDs (`talosctl wipe disk <partition> --drop-partition` or the Proxmox role) only when sure the data is no longer needed.
4.  **Merge revert only (before sync):** reverting this PR in Git while Talos is already changed leaves nodes with the new extensions and volume, which is harmless; re-run `task talos:app:generate-config` and reapply to realign.
