# Migrating an app from local-path to Longhorn

One app at a time. The aim is an app whose data is no longer tied to one worker: after the move it can be rescheduled to another node, and a node drain no longer takes the app down with it. Longhorn is **not** a backup (all three replicas live on the same host); Backrest stays the backup of record, see [Backups](#backups-and-this-change).

Pilot: **freqtrade** (a dry-run trading bot with a ~100 KB SQLite database), worked example at the end.

## Migration status (2026-11-10)

Every app-cluster claim has been moved, one app per PR, with a quiesced offline copy (`scripts/longhorn-copy-offline.sh`) and its own backup, isolated restore and post-cutover verification. Tracking issue: [#552](https://github.com/fabricesemti80/home-dc-kubernetes/issues/552).

| App               | Claims                                                            | PR   |
| ----------------- | ----------------------------------------------------------------- | ---- |
| freqtrade (pilot) | `freqtrade-data`                                                  | #537 |
| Recyclarr         | `recyclarr`                                                       | #566 |
| Prowlarr          | `prowlarr`                                                        | #567 |
| Jellyseerr        | `jellyseerr`                                                      | #568 |
| Sonarr            | `sonarr`                                                          | #569 |
| Radarr            | `radarr`                                                          | #570 |
| SABnzbd           | `sabnzbd`                                                         | #571 |
| qBittorrent       | `qbittorrent`                                                     | #572 |
| Jellyfin          | `jellyfin-config`, `jellyfin-cache`                               | #573 |
| Immich            | `immich-postgres-data`, `immich-redis-data`, `immich-model-cache` | #574 |
| Backrest          | `backrest`                                                        | #575 |
| vmagent           | `persistent-queue-data-vmagent-…-0`                               | #576 |

**The 14 old local-path claims were deleted on 2026-11-10**, at the operator's explicit request and ahead of the 2026-11-14 soak gate ([#578](https://github.com/fabricesemti80/home-dc-kubernetes/issues/578)). Verified before: every claim `Retain`, mounted by no pod, all apps `Synced`/`Healthy`, all 15 Longhorn volumes `healthy`, a post-cutover restore verified per app. Procedure: delete the PVC, delete the PV (`Retain` leaves the files), then remove exactly each `<pv>_<ns>_<claim>` directory on its node with a short-lived `busybox` pod in `local-path-storage` (hostPath, exact names, refuses anything not matching `pvc-*_*_*`). Result: 0 local-path PVCs and PVs; the 14 directories removed (`removed …` logged for each). One snag: two completed manual export pods from before the Backrest cutover still referenced the old `backups/backrest` claim and kept its `pvc-protection` finalizer; deleting those two finished Jobs released it.

**Rollback for these apps is now Backrest only** (restore the app's last `app-<name>` snapshot into a new Longhorn claim; for Immich the native `immich-db` export). The "Rollback after step 3" procedure below no longer applies to them: there is no old volume to re-claim.

Not touched: 26 older directories on `k8s-wrkr-02` and `k8s-wrkr-03` named `backup-*-pilot-*` and `backup-restore-*`/`backrest-sql-proof-*` (orphaned leftovers of the earlier Backrest pilot drills; their PV objects no longer exist). They are not related to this migration and were left in place; the local-path provisioner itself stays deployed.

### Failover test (2026-11-10)

Planned-maintenance path, as for the freqtrade pilot: `k8s-wrkr-03` cordoned and the pods of the three movable apps on it deleted (radarr, sabnzbd, qBittorrent). All three restarted on the other workers (`k8s-wrkr-01-gpu`, `k8s-wrkr-02`) within about a minute, with their data: Radarr's library, SABnzbd idle and qBittorrent's 12 torrents; all 15 Longhorn volumes stayed `attached`/`healthy`. The node was then uncordoned. Not covered: pods that are still pinned (Immich, Backrest, the Immich ML pod, Jellyfin for the GPU) and an unplanned worker failure, which with `node-down-pod-deletion-policy: do-nothing` needs the operator to fence the VM and force-delete the pods ([operations](longhorn.md#a-worker-is-down-unplanned)).

### Recyclarr cutover (completed 2026-11-10)

Migrate only Recyclarr in this change; all other workloads remain on their current claims. The operator selected one-at-a-time cutovers after Longhorn's first day of pilot soak. The source is `media/recyclarr` (1 GiB, local-path, `Retain`); the manually pre-created target is `media/recyclarr-longhorn` (1 GiB, Longhorn, `Retain`). Recyclarr is a Deployment on `k8s-wrkr-03`, not a Kubernetes CronJob. Its `protect-recyclarr` job currently reads the source on that node; after cutover it follows the Recyclarr pod using pod affinity.

**Pre-merge gate:** confirm a recent successful `app-recyclarr` snapshot and healthy Longhorn nodes, pause `apps`, `recyclarr` and `app-protect` auto-sync, suspend `protect-recyclarr`, stop Recyclarr, and copy the complete quiesced source to the unused Longhorn target with `scripts/longhorn-copy-offline.sh media recyclarr recyclarr-longhorn`. Verify the copy and keep the source claim and PV (`Retain`, `Prune=false,Delete=false`). Do not merge until the verified copy exists and the source remains stopped. This offline final copy avoids the write-loss window in the earlier export-based procedure.

While Recyclarr remains scaled to zero and Argo is paused, atomically remove the live Deployment's defaulted RollingUpdate fields when setting Recreate; otherwise Argo server-side diff rejects the strategy change:

```sh
kubectl -n media patch deployment recyclarr --type=merge -p '{"spec":{"strategy":{"type":"Recreate","rollingUpdate":null}}}'
```

After merge, sync Recyclarr and app-protect, confirm the workload starts with the copied data, verify the Longhorn volume has three healthy replicas, run a fresh `protect-recyclarr` export and `app-recyclarr` Backrest backup and restore, then resume the original scheduling and auto-sync policies. Preserve the old volume for a multi-day soak. For rollback, stop writers, restore newer Longhorn data if needed, and retain or rebind the old source claim _before_ reverting as described below; never let Argo create an empty replacement.

**Observed outcome (#566):** The offline copy verified file contents, ownership, permissions and symlinks. Recyclarr started on `k8s-wrkr-01-gpu`; Longhorn volume `pvc-420ba2a5-fd50-4097-9f8f-8da65ed3dbed` was healthy with three running replicas. Its protect job followed it onto that node. Post-cutover Backrest snapshot `b1113a214c8b` restored successfully; restored settings and Sonarr/Radarr mapping files matched the new export. The original local-path claim remains Bound to retained PV `pvc-ac77dff5-a8a0-4f18-b180-e2dc0a26aade`, with `Prune=false,Delete=false` and `IgnoreExtraneous`; do not delete it during the soak. Argo automation and the protect schedule were restored.

### Prowlarr cutover (completed 2026-11-10)

Migrate only `media/prowlarr` (2 GiB, local-path, retained) to the pre-created `media/prowlarr-longhorn` (2 GiB, Longhorn, retained). Prowlarr contains SQLite state and indexer credentials: do not expose files or API keys when checking it. Confirm a fresh `app-prowlarr` backup and isolated SQLite restore before stopping it. Pause the `apps`, `prowlarr` and `app-protect` Argo Applications, suspend `protect-prowlarr`, annotate the source PVC `Prune=false,Delete=false`, and scale Prowlarr to zero. Run `scripts/longhorn-copy-offline.sh media prowlarr prowlarr-longhorn`; keep the writer stopped until the copy and its integrity checks pass. Patch the stopped Deployment strategy to `Recreate` with `rollingUpdate: null`, as in the Recyclarr example, before merging.

After merge, sync Prowlarr and app-protect, confirm the UI/API and indexer searches work without printing credentials, verify three healthy Longhorn replicas and take and restore a new `app-prowlarr` backup. Resume the protect schedule and original Argo settings. Preserve the old local-path claim and PV through a multi-day soak. Rollback requires quiescing Prowlarr and copying back any newer data before reverting; never allow a revert to provision an empty old claim.

**Observed outcome (#567):** Offline copy and copied SQLite integrity passed. Prowlarr started on `k8s-wrkr-01-gpu` with all four indexers and the Sonarr/Radarr connections; a live NZBgeek search returned 10 results. Longhorn volume `pvc-cf021a50-6fc3-40b2-9720-6028bc34d931` was healthy with three running replicas. Its protect job followed it; post-cutover snapshot `93d347ac0923` restored with SQLite integrity ok and four indexers. The old local-path claim and PV remain retained for rollback; Argo automation and the protect schedule were restored.

### Jellyseerr cutover (completed 2026-11-10)

Migrate `media/jellyseerr` (2 GiB, local-path, retained) to the pre-created `media/jellyseerr-longhorn` (2 GiB, Longhorn, retained). Stop Jellyseerr before the complete offline copy; retain its UID/GID 1000 ownership and do not expose API keys or settings. A fresh `app-jellyseerr` backup and isolated SQLite restore are prerequisites. Pause `apps`, `jellyseerr` and `app-protect`, suspend `protect-jellyseerr`, annotate the old claim `Prune=false,Delete=false` and `IgnoreExtraneous`, then scale Jellyseerr to zero. Copy and verify with `scripts/longhorn-copy-offline.sh media jellyseerr jellyseerr-longhorn`; keep the writer stopped until cutover. This Deployment already uses `Recreate`.

After merge, sync Jellyseerr and app-protect; verify its version, existing requests, default Sonarr/Radarr connections, three healthy replicas, and a fresh backup and restore. Resume the original protect schedule and Argo settings. Keep the old claim and PV for rollback and copy back newer data before reverting.

**Observed outcome (#568):** The quiesced offline copy verified file contents, ownership, modes and symlinks. The copied SQLite database passed integrity checks with 12 requests and root ownership `1000:1000`. Seerr 3.5.1 started on `k8s-wrkr-01-gpu` with the same 12 request statuses and default Sonarr/Radarr connections. Longhorn volume `pvc-580c5547-2e14-4d18-a278-1e5bb44351bb` was healthy with three running replicas. Its protect job followed the pod; post-cutover snapshot `c8fd35fc0e27` restored with SQLite integrity ok and 12 requests. The old claim and PV remain retained; Argo automation and the backup schedule were restored.

### Sonarr cutover (completed 2026-11-10)

Migrate `media/sonarr` (2 GiB, local-path, retained) to the pre-created `media/sonarr-longhorn` (2 GiB, Longhorn, retained). Confirm a fresh `app-sonarr` snapshot and isolated SQLite restore, then pause `apps`, `sonarr` and `app-protect` Argo reconciliation, suspend `protect-sonarr`, annotate the source PVC `Prune=false,Delete=false` and `IgnoreExtraneous`, and scale Sonarr to zero. Copy and verify the quiesced source with `scripts/longhorn-copy-offline.sh media sonarr sonarr-longhorn`. Keep the writer stopped until merge; patch the stopped Deployment strategy to `Recreate` with `rollingUpdate: null`, as in the Recyclarr example.

After merge, sync Sonarr and app-protect, verify series, download clients and indexers without exposing API keys, three healthy replicas, and a fresh backup and isolated SQLite restore. Restore the protect schedule and Argo policies. Preserve the old claim and PV through soak; rollback requires stopping Sonarr and restoring newer Longhorn data to the retained source before reverting.

**Observed outcome (#569):** The quiesced offline copy and copied SQLite integrity passed with 30 series. Sonarr started on `k8s-wrkr-01-gpu` with 30 series, two download clients, four indexers and one tag. Longhorn volume `pvc-7c678069-372c-46fa-800e-4662513770a8` was healthy with three running replicas. Its protect job followed the pod; post-cutover snapshot `33a991c1821e` restored with SQLite integrity ok and 30 series. The old claim and PV remain retained; Argo automation and the backup schedule were restored.

### Radarr cutover (completed 2026-11-10)

Migrate `media/radarr` (2 GiB, local-path, retained) to pre-created `media/radarr-longhorn` (2 GiB, Longhorn, retained). Confirm a fresh `app-radarr` snapshot and isolated SQLite restore, then pause `apps`, `radarr` and `app-protect` Argo reconciliation, suspend `protect-radarr`, annotate the source PVC `Prune=false,Delete=false` and `IgnoreExtraneous`, and scale Radarr to zero. Copy and verify the quiesced source with `scripts/longhorn-copy-offline.sh media radarr radarr-longhorn`. Keep the writer stopped until merge; patch the stopped Deployment strategy to `Recreate` with `rollingUpdate: null`, as in the Recyclarr example.

After merge, sync Radarr and app-protect, verify movies, download clients and indexers without exposing API keys, three healthy replicas, and a fresh backup and isolated SQLite restore. Restore the protect schedule and Argo policies. Preserve the old claim and PV through soak; rollback requires stopping Radarr and restoring newer Longhorn data to the retained source before reverting.

**Observed outcome (#570):** The quiesced offline copy and copied SQLite integrity passed with 57 movies. Radarr started on `k8s-wrkr-03` with 57 movies, one download client and three indexers. Longhorn volume `pvc-2c90dee3-c35e-4077-8ae3-ecd8327adc90` was healthy with three running replicas. Its protect job followed the pod; post-cutover snapshot `731ac5bb5cf3` restored with SQLite integrity ok and 57 movies. The old claim and PV remain retained; Argo automation and the backup schedule were restored.

### SABnzbd cutover (completed 2026-11-10)

Migrate `media/sabnzbd` (2 GiB, local-path, retained) to pre-created `media/sabnzbd-longhorn` (2 GiB, Longhorn, retained); shared NFS downloads remain unchanged. Confirm a fresh `app-sabnzbd` backup and isolated restore and record queue status without exposing API keys. Pause `apps`, `sabnzbd` and `app-protect`, suspend `protect-sabnzbd`, annotate the source PVC `Prune=false,Delete=false` and `IgnoreExtraneous`, and scale SABnzbd to zero. Copy the quiesced source with `scripts/longhorn-copy-offline.sh media sabnzbd sabnzbd-longhorn`; verify contents and keep the writer stopped until merge. Patch the stopped Deployment strategy to `Recreate` with `rollingUpdate: null`, as in the Recyclarr example.

After merge, sync SABnzbd and app-protect, verify the API and queue, three healthy replicas, and a fresh backup and isolated restore. Restore the protect schedule and Argo settings. Preserve the old claim and PV through soak; rollback requires stopping SABnzbd and restoring newer Longhorn data to the retained source before reverting.

**Observed outcome (#571):** Offline copy verified; copied history database passed integrity checks. SABnzbd started on `k8s-wrkr-03` with API responding and an empty idle queue. Longhorn volume `pvc-d30b8324-965c-4b16-bdc7-0063b8d90c2f` was healthy with three running replicas. Its protect job followed the pod; post-cutover snapshot `c20c60fcfd34` restored with matching configuration and history integrity ok. The old claim and PV remain retained; Argo automation and the backup schedule were restored.

### qBittorrent cutover (completed 2026-11-10)

Migrate `media/qbittorrent` (2 GiB, local-path, retained) to pre-created `media/qbittorrent-longhorn` (2 GiB, Longhorn, retained); the shared NFS downloads and the `qbittorrent-peer` LoadBalancer (10.0.40.104, `externalTrafficPolicy: Cluster`) are unchanged, so dropping the node pin is safe. Record the torrent count and states through the WebUI API without printing the password. Pause `apps`, `qbittorrent` and `app-protect`, suspend `protect-qbittorrent`, annotate the source PVC `Prune=false,Delete=false` and `IgnoreExtraneous`, scale qBittorrent to zero (torrents pause; partial data lives on NFS) and copy with `scripts/longhorn-copy-offline.sh media qbittorrent qbittorrent-longhorn`. It holds `qBittorrent.conf`, the queue settings changed on 2026-11-10 and resume data, none of it SQLite; compare file counts and the preference values after cutover. This Deployment already uses `Recreate`.

After merge, sync qBittorrent and app-protect, verify the torrent count matches, the Sonarr download client test passes, three healthy replicas, and a fresh backup and isolated restore of `qBittorrent.conf`. Restore the protect schedule and Argo settings. Preserve the old claim through soak.

**Observed outcome (#572):** Offline copy verified. qBittorrent started with the same 12 torrents and queue preferences; Sonarr reported no download-client health issues. Longhorn volume was healthy with three running replicas, the protect job ran on the pod's node and the post-cutover snapshot restored with a matching `qBittorrent.conf`. The node pin was dropped; the old claim and PV remain retained.

### Jellyfin cutover (completed 2026-11-10)

Migrate `media/jellyfin-config` (5 GiB, 1.9 GB used, SQLite library state) and `media/jellyfin-cache` (20 GiB, empty) to pre-created `jellyfin-config-longhorn` and `jellyfin-cache-longhorn`. The GPU node pin and `runtimeClassName: nvidia` **stay** (they exist for the NVIDIA GPU, not for local-path). The weekly `jellyfin-transcode-cleanup` CronJob now mounts the Longhorn cache claim and is pinned to the GPU node so it can attach the volume. Suspend `protect-jellyfin` and `jellyfin-transcode-cleanup`, pause `apps`, `jellyfin` and `app-protect`, annotate both source PVCs, scale Jellyfin to zero and copy each claim with `scripts/longhorn-copy-offline.sh`. Verify the copied SQLite databases and the media library counts after cutover, and that hardware transcoding still works.

**Observed outcome (#573):** Both offline copies verified. Jellyfin started on the GPU node with the Quadro P2000 visible and `/health` returning 200; both Longhorn volumes were healthy with three running replicas. The cleanup job ran against the Longhorn cache on the GPU node and the protect job ran on the same node. The post-cutover snapshot restored with its SQLite database passing integrity. Old claims retained.

### Immich cutover (completed 2026-11-10)

Migrate `immich-postgres-data` (20 GiB), `immich-redis-data` (2 GiB) and `immich-model-cache` (10 GiB) to the pre-created `-longhorn` claims in one change. Immich is down for the duration. Order: take a fresh native export (`task backups:export CLUSTER=app-cluster APP=immich-db`) and a successful `immich-db` Backrest run; pause `apps`, `immich` and `app-protect`; suspend `backrest-export-immich-db`; annotate the three source claims; scale `immich`, `immich-machine-learning` and `immich-redis` to zero, **then** the `immich-database` StatefulSet. Before copying, require `pg_controldata` on the source claim to report the cluster as `shut down` (a clean shutdown), then copy each claim with `scripts/longhorn-copy-offline.sh` (byte-for-byte compare). Node pins are kept in this change. After merge, check the database logs show a normal start (no crash recovery), asset and user counts via the application, ML and Redis connectivity, three healthy replicas for each volume, and a new native export plus `immich-db` backup.

**Observed outcome (#574):** Pre-cutover native export restored and fully read with `pg_restore`; the source PostgreSQL reported a clean shutdown (`pg_controldata`) before the offline byte-for-byte copies; the database started without crash recovery; asset, user and album counts matched the baseline (3518/1/0); Immich 3.3.6, ML and Redis answered; all three Longhorn volumes were healthy with three running replicas; a new native export and `immich-db` backup succeeded. Old claims retained, node pins kept.

### Backrest cutover (completed 2026-11-10)

Migrate `backups/backrest` (4 GiB; `/state` holds the generated `config.json`, the operation history and the Immich export staging) to the pre-created `backups/backrest-longhorn`. **Backrest's recovery now depends on Longhorn**: the repository itself stays on the NAS (`/k8s-backup/app-cluster/backrest/repository`) and its key has an independent Keychain copy (verified equal to Doppler's on 2026-11-10); `config.json` is regenerated from Git at start, so losing `/state` loses only operation history and the staging copy of the Immich export. The Backrest Deployment and the `backrest-export-immich-db` CronJob stay pinned to `k8s-wrkr-03` (a ReadWriteOnce volume must be attached where both run). The export job and `task backups:status` now name `backrest-longhorn`. Order: fresh `backrest-config` run, pause `apps`, `backrest-app`, suspend the export CronJob, scale Backrest to zero, annotate the source claim, copy with `scripts/longhorn-copy-offline.sh backups backrest backrest-longhorn`, merge, sync. Verify the UI/API login, repository access, a new `immich-db` export followed by an `immich-db` Backrest run, and `backups:status` output. While Backrest is stopped no backup plan runs; the `app-protect` export jobs write to the NAS and are unaffected.

**Observed outcome (#575):** A fresh `backrest-config` snapshot restored with a `config.json` identical to the live state before the stop. The offline copy verified. Backrest started on `k8s-wrkr-03`; the Longhorn volume was healthy with three running replicas. A new native Immich export followed by an `immich-db` Backrest run produced a snapshot whose `captured-at` was the post-cutover export, proving Backrest and the export job share the new volume. Old claim retained.

### vmagent queue cutover (completed 2026-11-10)

Migrate the StatefulSet-owned queue claim `monitoring/persistent-queue-data-vmagent-vmagent-app-victoria-metrics-k8s-stack-0` (5 GiB) to a standalone `...-longhorn` claim. A StatefulSet `volumeClaimTemplate` is immutable and always yields the same claim name, so the VMAgent is switched to Deployment mode (`statefulMode` off) with `spec.volumes` naming the new claim as `persistent-queue-data`; the operator (v0.75.2) then mounts it at `/tmp/vmagent-remotewrite-data`. This was exercised on a disposable VMAgent before the cutover: the operator removed the old StatefulSet, created a Ready Deployment on the Longhorn claim, and left the old claim untouched. Queue contents are buffered samples only. Order: pause `apps` and `vmagent-app`, set `spec.paused: true` on the VMAgent so the operator does not recreate the StatefulSet, scale the StatefulSet to zero, annotate the old claim, copy with `scripts/longhorn-copy-offline.sh monitoring <old> <new>` (the claim root is the queue), merge, sync, then unpause. Verify the Deployment is Ready, the old StatefulSet is gone, remote write resumes (`vmagent_remotewrite_*` series on the infra VictoriaMetrics) and the queue backlog drains.

**Observed outcome (#576):** The offline copy verified. The operator removed the old StatefulSet and the Deployment became Ready with `-remoteWrite.tmpDataPath=/tmp/vmagent-remotewrite-data` mounted from the Longhorn claim; the volume was healthy with three running replicas. Remote write returned 2XX (151 requests) with 0 pending bytes, 0 dropped packets and 0 retries. The old claim was left untouched. The control-plane scrape warnings (`10.0.40.90:10257` and `:10259`) in the vmagent log are not related to this change.

## Ground rules

-   **Argo CD auto-syncs with prune and self-heal.** Anything merged to `main` goes live within minutes. The order below exists because of that: the empty target volume is merged first, the data is copied while the old app keeps running, and only then does a second change switch the app over.
-   **Copy from the Backrest export, not from the live volume.** The `app-protect` job already captures SQLite through the online backup API, so the copy is consistent and the running app is not touched. The only data at risk is what the app writes between that export and the cutover, so do the copy and the cutover back to back.
-   **The old volume is kept.** local-path volumes are `Retain`: when Argo prunes the old PVC the data stays on the node as a `Released` PV. Do not delete it until the app has run on Longhorn for several days and a Backrest restore of the new volume's export has been checked.
-   **Do not migrate caches.** (Superseded for this migration: the operator asked for every app-cluster claim, including caches and the vmagent queue, to move; they were migrated.)
-   **Capacity.** About 350 GiB of volume space in total: every volume is stored on all three nodes (3 replicas) and Longhorn stops scheduling on a disk below 25% free. All current `local-path` requests together are about 85 GiB.
-   **Order of apps.** Small, low-importance apps first (freqtrade, then the arr group on `k8s-wrkr-03`); the Immich PostgreSQL volume last.

## Prerequisites

1.  Longhorn healthy: `kubectl -n longhorn-system get nodes.longhorn.io` shows all nodes `Ready` and `Schedulable`.
2.  `app-protect` supports `selector` (see [Backrest operations](backrest.md#protecting-and-opting-out-apps)): a Longhorn volume is attached to one node at a time, so the export job must run where the app runs.
3.  The app is protected (`kubectl -n <ns> get cronjob protect-<app>`) and its last Backrest run succeeded: `task backups:run CLUSTER=app-cluster PLAN=app-<app>`.
4.  The app's Deployment uses `strategy: Recreate` (a ReadWriteOnce volume cannot be mounted by an old and a new pod on different nodes at once). Single-instance apps already do.
5.  You know the user the app runs as (`runAsUser`/`runAsGroup`): the copy tool sets ownership to it.

## Procedure

### 1. Add the empty target volume (PR, safe to merge)

Add `config/pvc-data.yaml` to the app (explicit name `<app>-data`, `storageClassName: longhorn`, a size at least as large as the old claim, annotation `argocd.argoproj.io/sync-options: Prune=false`) and list it in `config/kustomization.yaml`. Merging creates an empty, unused, `Bound` volume. Nothing about the app changes.

```sh
kubectl -n <ns> get pvc <app>-data                          # Bound, storage class longhorn
kubectl -n longhorn-system get volumes.longhorn.io          # detached, healthy, 3 replicas
```

### 2. Copy the data (live, the app keeps running)

```sh
scripts/longhorn-migrate-copy.sh <ns> <app> <app>-data <uid> <gid>
```

The tool takes a fresh export, then copies it into the new volume in a one-off Job and checks every SQLite file with `PRAGMA integrity_check`. It refuses if the target is not `Bound` on `longhorn`, is used by any pod, or already holds files (`--force` overrides the last check). It never writes to the old volume. Files excluded from the app's backup (`excludes` in `app-protect/values.yaml`) are not copied: the app regenerates them, so make sure that is true for the app.

Verify before the cutover: compare the database contents (for example table row counts) between the live app and the copy, and confirm the files are owned by the app's user.

### 3. Switch the app over (PR; goes live on merge)

In one change:

-   `values.yaml`: point the persistence entry at the new claim (`existingClaim: <app>-data`, drop `storageClass`/`size`) and **remove the node pin** that only existed because of local-path (`defaultPodOptions.nodeSelector`). The chart then stops rendering the old PVC.
-   `kubernetes/apps/app-cluster/storage/app-protect/values.yaml`: set `claim: <app>-data` and replace `node:` with `selector:` using the pod labels `app.kubernetes.io/instance: <app>` and `app.kubernetes.io/controller: <app>`.
-   Update the app's README and architecture doc, and the storage class in `docs/cluster/app-catalog.md`.

On merge Argo rolls the Deployment (`Recreate`: a short outage), then prunes the old PVC. The old PV stays as `Released` (`Retain`).

### 4. Verify

```sh
kubectl -n <ns> get pods -o wide                            # Running, on any node
kubectl -n <ns> get pvc                                     # <app>-data Bound; the old claim is gone
kubectl -n longhorn-system get volumes.longhorn.io          # attached, healthy, 3 replicas on 3 nodes
kubectl -n <ns> create job --from=cronjob/protect-<app> <app>-check
task backups:run CLUSTER=app-cluster PLAN=app-<app>         # a new snapshot with current data
```

Then prove the point of the migration: drain the node the app runs on (`kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`), watch the pod start on another node with the same data, and run the protect job again (it must land on the app's new node). Uncordon afterwards.

### 5. Soak and clean up

After several days of normal running: `kubectl get pv | grep Released` shows the old volume. Keep it as long as you want the rollback path. To remove it:

1.  `kubectl delete pv <old-pv>`. This does **not** delete the data: local-path volumes are `Retain`, so the files stay on the node in `/var/mnt/local-path-provisioner/<pv>_<ns>_<claim>`.
2.  Remove that exact directory with a short-lived pod on the node (`nodeName: <node>`, a `hostPath` volume of `/var/mnt/local-path-provisioner` with `type: Directory`, command `rm -rf /h/<pv>_<ns>_<claim>`), then delete the pod. Use the exact directory name; never a wildcard. (Verified on scratch volumes on 2026-11-09.)

Never leave a retained PV `Available` (claimRef cleared) without a claim being created for it in the same breath: any new claim of the same class and a size that fits will bind it.

## Rollback

-   **Before step 3 merges:** delete the empty `<app>-data` PVC (and its leftover `Retain` PV and Longhorn volume). Nothing else changed.
-   **After step 3:** follow the order below. **Do not simply revert and wait.** Argo CD auto-syncs with self-heal (and the `apps` parent does too), so the revert recreates the old claim and the app at the same moment. The old PV is still `Released`, and a `Released` volume is never matched by a new claim: the local-path provisioner creates a **new, empty volume** and the app starts with an empty database. This was reproduced on 2026-11-09 with a scratch volume (the app found no data), and creating the correct claim afterwards fails because the claim already exists with a different volume.

### Rollback after step 3 (recommended order: claim the old volume first, then revert)

1.  Find the old volume. It is `Released`, its `claimRef` still names the old claim, and it still holds the data:
    ```sh
    kubectl get pv | grep '<ns>/<old-claim>'
    ```
2.  Immediately before you merge the revert, free it and claim it under the **old claim name and old spec** in one go. The claim binds at once, with no pod needed (verified 2026-11-09):
    ```sh
    kubectl patch pv <old-pv> -p '{"spec":{"claimRef":null}}'
    kubectl -n <ns> apply -f - <<EOF
    apiVersion: v1
    kind: PersistentVolumeClaim
    metadata: {name: <old-claim>}
    spec:
      accessModes: [ReadWriteOnce]
      storageClassName: local-path
      volumeName: <old-pv>
      resources: {requests: {storage: <old-size>}}
    EOF
    kubectl -n <ns> get pvc <old-claim>   # Bound to <old-pv>
    ```
3.  Decide about newer data. The old volume holds the data as of the cutover; anything the app wrote on Longhorn since then exists only on the Longhorn volume and in the Backrest exports taken after the cutover. If that matters, restore it into the old claim before the revert (for example with a one-off Job that mounts `<old-claim>`, see [Backrest operations](backrest.md)); for freqtrade (a dry-run bot) the loss is acceptable.
4.  Merge the revert. Argo applies the reverted Deployment and the chart's claim, which has the same name and spec as the one you created. Check that the Application is `Synced` and `Healthy`, the claim is still `Bound` to `<old-pv>`, and the app shows its data. (The Kubernetes side of this sequence was tested; Argo adopting the pre-created claim has not been, so check it.)

### If the revert was already merged and the app started on an empty volume

Stop it from writing further, then bring the old data back without creating a claim that conflicts with the one Argo made:

1.  Pause reconciliation, parent first (the same procedure as [Rollback Phase 6/7](../cluster/installation.md)): `argocd app set apps --sync-policy none`, then `argocd app set <app> --sync-policy none`. Scale the app to zero.
2.  Free the old PV and claim it under a **different** name (`<app>-restore`, same spec with `volumeName: <old-pv>`), then copy the files into the live claim with a one-off Job that mounts both, or restore from Backrest into the live claim.
3.  Delete the temporary claim, scale the app up, and resume GitOps (`task sync-argo-bootstrap`, `task reconcile`).

## Backups and this change

-   **Backrest plans are unchanged.** They back up the export on the NAS (`/k8s-backup/app-cluster/exports/<app>/current`), never the volume. Only the export job's scheduling changes (`selector` instead of `node`).
-   **Do not add a Longhorn backup target.** Longhorn backups are crash-consistent volume copies in Longhorn's own format; Backrest's exports are application-consistent and restorable without Longhorn or a healthy cluster. Longhorn snapshots are useful for a quick rollback before an upgrade, but they are not a backup.
-   If the app is scaled to zero its export job stays `Pending` and the freshness check reports the stale export: set `protect: false` for an app that is intentionally off.

## Worked example: freqtrade

| Item            | Value                                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Namespace / app | `trading` / `freqtrade`                                                                                                        |
| Old claim       | `freqtrade`, `local-path`, 2 Gi, on `k8s-wrkr-01-gpu`                                                                          |
| New claim       | `freqtrade-data`, `longhorn`, 2 Gi                                                                                             |
| Runs as         | uid/gid `1000:1000` (`fsGroup: 1000`)                                                                                          |
| Data            | `tradesv3.dryrun.sqlite` (~94 KB); `data`, `logs`, `backtest_results`, `hyperopt_results`, `plot` are excluded and regenerated |
| Pod labels      | `app.kubernetes.io/instance: freqtrade`, `app.kubernetes.io/controller: freqtrade`                                             |

1.  Done 2026-11-09 (#537): `kubernetes/apps/app-cluster/trading/freqtrade/config/pvc-data.yaml`.
2.  Done 2026-11-09: `scripts/longhorn-migrate-copy.sh trading freqtrade freqtrade-data 1000 1000` (export captured 09:57 UTC; the table row counts of the copy matched the live database, files owned by `1000:1000`, write test as uid 1000 ok).
3.  Cutover PR (this change): in `values.yaml` replace the `persistence.config` block with `type: persistentVolumeClaim`, `existingClaim: freqtrade-data`, the same `globalMounts`, and delete `defaultPodOptions.nodeSelector`; in the `app-protect` values change the freqtrade entry to `claim: freqtrade-data` and `selector:` with the two labels instead of `node: k8s-wrkr-01-gpu`.
4.  Verify as above, with a node-failover test: cordon the node the pod runs on, delete only the pod, confirm it restarts on another node with its data, then uncordon.
5.  Old volume deleted on 2026-11-10 at the operator's explicit request, before the soak gate below was met ([#551](https://github.com/fabricesemti80/home-dc-kubernetes/issues/551)).

### Soak evidence

Read-only checks. The cutover pod started at 2026-11-09 11:19:51 UTC. The 10:10 UTC Backrest run on 2026-11-09 was the manual verification run, not a scheduled one.

| Check (2026-11-10, 08:18 UTC)                                             | Result                                                                                                                                                                                                                                                    |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Export `protect-freqtrade`, 01:40 UTC (first scheduled run after cutover) | Job `protect-freqtrade-29904580` `Complete` 01:40:00-01:40:05 on `k8s-wrkr-03` (the pod's node, so `selector` works). Init log `snapshot ok: 1 SQLite database(s) via backup API`                                                                         |
| Backrest `app-freqtrade`, 03:10 UTC (first scheduled run after cutover)   | `STATUS_SUCCESS`, snapshot `b47b5b961de7`, 2 files / 94,241 B processed, ~99.7 KB added. Same file count and bytes as every run 2026-11-05 to 2026-11-09 (all `STATUS_SUCCESS`)                                                                           |
| Pod                                                                       | `freqtrade-6d45644bd8-js7fz` `Running`, ready, 0 restarts, on `k8s-wrkr-03`                                                                                                                                                                               |
| Longhorn volume `pvc-bfa1224a-bd62-432f-a56e-d2e3bc5aec65`                | `attached` to `k8s-wrkr-03`, `healthy`, 3 replicas `running`, one on each worker. Last replica healthy since 2026-11-09 15:29 UTC, after `k8s-wrkr-01-gpu` came back `Ready` at 15:28. All three Longhorn nodes `Ready`/schedulable                       |
| Alertmanager (infra-cluster)                                              | 0 alerts, 0 active silences. `ALERTS` history (last 30 h): only `KubernetesPodCrashLooping` 2026-11-09 11:01-11:33 UTC in `kube-system`, `gpu-operator` and `longhorn-system` (`csi-provisioner`), during the node reboots. None in `trading`, none since |
| Old PV `pvc-1b6eb81e-faec-4c9d-a3e3-b5505965345b`                         | `Released`, `Retain`, claimRef `trading/freqtrade`, `local-path`, 2 Gi, node affinity `k8s-wrkr-01-gpu`. Directory present (`talosctl ls`, read-only) with `tradesv3.dryrun.sqlite` 94,208 B, last changed 2026-11-09 10:08:56 UTC                        |

Not verified: Slack (Alertmanager keeps no history, so the `ALERTS` series is the record), and a Backrest restore of a post-cutover snapshot.

### Deleting the old volume

**Done 2026-11-10, ahead of the gate.** The operator explicitly approved deleting the old volume after one night of soak (1/5) and without a post-cutover restore test. The PV `pvc-1b6eb81e-faec-4c9d-a3e3-b5505965345b` was deleted, and the helper pod removed exactly `/var/mnt/local-path-provisioner/pvc-1b6eb81e-faec-4c9d-a3e3-b5505965345b_trading_freqtrade` on `k8s-wrkr-01-gpu` (log `removed`; `kubectl get pv` no longer lists it). Pre-checks: PV `Released`/`Retain`, claimRef `trading/freqtrade`, and the Deployment mounted only `freqtrade-data` (Longhorn). **Rollback is now Backrest only:** post-cutover snapshot `b47b5b961de7` and the 2026-11-05 to 2026-11-09 snapshots of plan `app-freqtrade`. The local-path rollback in [Rollback after step 3](#rollback-after-step-3-recommended-order-claim-the-old-volume-first-then-revert) no longer applies.

The original gate, kept for the remaining app migrations (#552):

**Earliest date: 2026-11-14, after the 03:10 UTC Backrest run.** All of the following must hold, and the operator must approve the deletion explicitly:

-   [ ] Five consecutive scheduled export and Backrest runs since cutover (2026-11-10 to 2026-11-14) are `Complete`/`STATUS_SUCCESS` with about 94 KB processed. 2026-11-10: done (1/5).
-   [ ] No firing alert in `trading`, and none for the Longhorn volume, over the same period. Pod restarts unchanged unless explained.
-   [ ] Volume `healthy` with 3 running replicas on 3 nodes.
-   [ ] A post-cutover snapshot restored to the NAS (`task backups:restore CLUSTER=app-cluster PLAN=app-freqtrade SNAPSHOT=<id>`), and `PRAGMA integrity_check` is `ok` on the restored `tradesv3.dryrun.sqlite`.

Procedure (deletion removes the only rollback path in [Rollback after step 3](#rollback-after-step-3-recommended-order-claim-the-old-volume-first-then-revert)):

```sh
PV=pvc-1b6eb81e-faec-4c9d-a3e3-b5505965345b
DIR=pvc-1b6eb81e-faec-4c9d-a3e3-b5505965345b_trading_freqtrade
# 1. Re-check: must print "Released Retain trading/freqtrade"
kubectl get pv $PV -o jsonpath='{.status.phase} {.spec.persistentVolumeReclaimPolicy} {.spec.claimRef.namespace}/{.spec.claimRef.name}{"\n"}'
# 2. Delete the PV object (Retain: the files stay on the node)
kubectl delete pv $PV
# 3. Delete exactly that directory on k8s-wrkr-01-gpu, then the pod
kubectl -n local-path-storage apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata: {name: rm-freqtrade-old-pv}
spec:
  nodeName: k8s-wrkr-01-gpu
  restartPolicy: Never
  containers:
    - name: rm
      image: busybox
      command: [sh, -ec, 'test -d "/h/$DIR" && rm -rf "/h/$DIR" && ! test -e "/h/$DIR"']
      volumeMounts: [{name: h, mountPath: /h}]
  volumes: [{name: h, hostPath: {path: /var/mnt/local-path-provisioner, type: Directory}}]
EOF
kubectl -n local-path-storage wait --for=jsonpath='{.status.phase}'=Succeeded pod/rm-freqtrade-old-pv --timeout=120s
kubectl -n local-path-storage logs rm-freqtrade-old-pv; kubectl -n local-path-storage delete pod rm-freqtrade-old-pv
```

`$DIR` is expanded by the shell into the manifest (the heredoc is unquoted on purpose), so the pod sees the literal directory name. The pod runs in `local-path-storage` because that namespace is labelled `pod-security.kubernetes.io/enforce: privileged` (checked 2026-11-10). `default` has no label, so the Talos cluster-wide default (`baseline`) would reject a `hostPath` volume. Afterwards, `kubectl get pv | grep $PV` and `talosctl -n 10.0.40.95 ls /var/mnt/local-path-provisioner` must no longer show it. Tick the issue item and record the date here.

The tool was exercised on 2026-11-09 against a disposable Longhorn volume: fresh export, copy, `integrity_check=ok`, file ownership `1000:1000`, and a write test as uid 1000 with WAL mode. Its guards were checked against the production claim (refused: wrong storage class), a missing app, a missing PVC, a bad uid, and a populated target (refused: not empty).
