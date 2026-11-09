# Longhorn on the app-cluster

**Status:** prepared in Git, **not applied**. Nothing described here is live until the operator runs the [rollout](../operations/longhorn.md#rollout-order).

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
-   Repository convention is unchanged: **config/state PVCs keep `storageClass: local-path`** and are backed up by Backrest. No application is migrated to Longhorn in this work.

## Limits, honestly

-   **Single failure domain.** All three SSDs sit in one physical host (`pve-00`), and the three workers are VMs on it. Three replicas protect against a single SSD, VM or worker failure and allow node maintenance. They do **not** protect against loss of the host, its power, the SATA controller, an operator error on `pve-00`, or deletion/corruption inside a volume (replicas replicate the damage). One of the three SSDs has 3 pending sectors (owner-accepted); expect it to be the first to fail.
-   **Longhorn volumes are not a backup.** Backrest (`docs/operations/backrest.md`) remains the backup mechanism, and an app on Longhorn must still be enrolled in `app-protect`. No Longhorn backup target or snapshot schedule is configured here.
-   **Capacity.** About 465 GiB raw per node, about 420 GiB schedulable after the 10% reserve (Longhorn's 25% minimal-available threshold lowers this further). With 3 replicas every volume consumes its size on all three nodes, so the usable pool is about **one SSD** (roughly 300-400 GiB of volume capacity).
-   **Performance.** SATA SSDs shared by Longhorn's synchronous 3-way replication and the host's page cache; fine for config/state, not benchmarked.
-   **Out of scope:** migrating apps, the infra-cluster (physical), a Longhorn backup target, V2 data engine, monitoring dashboards/alerts for Longhorn.

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
