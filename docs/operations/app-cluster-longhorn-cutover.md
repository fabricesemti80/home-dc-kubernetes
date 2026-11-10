# App-cluster Longhorn cutover: all local-path claims

**Do not merge or sync the cutover PR until every target below has been copied and verified.** Argo auto-sync can start an app on an empty target as soon as the PR is merged. This is a coordinated maintenance outage, not an online migration. If any step fails, keep reconciliation paused, leave the old PVCs and PVs intact, and stop. The infra cluster is out of scope and remains on its own storage.

## Assumptions and gates

-   The app-cluster context is selected explicitly (`export KUBECONFIG="$PWD/kubeconfig"`); verify `kubectl config current-context` and `kubectl get nodes` before any command. Use a checkout of the PR branch, not the old `main`.
-   All three Longhorn nodes are Ready and Schedulable; capacity and actual free space on every disk can support the targets with three replicas. Check `kubectl -n longhorn-system get nodes.longhorn.io -o yaml` and the Longhorn UI. Longhorn remains a single physical host failure domain, not a backup.
-   Confirm a recent, successful independent Backrest snapshot for each protected application and native Immich PostgreSQL export; test representative restores, including Backrest configuration and credentials, **before** stopping Backrest. Moving Backrest's state to Longhorn makes Longhorn a dependency for managing backups; preserve a separate, tested way to restore that state.
-   Reserve a maintenance window for **all** apps below: the PR switches every listed claim together. Stop clients/writers, native database export jobs, app-protect jobs and the Jellyfin cleanup job. Stop the relevant controllers and leave them stopped from the copy until the cutover. All copies must pass; a copy taken while an app continues to write is not a final copy.
-   Before cutover, check each source PV's reclaim policy is `Retain`. Annotate each existing source PVC with `argocd.argoproj.io/sync-options: Prune=false,Delete=false`; retain the old claim and its PV for rollback. Never delete or clear a PV's claimRef as part of migration.
-   Note current replica counts and Argo auto-sync settings, and record each old claim's PV and storage class before changing anything. Do not assume all counts are one. The vmagent is operator-managed and must also be paused at the VMAgent CR.

## Claim mapping

Every target is a new, explicitly named Longhorn `ReadWriteOnce` PVC, the same size as the source. The two caches and vmagent queue are copied too. The copy helper copies the **root** of each claim, including vmagent's queue root.

| Namespace  | Source                                                                 | Target                                                                          |
| ---------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| media      | immich-model-cache                                                     | immich-model-cache-longhorn                                                     |
| media      | immich-postgres-data                                                   | immich-postgres-data-longhorn                                                   |
| media      | immich-redis-data                                                      | immich-redis-data-longhorn                                                      |
| media      | jellyfin-cache                                                         | jellyfin-cache-longhorn                                                         |
| media      | jellyfin-config                                                        | jellyfin-config-longhorn                                                        |
| media      | jellyseerr                                                             | jellyseerr-longhorn                                                             |
| media      | prowlarr                                                               | prowlarr-longhorn                                                               |
| media      | qbittorrent                                                            | qbittorrent-longhorn                                                            |
| media      | radarr                                                                 | radarr-longhorn                                                                 |
| media      | recyclarr                                                              | recyclarr-longhorn                                                              |
| media      | sabnzbd                                                                | sabnzbd-longhorn                                                                |
| media      | sonarr                                                                 | sonarr-longhorn                                                                 |
| backups    | backrest                                                               | backrest-longhorn                                                               |
| monitoring | persistent-queue-data-vmagent-vmagent-app-victoria-metrics-k8s-stack-0 | persistent-queue-data-vmagent-vmagent-app-victoria-metrics-k8s-stack-0-longhorn |

## Prepare, then quiesce

1. In this PR checkout, create only the target PVC files, not their kustomizations or the workload manifests:

    ```sh
    for f in kubernetes/apps/app-cluster/media/*/config/pvc-*-longhorn.yaml \
      kubernetes/apps/app-cluster/storage/backrest/config/pvc-state.yaml \
      kubernetes/apps/app-cluster/monitoring/vmagent/config/pvc-queue.yaml; do
      kubectl apply -f "$f"
    done
    kubectl get pvc -A
    kubectl -n longhorn-system get volumes.longhorn.io
    ```

    Confirm all 14 targets are `Bound`, `longhorn` and healthy, and each source PV is `Retain`. A target must be empty and unused. The manifests use `Prune=false,Delete=false`; remove manually created targets only if verified unused, following Longhorn's Retain cleanup procedure.

2. Pause auto-sync and self-heal on the `apps` parent **first**, then on `app-protect`, `backrest-app`, `vmagent-app`, `immich`, `jellyfin`, `jellyseerr`, `prowlarr`, `qbittorrent`, `radarr`, `recyclarr`, `sabnzbd`, and `sonarr` using `argocd app set <name> --sync-policy none`. Confirm auto-sync is disabled for each before continuing. Save their original settings for restoration. Do not pause or alter infra-cluster Applications.
3. Suspend the `protect-*` CronJobs in `media`, `jellyfin-transcode-cleanup` in `media`, and `backrest-export-immich-db` in `backups`. Wait for any already-running Jobs to finish and verify no active pod mounts a source or target claim after step 4. Do not delete backup jobs or assume suspending a CronJob stops an existing Job.
4. Pause the VictoriaMetrics operator's VMAgent reconciliation (`kubectl -n monitoring patch vmagent vmagent-app-victoria-metrics-k8s-stack --type=merge -p '{"spec":{"paused":true}}'`). Scale its StatefulSet `vmagent-vmagent-app-victoria-metrics-k8s-stack` to zero and verify it stays at zero. Scale the media Deployments `immich`, `immich-machine-learning`, `immich-redis`, `jellyfin`, `jellyseerr`, `prowlarr`, `qbittorrent`, `radarr`, `recyclarr`, `sabnzbd`, `sonarr`, the `immich-database` StatefulSet, and `backups/backrest` Deployment to zero. Stop Immich's application before its PostgreSQL and Redis. Wait for all pods using these claims to terminate. This causes a media, backup and metrics-queue outage; no writes can be accepted during the copy.
5. Record and annotate every source PVC before proceeding. Example:

    ```sh
    kubectl -n media get pvc sonarr -o jsonpath='{.spec.volumeName}{"\n"}'
    kubectl get pv <pv-name> -o jsonpath='{.spec.persistentVolumeReclaimPolicy}{"\n"}' # Retain
    kubectl -n media annotate pvc sonarr 'argocd.argoproj.io/sync-options=Prune=false,Delete=false' --overwrite
    ```

    Repeat for **every** source, including the cache, queue and Backrest claims. Verify that the annotation is present on the live claims. Do not continue if the GitOps controller might prune one.

## Offline copy and validation

For each row in the table, run:

```sh
scripts/longhorn-copy-offline.sh <namespace> <source> <target>
```

The helper refuses non-Bound or wrong-class claims, a source or target used by an active pod, and a populated target. A temporary Job mounts the source read-only and the target read-write; `cp -a` preserves ownership and permissions, then the helper compares file contents, names, types, modes, owners and symlink targets. Inspect failed Job events and logs; a failed target may contain partial data and must **not** be mounted by an app. The pod check is not a lock: keep all controllers and jobs paused so nothing can start during or after the copy. Do not bypass these checks. Record the result for all 14 claims.

For PostgreSQL, require a clean prior shutdown and matching copied files; after cutover verify the database starts against the existing data directory and that expected database tables/rows are present, not a newly initialized database. Check SQLite databases and app-specific settings for the other workloads. Confirm Longhorn volume health and inspect target ownership. Keep all writers stopped; if any source starts or changes, the final copy is no longer valid.

## Cutover and verify

1. Merge the reviewed PR only after all 14 copies and checks pass. Refresh Argo to the merged revision while auto-sync remains disabled. The vmagent change moves its operator-managed queue from a StatefulSet to a single-replica Deployment because StatefulSet `volumeClaimTemplates` are immutable. Its old PVC remains retained. The Jellyfin GPU node pin remains and its cleanup job uses the new cache claim. Media node pins are retained in this cutover.
2. Sync `app-protect`, then each media Application and `backrest-app`; for vmagent sync `vmagent-app`, unpause the VMAgent CR, and verify the operator removes the old StatefulSet and creates a Deployment with the new PVC. Do not force-delete pods that may still have writers. Restore original controller replicas if sync has not already restored them. Resume CronJobs and Argo auto-sync/self-heal using the recorded original settings; restore the `apps` parent last. Check for failed syncs or Pending pods before continuing.
3. Verify each workload's pod mounts the intended `-longhorn` PVC, all targets are Bound and Longhorn volumes healthy with three replicas. Confirm Immich's existing data, Jellyfin transcoding and the media services' existing settings and data. Check vmagent remote-write health and backlog; check Backrest plans, repository access and a new protected export and snapshot, then perform a restore. Verify app-protect Jobs follow their workloads and the Jellyfin cleanup Job can mount its cache.
4. Keep the old retained claims, PVs and data through a multi-day soak and successful restores. Do not delete them without explicit approval. Longhorn's automatic node-down pod deletion remains disabled: unplanned failure recovery requires fencing and operator intervention.

## Rollback

Stop the affected workload and backup jobs, pause parent and child reconciliation, and stop writes. The old PVCs are intentionally retained under their original names. If any source claim was pruned, follow [the retained-PV recovery sequence](local-path-to-longhorn.md#rollback-after-step-3-recommended-order-claim-the-old-volume-first-then-revert) **before** a revert; do not let Argo create an empty claim. Data written after cutover lives on Longhorn: copy it back to the old claim while stopped and verify, or restore a verified post-cutover backup. A raw reverse copy requires a separate vetted procedure; the offline helper intentionally only copies local-path to Longhorn and refuses to overwrite populated targets. For vmagent, revert to the StatefulSet only after stopping the Deployment and verifying the original queue PVC is still bound. Revert the Git change, restore the old claims and controller settings, then resume jobs and Argo. Keep the new retained Longhorn volumes until recovery is verified.
