# Migrating an app from local-path to Longhorn

One app at a time. The aim is an app whose data is no longer tied to one worker: after the move it can be rescheduled to another node, and a node drain no longer takes the app down with it. Longhorn is **not** a backup (all three replicas live on the same host); Backrest stays the backup of record, see [Backups](#backups-and-this-change).

Pilot: **freqtrade** (a dry-run trading bot with a ~100 KB SQLite database), worked example at the end.

## Ground rules

-   **Argo CD auto-syncs with prune and self-heal.** Anything merged to `main` goes live within minutes. The order below exists because of that: the empty target volume is merged first, the data is copied while the old app keeps running, and only then does a second change switch the app over.
-   **Copy from the Backrest export, not from the live volume.** The `app-protect` job already captures SQLite through the online backup API, so the copy is consistent and the running app is not touched. The only data at risk is what the app writes between that export and the cutover, so do the copy and the cutover back to back.
-   **The old volume is kept.** local-path volumes are `Retain`: when Argo prunes the old PVC the data stays on the node as a `Released` PV. Do not delete it until the app has run on Longhorn for several days and a Backrest restore of the new volume's export has been checked.
-   **Do not migrate caches.** `jellyfin-cache`, `immich-model-cache` and the vmagent queue are regenerable and gain nothing from three replicas. Migrate configuration and database volumes.
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

After several days of normal running: `kubectl get pv | grep Released` shows the old volume. Delete the PV object once you no longer want the rollback path; the files remain on the node under `/var/mnt/local-path-provisioner/` until removed, which is harmless (the volume is small) but note it.

## Rollback

-   **Before step 3 merges:** delete the empty `<app>-data` PVC (and its leftover `Retain` PV and Longhorn volume). Nothing else changed.
-   **After step 3:** revert the change. Argo recreates a claim from the old values; to get the old data back instead of an empty volume, clear the `claimRef` on the old `Released` PV (`kubectl patch pv <pv> -p '{"spec":{"claimRef":null}}'`) and create the claim with `volumeName: <pv>`, or restore the app's data from Backrest. The data written on Longhorn since the cutover is not in the old volume; it is in the Backrest exports taken after the cutover.

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

1.  PR: `kubernetes/apps/app-cluster/trading/freqtrade/config/pvc-data.yaml` (this change).
2.  `scripts/longhorn-migrate-copy.sh trading freqtrade freqtrade-data 1000 1000`.
3.  Cutover PR: in `values.yaml` replace the `persistence.config` block with `type: persistentVolumeClaim`, `existingClaim: freqtrade-data`, the same `globalMounts`, and delete `defaultPodOptions.nodeSelector`; in the `app-protect` values change the freqtrade entry to `claim: freqtrade-data` and `selector:` with the two labels instead of `node: k8s-wrkr-01-gpu`.
4.  Verify as above, including the drain test.

The tool was exercised on 2026-11-09 against a disposable Longhorn volume: fresh export, copy, `integrity_check=ok`, file ownership `1000:1000`, and a write test as uid 1000 with WAL mode. Its guards were checked against the production claim (refused: wrong storage class), a missing app, a missing PVC, a bad uid, and a populated target (refused: not empty).
