# Longhorn on the app-cluster

**Status:** live since 2026-11-09 (rollout done, Argo Application still on manual sync). Every app-cluster app claim runs on it since 2026-11-10: freqtrade (pilot) and the 14 claims migrated one app at a time (see [#552](https://github.com/fabricesemti80/home-dc-kubernetes/issues/552) and the [runbook](../operations/local-path-to-longhorn.md)). The old local-path claims are retained for rollback. Soak in progress, see [#551](https://github.com/fabricesemti80/home-dc-kubernetes/issues/551).

## Problem

All app-cluster state lives on `local-path` volumes: node-local, bound to the worker that first used them, and lost with that worker's 100 GiB virtual data disk. Three unused 500 GB SATA SSDs (Crucial MX500, about 465.76 GiB each) sit in `pve-00`. The goal is replicated block storage on those SSDs that apps can adopt later, without touching the existing `local-path` volumes.

## Decision

| Layer        | Change                                                                                                                                                                                                            | Where                    |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| Proxmox host | Prepare the three SSDs (optional guarded signature wipe)                                                                                                                                                          | `home-dc-proxmox` PR     |
| Proxmox VM   | Raw whole-disk passthrough as `scsi2`: 4095 `k8s-wrkr-01-gpu` ← `ata-CT500MX500SSD1_2344E8836BF7`, 4096 `k8s-wrkr-02` ← `ata-CT500MX500SSD1_2344E8836D00`, 4097 `k8s-wrkr-03` ← `ata-CT500MX500SSD1_2349E8875927` | `home-dc-terraform` PR   |
| Talos        | Image Factory schematics with `iscsi-tools` and `util-linux-tools`; `longhorn` user volume selected by size; kubelet bind mount of `/var/mnt/longhorn`                                                            | this repo, `talos/app`   |
| Kubernetes   | Longhorn `1.13.0` (Helm chart, Argo CD Application), 3 replicas, data path `/var/mnt/longhorn`, default StorageClass `longhorn`                                                                                   | this repo, `kubernetes/` |

### Talos

-   **Schematics** (public, non-secret; created with `POST https://factory.talos.dev/schematics` and recorded in [`talos/README.md`](../../talos/README.md#image-factory-schematics)):
    -   workers 02/03: `613e1592b2da41ae5e265e8789429f22e121aab91cb4deb6bc3c0b6262961245` = `iscsi-tools` + `util-linux-tools` (was the empty schematic `3765…`);
    -   GPU worker: `fb73a1920c434ba8ec579d24f15097f18ffb171342b1c61f68c063d1b2b601c2` = `iscsi-tools` + `nonfree-kmod-nvidia-lts` + `nvidia-container-toolkit-lts` + `util-linux-tools` (was `af8eb8…`; the 580-series LTS pair is kept unchanged);
    -   the control plane keeps `3765…`: Longhorn does not run there (NoSchedule taint, no data disk).
    -   All four extensions were confirmed to exist for Talos `v1.13.12` in the factory's official extension list.
-   **Disk selection by size, never by name.** Talos `UserVolumeConfig` selects disks with a CEL expression; `/dev/sdX` names are not stable. Per worker there are three disks: the 55 GiB system disk, the 100 GiB `local-path-provisioner` data disk and the new ~465 GiB SSD.
    -   `local-path-provisioner`: `!system_disk && disk.size < 200u * GiB` (was `!system_disk`, which would also match the new SSD on a fresh node), `minSize: 80GiB`, `maxSize: 90GiB` unchanged.
    -   `longhorn`: `!system_disk && disk.size > 400u * GiB`, `minSize: 400GiB`, `grow: true`. Mounted by Talos at `/var/mnt/longhorn`.
    -   The two sizes are disjoint by more than a factor of two, so neither selector can match the other's disk. Talos finds an existing volume by its partition label (`u-<name>`), so the already-provisioned `local-path-provisioner` partition keeps being used.
-   **Kubelet bind mount.** Longhorn needs `/var/mnt/longhorn` visible in the kubelet mount namespace with `rshared` propagation (Longhorn's Talos guide for Talos ≥ 1.10: `extraMounts` of `type: bind`, options `bind, rshared, rw`). It is a **worker-only** patch (`talos/app/patches/worker/machine-longhorn.yaml`): the control plane has no such volume and a bind mount with a missing source would endanger the kubelet there.
-   The `worker:` block of `templates/config/talos/talconfig.yaml.j2` now carries both `userVolumes` and `patches` in one mapping (previously a second `worker:` key would have been emitted as soon as a worker patch existed).

### Longhorn

-   Chart `longhorn` `1.13.0` from `https://charts.longhorn.io` (requires Kubernetes ≥ 1.34; cluster runs 1.36). Pinned in the Argo CD Application so Renovate (argocd manager) proposes updates.
-   Namespace `longhorn-system`, label `pod-security.kubernetes.io/enforce: privileged` (Talos defaults to baseline), annotation `Prune=false,Delete=false` so a stray Argo prune cannot delete every volume.
-   `defaultSettings.defaultDataPath: /var/mnt/longhorn`, replica count 3 (settings and StorageClass), `storageReservedPercentageForDefaultDisk: "10"` (the data path is a dedicated partition; the chart default of 30% would waste ~140 GiB per node), usage metrics and upgrade checker off, `preUpgradeChecker.jobEnabled: false` (Longhorn's guidance for Argo CD).
-   StorageClass `longhorn`: **default class**, `reclaimPolicy: Retain` (repository standard: PVC deletion preserves data), `volumeBindingMode: Immediate`, ext4.
-   UI: internal only, `HTTPRoute` `longhorn.krapulax.home` on `envoy-internal` (same pattern as Backrest and the media apps). No Cloudflare tunnel route and no public hostname. The UI has no authentication and can delete volumes, so it relies on the trusted LAN exactly like the other internal UIs; if that is not acceptable, remove `http-route-internal.yaml` and use `kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80`.
-   **DNS.** The route carries `external-dns.alpha.kubernetes.io/target: kubernetes.krapulax.home`. The Technitium ExternalDNS instance (`--gateway-name=envoy-internal`, RFC2136, zone `krapulax.home`) publishes `longhorn.krapulax.home` automatically once the Application is synced; there is no manual DNS record and no Cloudflare record. Validation: `dig +short longhorn.krapulax.home` equals `dig +short kubernetes.krapulax.home` (`10.0.40.102`). Before the sync the name does not resolve (observed 2026-11-08).
-   **Homepage.** The UI is listed on the Homepage dashboard as `Longhorn` in the group `App Cluster - storage`, linking to `http://longhorn.krapulax.home`. It is a static entry (`STATIC_APP_STORAGE` in `scripts/ensure-homepage-annotations.py`) because Homepage does not discover internal-only routes, like Freqtrade. The description says there is no login.
-   **No secrets** are introduced (no backup target is configured; `docs/secrets-and-env-vars.md` is unchanged).
-   **Ordering.** The Application uses sync wave `1` (after Cilium, Envoy Gateway and the other wave-0 platform apps, and after `local-path` at `-1`). It also has **no `automated` sync** on purpose: merging the PR must not deploy Longhorn onto Talos nodes that lack the extensions, volume and bind mount, nor change the cluster's default StorageClass before storage is verified. It is synced manually as the last rollout step; a follow-up PR enables automation (precedent: `cloudflare-dns`).

### Default StorageClass

Observed read-only on 2026-11-08: the only StorageClass is `local-path` and it is **already not the default** (`local-path` values set `defaultClass: false`; the live annotation is `false`). Making `longhorn` the default therefore does not need a change to `local-path`; the repository keeps `defaultClass: false` explicitly and `scripts/validate.sh` now fails if any chart other than Longhorn sets a default class.

-   **Unaffected:** every existing PVC (a bound PVC never changes class), and every app with an explicit `storageClass`/`storageClassName`. All app-cluster apps in Git set `local-path` explicitly, or `storageClassName: ""` for the static NFS claims (`media-library-pvc`, `k8s-backup`), which opt out of any default.
-   **Could change:** a PVC (or StatefulSet `volumeClaimTemplate`) created **without** a class, by a future app or a chart update, will now be provisioned by Longhorn (3 replicas, `Retain`) instead of staying `Pending`. A PVC already `Pending` without a class would also be assigned `longhorn` retroactively once the default exists. None exists today: a review of `kubernetes/apps/app-cluster` found only explicit classes, and a read-only `kubectl get pvc -A` on 2026-11-08 showed 15 `local-path` claims and two static NFS claims with `storageClassName: ""`.
-   Repository convention (updated 2026-11-10): **app-cluster config/state PVCs use explicit Longhorn claims** and are backed up by Backrest; `local-path` stays only for retained rollback claims and the infra-cluster. The migration is described in the [runbook](../operations/local-path-to-longhorn.md).

## Limits, honestly

-   **Single failure domain.** All three SSDs sit in one physical host (`pve-00`), and the three workers are VMs on it. Three replicas protect against a single SSD, VM or worker failure and allow node maintenance. They do **not** protect against loss of the host, its power, the SATA controller, an operator error on `pve-00`, or deletion/corruption inside a volume (replicas replicate the damage). One of the three SSDs has 3 pending sectors (owner-accepted); expect it to be the first to fail.
-   **Longhorn volumes are not a backup.** Backrest (`docs/operations/backrest.md`) remains the backup mechanism, and an app on Longhorn must still be enrolled in `app-protect`. No Longhorn backup target or snapshot schedule is configured here.
-   **Capacity.** About 465 GiB raw per node, about 420 GiB schedulable after the 10% reserve (Longhorn's 25% minimal-available threshold lowers this further). With 3 replicas every volume consumes its size on all three nodes, so the usable pool is about **one SSD** (roughly 300-400 GiB of volume capacity).
-   **Performance.** SATA SSDs shared by Longhorn's synchronous 3-way replication and the host's page cache; fine for config/state, not benchmarked.
-   **Out of scope:** migrating apps, the infra-cluster (physical), a Longhorn backup target, V2 data engine, monitoring dashboards/alerts for Longhorn.

## Node-down pod deletion policy (decision 2026-11-10)

**Decision: keep `node-down-pod-deletion-policy: do-nothing`** (Longhorn's default; `values.yaml` does not set it, live value `do-nothing` read on 2026-11-10). No Git change. Recovery from an unplanned single-worker failure is a manual, fenced step: [Longhorn operations, worker down](../operations/longhorn.md#a-worker-is-down-unplanned).

### Context

-   With `do-nothing`, Kubernetes never force-deletes a pod on a node that stops reporting: after about 5 minutes it is marked for deletion and stays `Terminating`. The `ReadWriteOnce` Longhorn volume stays attached to the lost node, so a Deployment's replacement pod hangs in `ContainerCreating` and a StatefulSet creates no replacement at all (Longhorn 1.13 docs, _Node Failure Handling_). The app stays down until the node returns or an operator force-deletes the old pod.
-   The other options force-delete such pods so the volume can be reattached elsewhere: `delete-deployment-pod`, `delete-statefulset-pod`, `delete-both-statefulset-and-deployment-pod`.
-   Only Longhorn volumes are affected, and since 2026-11-10 that is every app-cluster app claim: with `do-nothing` an unplanned worker failure leaves its Longhorn-backed pods (media apps, Immich, Backrest, vmagent) down until the operator fences the VM and force-deletes them. Node pins kept for Immich, Backrest and Jellyfin (GPU) still tie those pods to one worker; the others (arr group, qBittorrent, Jellyseerr, Recyclarr, Prowlarr) no longer have one.
-   The 2026-11-10 decision below was taken when freqtrade was the only Longhorn consumer; **revisit it now that production workloads use Longhorn** (the revisit trigger below has been met).
-   Related setting, live `true` (default): `auto-delete-pod-when-volume-detached-unexpectedly`. Longhorn already restarts a controller-managed pod whose volume was detached under it.

### Options

| Option                                       | Effect for freqtrade (Deployment, RWO)                                                      | Benefit                                                                       | Risk / cost                                                                                                                                                                                                                     |
| -------------------------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `do-nothing` (current, **chosen**)           | Down until the worker returns or an operator force-deletes the pod                          | No unfenced takeover. The operator checks the VM is off before moving the app | Unattended recovery needs a person. `KubernetesNodeNotReady` (5 min) alerts on Slack                                                                                                                                            |
| `delete-deployment-pod`                      | Pod force-deleted, volume reattached and pod started on a healthy worker, typically minutes | Unattended failover for a crashed worker VM                                   | No fencing: "node down" means the kubelet stopped reporting, not that the VM is off. A hung kubelet whose container keeps writing, or a worker that comes back, briefly gives two writers on one ext4 filesystem. Untested here |
| `delete-statefulset-pod`                     | No effect (freqtrade is not a StatefulSet)                                                  | None today                                                                    | Same no-fencing risk for any future StatefulSet                                                                                                                                                                                 |
| `delete-both-statefulset-and-deployment-pod` | Same as `delete-deployment-pod`                                                             | Covers future StatefulSets too                                                | Widest blast radius of the no-fencing risk                                                                                                                                                                                      |

### Why `do-nothing` fits this topology

-   **The policy only matters for one VM failing alone.** All three workers are VMs on `pve-00`. Planned maintenance uses drains (policy not involved). Losing the host takes every worker and every replica at once, and no policy helps.
-   **That failure is rare and fencing is cheap.** The operator can confirm in Proxmox that the VM is stopped (or stop it) in a minute, which removes the two-writer risk an automatic force-delete cannot rule out.
-   **The pilot gains little.** A dry-run bot can be down for hours. The volumes that would later gain most from automatic failover (Immich PostgreSQL) are the ones where an unfenced takeover could do most damage.
-   **Untested.** Node-failure behaviour on this cluster has not been tested. The 2026-11-09 failover test cordoned the node and deleted the pod, which is the planned-maintenance path.

### Assumptions

1.  `KubernetesNodeNotReady` (infra-cluster vmalert, `for: 5m`) reaches the operator for app-cluster workers.
2.  Hours of freqtrade downtime after an unplanned worker failure are acceptable.
3.  Kubernetes' non-graceful node shutdown (`node.kubernetes.io/out-of-service` taint, GA since 1.28) is a fenced alternative to deleting the pod by hand. It has not been tested with Longhorn here.

### Revisit when

-   an app whose downtime matters moves to Longhorn, or a StatefulSet does; or
-   a controlled node-failure test is run (stop one worker VM in Proxmox, time the manual recovery, then repeat with `delete-deployment-pod` on a scratch Deployment).

If it changes, set `defaultSettings.nodeDownPodDeletionPolicy` in `kubernetes/apps/app-cluster/storage/longhorn/values.yaml`. The Longhorn Application syncs manually, so the change goes live only after `argocd app sync longhorn`. Rollback: remove the key and sync again (setting changes do not restart volumes).

### Next actions

-   [x] Record the decision and the manual recovery procedure (2026-11-10).
-   [ ] Controlled node-failure test on a scratch Longhorn Deployment (needs its own issue; not opened yet).

## Assumptions

1.  At rollout the live nodes ran Talos `v1.13.8` while `talenv.yaml` targeted `v1.13.12`; the extensions exist for both versions in the Image Factory. The runbook upgrades with an explicit `VERSION` so the schematic change and the Talos version bump are separate decisions. All four nodes were moved to `v1.13.12` afterwards (2026-11-09), and the NVIDIA modules plus a GPU transcode were verified on that version.
2.  The Terraform PR attaches the SSDs as `scsi2` (QEMU HARDDISK, `ssd=1`, `discard=on`; serials equal the SSD serials), so the guest sees one ~465 GiB disk per worker. The attach needs a VM stop/start (operator step).
3.  The SSD's old signatures are gone before Talos first sees the disk (Proxmox PR's guarded wipe, or `talosctl wipe disk`), because Talos only provisions a volume on a disk with sufficient **free** space; a foreign partition table can make that fail.
4.  Talos `v1.13`'s CEL environment supports `disk.size`, `GiB`, `system_disk` (documented for v1.13) and `talosctl validate` accepts the rendered documents (verified offline).
5.  Longhorn's host dependencies are satisfied by the two extensions plus Talos' default kubelet image (NFS client, `fstrim` via `util-linux-tools`).
6.  Cluster nodes are `k8s-wrkr-01-gpu`, `-02`, `-03` only; the NoSchedule-tainted control plane runs no Longhorn pods.

## Validation

Pre-merge (done in the PR, offline): `talhelper validate talconfig`, `talhelper genconfig` to a temp dir plus `talosctl validate --mode metal` on all four machine configs, `helm template` + `kubeconform`, `kustomize build`, `scripts/validate.sh`. Post-rollout checks are listed in the [runbook](../operations/longhorn.md#verification).

## Rollback

See the [runbook](../operations/longhorn.md#rollback). In short: before any app uses Longhorn, rollback is to remove the Application (`Delete=false` on the namespace keeps it safe while volumes exist), revert the Talos configuration and re-apply it, then detach the SSDs in Terraform. Reverting the Git change alone changes nothing live.
