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

The tool was exercised on 2026-11-09 against a disposable Longhorn volume: fresh export, copy, `integrity_check=ok`, file ownership `1000:1000`, and a write test as uid 1000 with WAL mode. Its guards were checked against the production claim (refused: wrong storage class), a missing app, a missing PVC, a bad uid, and a populated target (refused: not empty).
