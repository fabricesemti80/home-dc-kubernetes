# 🎬 Media Management Rollout

> This plan is scoped to the app-cluster media namespace as part of the broader [app-cluster standalone refactor](./app-cluster-standalone-refactor.md). The parent plan owns cluster topology, Talos bootstrap, local-path provisioner installation, and GPU operator enablement; this document owns media workload placement, storage migration, and Tdarr removal.

## 📌 New cluster topology

The replacement app cluster runs one controller and three workers:

| Node              | Role          | IP           | Workloads                                                                                      |
| ----------------- | ------------- | ------------ | ---------------------------------------------------------------------------------------------- |
| `k8s-ctrl-01`     | control-plane | `10.0.40.90` | no user workloads (tainted)                                                                    |
| `k8s-wrkr-01-gpu` | worker (GPU)  | `10.0.40.95` | Jellyfin                                                                                       |
| `k8s-wrkr-02`     | worker        | `10.0.40.96` | Immich server/Redis/Postgres                                                                   |
| `k8s-wrkr-03`     | worker        | `10.0.40.97` | Immich machine learning, SABnzbd, qBittorrent, Sonarr, Radarr, Prowlarr, Jellyseerr, Recyclarr |

All media config/state PVCs use `storageClass: local-path` and `accessMode: ReadWriteOnce`. The shared `media-library-pvc` (NFS) remains unchanged for `/media`, `/downloads`, and `/data mounts`.

## 📌 Placement rationale

-   `k8s-wrkr-01-gpu` hosts Jellyfin so hardware transcoding can be enabled once the NVIDIA device plugin advertises `nvidia.com/gpu`.
-   Immich server/Redis/Postgres stay co-located on worker 02; its machine-learning cache is on worker 03.
-   Media managers are pinned to worker 03; the entire app-cluster monitoring stack and other unused apps are retired rather than migrated.
-   Each RWO PVC is pinned to a worker via `nodeSelector` so the pod remains co-located with its volume.

## 📌 Storage migration

-   CephFS-backed app PVCs are migrated to `local-path` `ReadWriteOnce`.
-   The existing NAS NFS `media-library-pvc` is preserved for shared media/downloads mounts.
-   Live PVCs and PVs are not deleted; new local-path PVCs will be provisioned on first sync in the fresh cluster.

## 📌 Tdarr removal

`tdarr` is removed from the rollout:

-   `kubernetes/apps/app-cluster/media/tdarr/` deleted
-   `kubernetes/argo/apps/app-cluster/media/tdarr.yaml` deleted
-   Tdarr references removed from homepage annotations and AutoKuma generation; Glance was retired separately.
-   `infra/terraform_localdns` no longer declares the Tdarr CNAME, but its UniFi credentials are absent from scoped Doppler; do not apply until the stack's ownership and a scoped plan are confirmed. Active internal DNS remains on Technitium.
-   The `tdarr-cache` NFS subpath is left in place and can be cleaned up manually after confirming no active transcode state
-   The existing infra-cluster AutoKuma monitor for Tdarr is intentionally untouched because this migration must not alter the physical cluster; it may report Tdarr unavailable until a separately authorized infra-cluster monitoring change.

## 📌 Phase 1 — Preparation

-   [x] Decide to reuse the `media` namespace for management services
-   [x] Choose `sabnzbd` instead of `nzbget` for the first downloader rollout
-   [x] Keep NFS for media paths; migrate app configs from CephFS to local-path
-   [x] Defer cross-app API-key automation until base services are stable
-   [x] Remove Tdarr from the stack

## 📌 Implementation

-   [x] Update placement for all media `values.yaml` to worker nodes
-   [x] Migrate media app PVCs from `cephfs`/`ReadWriteMany` to `local-path`/`ReadWriteOnce`
-   [x] Pin Jellyfin to `k8s-wrkr-01-gpu`, set `runtimeClassName: nvidia`, and add `nvidia.com/gpu: "1"` limit
-   [x] Update app-owned READMEs to describe local-path storage
-   [x] Remove Tdarr manifests, Argo application, and related references
-   [ ] Sync Argo CD and verify workloads become healthy

## 📌 Operator Steps

-   [ ] Confirm dedicated local-path data disks are mounted on each worker at `/var/mnt/local-path-provisioner`
-   [ ] Confirm the local-path StorageClass is installed and uses `WaitForFirstConsumer`/`Retain`
-   [ ] Confirm `/media/downloads/complete` exists on the NFS server
-   [ ] Confirm `/media/downloads/incomplete` exists on the NFS server
-   [ ] Open `https://sabnzbd.krapulax.dev`
-   [ ] Complete SABnzbd first-run setup
-   [ ] Add Usenet server details in the SABnzbd UI unless a later Doppler-backed bootstrap is introduced
-   [ ] Open `https://qbittorrent.krapulax.dev`
-   [ ] Complete qBittorrent first-run setup
-   [ ] Add `QBITTORRENT_WEBUI_PASSWORD` to Doppler (`home-dc-kubernetes/apps`) before syncing qBittorrent
-   [ ] Set qBittorrent save path to `/downloads` and temporary path to `/incomplete-downloads`
-   [ ] Forward `6881/TCP` and `6881/UDP` from the router to the qBittorrent peer service
-   [ ] Open `https://sonarr.krapulax.dev`
-   [ ] Configure Sonarr root folders and downloader integration
-   [ ] Open `https://prowlarr.krapulax.dev`
-   [ ] Add indexers in Prowlarr
-   [ ] Add Sonarr as an app in Prowlarr using `http://sonarr.media.svc.cluster.local:8989`
-   [ ] Add `SONARR_API_KEY` to Doppler for Recyclarr
-   [ ] Verify Recyclarr syncs Sonarr quality settings
-   [ ] Open `https://radarr.krapulax.dev`
-   [ ] Configure Radarr root folders and downloader integration
-   [ ] Open `https://requests.krapulax.dev`
-   [ ] Connect Jellyseerr to Jellyfin, Sonarr, and Radarr
-   [ ] After GPU operator/device plugin advertises `nvidia.com/gpu`, verify Jellyfin hardware transcode; fall back to CPU transcode if GPU is unavailable

## ✅ Validation

-   [ ] `kubectl get nodes -o wide` shows `k8s-wrkr-01-gpu`, `k8s-wrkr-02`, `k8s-wrkr-03` Ready
-   [ ] `kubectl get pods -n media`
-   [ ] `kubectl get pvc -n media`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=sabnzbd`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=qbittorrent`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=sonarr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=prowlarr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=recyclarr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=radarr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=jellyseerr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=jellyfin` and confirm node `k8s-wrkr-01-gpu`
-   [ ] `kubectl exec -n media deploy/sabnzbd -- grep '^host_whitelist' /config/sabnzbd.ini`
-   [ ] `curl -I https://sabnzbd.krapulax.dev/`
-   [ ] `curl -I https://qbittorrent.krapulax.dev/`
-   [ ] `kubectl get svc -n media qbittorrent-peer`
-   [ ] `kubectl get dopplersecret -n doppler-operator-system qbittorrent-secrets`
-   [ ] `curl -I https://sonarr.krapulax.dev/`
-   [ ] `curl -I https://prowlarr.krapulax.dev/`
-   [ ] `curl -I https://radarr.krapulax.dev/`
-   [ ] `curl -I https://requests.krapulax.dev/`
-   [ ] `kubectl logs -n media deploy/recyclarr --tail=100`
-   [ ] `curl -I https://jelly.krapulax.dev/`
-   [ ] Confirm Jellyfin `/health` body reports `Healthy`
-   [ ] Verify an actual GPU transcode in Jellyfin logs once `nvidia.com/gpu` is available

## 🤔 Assumptions

-   The local-path provisioner and dedicated worker data disks are installed and sized by the parent storage work before app sync.
-   The NFS export `10.0.40.2:/media` is reachable from all workers and contains the expected `/media/downloads/complete` and `/media/downloads/incomplete` paths.
-   `media-library-pvc` remains the shared NFS claim for media/downloads mounts.
-   Jellyfin GPU scheduling intentionally gates on the NVIDIA device plugin; the pod will remain `Pending` until `nvidia.com/gpu` is advertised.
-   Worker capacity is 4 vCPU / 10 GiB; current CPU limits may exceed single-worker allocatable and should be reviewed after the first sync.
-   Tdarr state in the old CephFS/NFS paths is no longer needed; live PVCs are not deleted by this change.

## ↩️ Rollback

-   Before DNS cutover, stop Argo sync to the replacement cluster and keep the old deployment/routes available if storage is still usable.
-   To revert Jellyfin GPU placement, remove `runtimeClassName: nvidia` and the `nvidia.com/gpu` limit, then move the `nodeSelector` to a CPU worker.
-   To roll back a failed local-path app, restore its config/database backup onto the same worker's RWO volume; do not move the pod to another worker without restoring data.
-   Delete the media Argo applications and their HTTPRoutes if the entire stack must be withdrawn.
-   Retain NFS media content and download directories; do not delete retained PVs as an implicit cleanup step.

## 📌 Follow-Up

-   [ ] Design and implement API-key bootstrap automation
-   [ ] Review CPU/memory limits against actual 4 vCPU/10 GiB worker capacity after sync
