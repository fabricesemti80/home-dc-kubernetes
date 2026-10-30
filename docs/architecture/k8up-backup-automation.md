# Operator-driven application backups

Status: **operator installed; application backup policies not enabled**. The [operator runbook](../operations/k8up.md) covers the GitOps Applications and reproducible bootstrap/status/verification Tasks. The NAS target and opt-in-only K8up controllers are running on both clusters. Source capture, restore adapters, policy schedules and the data-path acceptance pilot below remain implementation gates; existing target smoke tests are not application backups.

## Decision

Adopt **K8up + Restic**, subject to the acceptance pilot below. Install one operator independently in each cluster through Argo, using the existing NAS NFS export as a filesystem repository backend. K8up owns discovery, backup scheduling, capture Jobs, repository checks, pruning and Snapshot/Restore resources. Git/Argo owns deployment definitions; secret-manager bootstrap and Talos/etcd recovery remain separate.

The user-facing contract is: **enroll a supported app once in Git, then receive alerts only when protection needs attention**. Ordinary enrollment should require metadata and a known capture profile, not another handwritten CronJob. A genuinely new database/app format still needs a tested capture/restore adapter once; a label cannot infer how to make an arbitrary running database consistent.

Installed baseline: upstream Helm chart **4.10.1** at commit `ff230b43ab8d73f3666219d748dea55bee036fdf`, operator/runner **v2.16.1** pinned to image index digest `sha256:f59bfa37c51511d5ad67e53816fb55c62d0e6411890e59bb6b965923129f30b5`, API `k8up.io/v1`. Chart and image versions are different numbers. Controller rollout/metrics and protected CRD lifecycle were verified on both clusters; backup/restore compatibility is still subject to the data-path pilot. Repeat that pilot on upgrades affecting selection, streaming or restore behavior. The upstream operator chart owns controllers/RBAC; an earlier-wave Kustomize source owns the nine protected CRDs.

No S3 gateway is required: K8up's `backend.local.mountPath` can reference an NFS-mounted directory. This retains recovery access with ordinary Restic from a trusted host if Kubernetes/K8up is unavailable. Do not replace the existing target or migrate its retained volumes. Velero is not selected: its filesystem backup requires object storage and excludes hostPath volumes; its cluster-object recovery is less central when Argo already owns desired state.

## Responsibility boundaries

| Component                   | Responsibility                                                                                          | Not a guarantee                                                                      |
| --------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Argo CD                     | K8up installation, pinned CRDs, namespace policies, enrollment metadata, adapters and Secret references | Does not restore application data or runtime secrets from Git                        |
| K8up                        | Label/annotation discovery; capture, check, prune and restore execution; snapshot catalog               | Does not automatically quiesce arbitrary apps or import streamed SQL into a database |
| Restic / NAS                | Encrypted, deduplicated repositories and data retrieval                                                 | Same-NAS copies do not survive loss of the NAS; writable NFS clients can delete data |
| App capture adapters        | Native exports or approved cold-copy preparation; artifact validation and source timestamps             | A successful tar/HTTP request alone is not application-consistency evidence          |
| Restore Tasks               | Resolve an app/recovery point, restore to fresh storage, import DB/native exports and validate          | No automatic overwrite or production cutover                                         |
| Monitoring / restore drills | Missing-source, stale-backup, failed Job, capacity and failed-recovery alerts                           | Green operator status is not proof that every expected app was captured              |

## Enrollment: small metadata, explicit policy

Configure `k8up.skipWithoutAnnotation: true` globally in **both** operators (`BACKUP_SKIP_WITHOUT_ANNOTATION=true`). Default K8up behavior is broader; it must not silently enroll shared media, backup repositories, caches or raw databases.

Use native K8up annotations plus ordinary labels selected by K8up policies:

-   `backup.krapulax.dev/app`: stable app identity, such as `sonarr` or `immich-db`.
-   `backup.krapulax.dev/policy`: one of the profile names below, selected through `labelSelectors`.
-   `backup.krapulax.dev/strategy`: `files`, `native-export`, `postgres-dump`, `cold-copy` or `photo-set`. This is our declarative validation/restore contract, **not a built-in K8up field**.
-   `k8up.io/backup: "true"`: opt a compatible source PVC into filesystem capture. It is an annotation, not a label.
-   `k8up.io/backup: "false"`: explicitly exclude raw PGDATA, caches, shared media/download claims, repository target claims, exported-state sources collected through an adapter, and disposable restore targets.

A safe-to-copy configuration PVC would carry the following **metadata fragment**, not a new PVC definition:

```yaml
metadata:
    labels:
        backup.krapulax.dev/app: example-config
        backup.krapulax.dev/policy: daily-files
        backup.krapulax.dev/strategy: files
    annotations:
        k8up.io/backup: "true"
```

For a one-app operation, combine app and policy in **one** `matchLabels` selector
(AND). Multiple `labelSelectors` entries are OR alternatives in K8up; adding an
app selector beside a broad policy selector would still select the whole policy.

`files` means immutable or otherwise already application-consistent files. It is **not** the default for live Sonarr/Jellyseerr/Jellyfin databases. For an export, label the `PreBackupPod` or explicitly selected command-bearing pod instead; keep its raw data PVC excluded. For a cold copy, enrollment selects the coordinated capture adapter, not a live-directory scan.

Put metadata on the actual PVC, Pod template or `PreBackupPod`, not solely on the Argo Application. StatefulSet `volumeClaimTemplates` and chart-generated PVC metadata need their supported values/rendering path checked; never assume Deployment labels propagate to claims. New namespaces need an NFS target claim, repository Secret and matching policies once; a label does not create these prerequisites.

Add repository validation with implementation: reject unknown profiles/strategies, missing app identities, raw database/cache/backup-target enrollment, and duplicate capture ownership. An enrollment audit must also flag stateful sources without any declared protection or explicit exclusion. Git labels are selectors, not an authorization boundary.

## Profiles, repositories and automatic policy

Policies are shared by namespace and protection class; adding an app to an established class does not add a bespoke CronJob. The app's capture adapter and restore method remain with its configuration. Initial namespace coverage is app-cluster `media` and infra-cluster `ai`, `network`, `monitoring`.

| Profile        | Intended capture                                                                                          | Proposed cadence                                       | Retention after successful restore gate                   |
| -------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------- |
| `critical-6h`  | Immich/LiteLLM logical DB exports; separate exact-instance Technitium exports                             | Every 6h, staggered                                    | 24 hourly representatives, 14 daily, 8 weekly, 12 monthly |
| `daily-files`  | Files already known to be consistent without quiescing                                                    | Daily                                                  | 14 daily, 8 weekly, 6 monthly                             |
| `daily-export` | Verified native Servarr/Jellyfin archives plus required settings coverage                                 | Daily                                                  | 14 daily, 8 weekly, 6 monthly                             |
| `daily-cold`   | Jellyseerr, SABnzbd, qBittorrent, Pulse, matched Kuma/AutoKuma state; other apps requiring a stopped copy | Daily only after quiesce/watchdog acceptance           | 14 daily, 8 weekly, 6 monthly                             |
| `photos-daily` | Matched Immich DB and originals, including external-library data                                          | Daily only after set-consistency/throughput acceptance | 14 daily, 8 weekly, 12 monthly, capacity-reviewed         |

Recyclarr may use `daily-files` only after its scheduling/sync exclusion is proven; otherwise use a coordinated adapter. Retired Kestra and released LiteLLM volumes are one-off archives, not default policy members. Valkey/model/Jellyfin caches and download payloads remain excluded. The detailed source inventory and per-app restore acceptance stay in [the inventory plan](../cluster/database-backups.md), rather than being duplicated here.

Repository layout: `/k8s-backup/<cluster>/<namespace>/<profile>`, for example `app-cluster/media/critical-6h`. This **supersedes the earlier per-app repository recommendation** for routine policy members: a shared class repository gives new apps existing schedules/maintenance/key references. Separate repositories are still allowed when an app needs a distinct trust or retention boundary, but that is an explicit policy addition. A shared namespace/profile key grants access to that repository's applications; different directories on the same writable export still do not enforce isolation.

Create one unique retained target PV/PVC per source namespace, with `k8up.io/backup: "false"`; mount it as a repository volume, not as an automatically discovered source. Existing `backups/k8s-backup` claims cannot be mounted from `media`/`ai`/`network`/`monitoring`. `backend.local.mountPath` identifies the repository directory but **does not mount NFS by itself**. The same target mount, Secret and path must be present in backup, check, prune, snapshot-sync and restore execution. Do not configure a single global nodeSelector for every runner.

Snapshot identities must remain stable across ephemeral pods. Verify the selected release's host/path naming, keep application identity/source paths in the recovery catalog, and test retention groups. K8up snapshots are `snapshots.k8up.io`, not CSI VolumeSnapshots. Do not treat a Snapshot CR label or the newest repository entry as sufficient evidence that a particular app was captured.

K8up can report success with **“nothing to backup”**. Protection therefore requires expected app/source coverage and a newly completed, valid artifact per expected source, not just a successful Backup CR or repository timestamp. For exports, validate the producer exit status, archive format, expected content and source capture time; never publish an old ZIP or stderr as a fresh backup.

### Reference resources for the pilot

These complete K8up reference objects are **documentation examples, not deployed manifests**. They assume a `media/k8s-backup-repository` target claim and `media/k8up-daily-export` Secret with key `password`, both to be provisioned in the implementation. They collect only already-configured `daily-export` sources. No prune stanza is included: destructive retention stays disabled until the restore gate passes. Values are proposed, not measured resource guarantees.

```yaml
apiVersion: k8up.io/v1
kind: PodConfig
metadata:
    name: nas-repository
    namespace: media
spec:
    template:
        spec:
            containers:
                # PodConfig overlay: K8up supplies the runner image and command.
                - name: k8up
            volumes:
                - name: repository
                  persistentVolumeClaim:
                      claimName: k8s-backup-repository
---
apiVersion: k8up.io/v1
kind: Schedule
metadata:
    name: daily-export
    namespace: media
spec:
    podConfigRef:
        name: nas-repository
    backend:
        local:
            mountPath: /repository/app-cluster/media/daily-export
        repoPasswordSecretRef:
            name: k8up-daily-export
            key: password
        volumeMounts:
            - name: repository
              mountPath: /repository
    failedJobsHistoryLimit: 3
    successfulJobsHistoryLimit: 2
    resourceRequirementsTemplate:
        requests:
            cpu: 50m
            memory: 128Mi
        limits:
            cpu: 500m
            memory: 1Gi
    backup:
        schedule: "45 2 * * *"
        activeDeadlineSeconds: 3600
        labelSelectors:
            - matchLabels:
                  backup.krapulax.dev/policy: daily-export
    check:
        schedule: "0 5 * * 6"
        activeDeadlineSeconds: 3600
```

Set the operator timezone to UTC; do not infer timezone from these cron strings. The PodConfig adds only the repository volume, leaving source-node placement to K8up. Rendered Jobs must prove that this volume and backend mount survive every operation's template merge, including the export-only runner that mounts no source PVC. Namespace policies for infra use their own cluster prefix and Secrets, not these app-cluster values.

## Capture adapters and real storage constraints

### Worker-local PVCs

The inspected v2.16.1 executor pins mounted RWO claims to their consuming pod's node, derives placement from PV node affinity for unmounted RWO claims in classic scheduling, supports `k8up.io/hostname`, and groups compatible PVC work by node. Keep classic scheduling initially. A PodConfig must not override node placement or allow an unbound claim to be accidentally provisioned on another worker.

This is source evidence, **not a live proof on Talos/local-path**. The pilot must simultaneously capture two synthetic RWO PVCs on different app workers, restore them to new claims, and compare contents. Include a stopped/unmounted source and an unavailable node: that source must be flagged missing/failed rather than disappearing from the coverage report. Do not back up real PGDATA simply to test placement.

### Database and native-export adapters

Prefer labeled `PreBackupPod` templates with dedicated, namespace-scoped DB/API credentials. K8up starts the helper, executes its capture command and streams the result to Restic, then cleans up the helper. Use matching PG14/PG17 clients and archive formats from the inventory plan; passwords come from Secrets/environment, never command literals. Recreate required DB roles from the recovery specification/secret manager before import; do not depend on restoring plaintext role passwords from Git.

K8up also supports `k8up.io/backupcommand` on an existing Pod, but it requires namespace pod-exec privileges and ties tooling to the app image. Use it only when justified and tested. The pinned source filters PVCs/command pods by policy selectors and includes PreBackupPods belonging to the current Backup UID. Selector isolation between simultaneous policies remains a required pilot test. Do not assume labels on a `PreBackupPod` automatically appear on its generated pod.

The pinned executor role includes `pods/exec` in namespaces where it is bound. The manager can create Deployments, Jobs, service accounts and role bindings; it is a trusted, privileged backup component even without cluster-admin. Its ability to create workloads can expose namespace Secrets indirectly. Git/RBAC admission controls must restrict who can define capture commands, PodConfigs and helper images. Policy labels are not a sandbox. Use independent operators/credentials in the two clusters, not an app-cluster operator reaching into infra through a kubeconfig.

Native exports must fail if the producer fails or produces an invalid/incomplete archive. A negative test must demonstrate that a partially produced stream does not count as a valid recovery point. Any partial snapshot left in Restic after a producer failure stays unaccepted and excluded from the recovery catalog until separately verified. Prefer artifact validation before streaming where format validation requires reading the whole file, with private bounded staging and cleanup.

### HostPath and cold-copy state

K8up does not discover arbitrary host directories from a PVC annotation. Keep Pulse `/var/pulse/data`, Kuma `/var/uptime-kuma/data` and AutoKuma `/var/autokuma/data` in coverage through explicit per-app adapters pinned to `infra-wk-01`, mounting only those paths. Do not introduce a privileged all-host filesystem scraper. Conversion to static retained local PV/PVC bindings at the same paths is a separate reviewed option, not an incidental storage migration or authorization to move data.

A `PreBackupPod` is **not** an automatic main-application shutdown hook. A shared cold-copy adapter must coordinate graceful stop, capture and restart. Before unattended use it needs a durable per-app maintenance lease recording original replica/reconcile settings and a watchdog outside that capture Job. The watchdog restores availability after timeout, cancellation or Job/node loss and preserves capture failure status. If the source node is unavailable, report that recovery is blocked; do not claim to repair hardware or restore node-local state automatically.

Argo coordination must be scoped to the exact child Application/controller; do not disable parent self-heal/prune globally or permanently ignore all replica drift. Pilot a temporary reconciliation pause, prove the app-of-apps does not undo it, then restore its original state. If that cannot be made reliable for a workload, use a proven online export or keep cold capture operator-triggered; **do not enable `daily-cold` and call the app protected**. Kuma/AutoKuma are a matched set, with AutoKuma stopped first and started last. Embedded MariaDB must fully stop before its datadir is copied. The proposed watchdog is an implementation requirement, not an existing K8up feature.

Immich's `photos-daily` adapter follows the inventory plan: DB plus original files with a shared set identifier, coordinated server/external-writer activity or a validated source-snapshot procedure. A DB-only six-hour dump is not a complete photo recovery point. The whole `/media` share must not be labeled for backup to capture only its Immich subtree.

## Low-maintenance operations and alerts

K8up Schedules, not per-app CronJobs, own routine capture/check/prune. A small shared restore/maintenance adapter is acceptable where K8up does not implement DB import, cold-copy coordination or application validation; do not build a second scheduling operator. Initial scheduling is opt-in, with no production policy enabled until its pilot/restore acceptance passes.

-   Retain the inventory plan's policy counts, stable Restic identities and upgrade-checkpoint rules. Set explicit keep-tag behavior for checkpoints and verify it against the pinned K8up/Restic implementation before enabling prune.
-   Backup/check/prune/restore concurrency must be safe **per repository**, not just per Job kind. Separate K8up concurrency limits do not by themselves serialize different operations. Stagger windows, honor Restic locks and fail/requeue visibly on contention; never automatically break locks. Prove two racing operations cannot prune active/unvalidated recovery data. Start with manual prune dry-runs and enable scheduled pruning only after this test and a real restore.
-   Alert on expected-source absence, failed/missed Jobs, invalid/empty export artifacts, new opt-ins without policy/credentials, critical capture age over 8h, daily capture age over 30h, restore/check failure and target free space below 20%. Zero matched sources is not a green backup.
-   Wire metrics/status/webhooks to monitoring that actually exists; do not install ServiceMonitor/PrometheusRule objects assuming their CRDs or a working notification receiver exist. Provide an out-of-cluster dead-man check for each cluster's backup heartbeat so a failed cluster cannot silence its own alarm. Reuse the current monitoring stack until VictoriaMetrics is implemented and proven.
-   Automate repository checks and disposable restore drills. Rotate real application drills monthly/quarterly as specified in the inventory; protect the drill from outbound downloads/notifications/DNS updates. Normal success is quiet; failure requires an actionable message naming cluster, app/source, last valid recovery point and failed phase.

“Set up and forget” means **no routine manual backup work**, not untested restores or no alerts. No app is marked protected until capture, restore, alert delivery and expected-source reporting all pass.

## Restore interface: one workflow, explicit recovery point

Proposed Taskfile commands below are a **future interface**, not commands available in this documentation PR. Existing `backups:status` and `backups:smoke` remain unchanged.

| Task                                                  | Behavior                                                                                                                                                                                |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backups:list CLUSTER=… APP=…`                        | Resolve app/policy repository from Git metadata; list valid snapshots with full ID, source path, capture time, images/schema, recovery-set completeness and last restore validation     |
| `backups:run CLUSTER=… APP=…`                         | Create a uniquely named one-off K8up Backup narrowed to that app; do not accidentally run every app in its policy; report per-source acceptance                                         |
| `backups:restore-plan CLUSTER=… APP=… SNAPSHOT=…`     | Read-only plan: resolve an exact snapshot and required paths, check keys/versions/capacity, show new claim/node or DB target, identify disabled outbound integrations and prerequisites |
| `backups:restore CLUSTER=… APP=… SNAPSHOT=… TARGET=…` | Create a fresh isolated recovery target, restore/import and run app-specific checks; fail if the target already holds production state; preserve failed drill artifacts for inspection  |
| `backups:promote CLUSTER=… APP=… RESTORE=…`           | Separate explicitly confirmed production cutover through reviewed GitOps changes; keep old PVCs/keys and record rollback                                                                |

Use a full immutable snapshot ID, app identity and required source paths. Never silently choose `latest`, accept a different app's snapshot in a shared repository, or use `restoreTimeFilter` as an exact selection: upstream documents fallback to latest when that filter has no match. K8up's PVC Restore does not automatically verify that the selected snapshot contains the intended source; set `spec.paths` and independently inspect its catalog/content. Verify the restored directory layout before mounting it into an app. New restore claims are excluded from automatic backups until accepted/cut over.

Two restore paths sit behind the same interface:

1. **Filesystem snapshots:** a K8up Restore to a fresh retained claim, with explicit snapshot ID and source-path filters, repository mount/credentials and correct node/UID/GID; validate application state with matching images.
2. **Streamed exports (`backupcommand`/`PreBackupPod`):** upstream's ordinary PVC Restore does **not** restore stdin snapshots. The restore adapter uses `restic dump` for the exact snapshot/file, validates the artifact, then invokes the matching PG/native import into a fresh isolated target. File-based successful extraction alone is not DB restore success. Handle required roles/extensions and prevent Argo/application initialization before import.

A complete cluster loss uses the same repository with an independently escrowed key from a trusted recovery host: bootstrap storage/secrets/Argo/K8up from Git, or use Restic directly and import data without K8up. Persist an encrypted recovery catalog with repository paths, snapshots/set membership, image/schema/extension versions and source mappings outside the cluster. Do not rely solely on Snapshot CRs in the etcd being recovered. K8up's installed Restic version/repository format must also be pinned and recorded; compatibility with the earlier standalone Restic 0.19.1 target probes is not yet proven. Use new pilot repositories, not an unreviewed shared repository upgrade.

## GitOps rollout and acceptance

Proposed implementation locations follow existing cluster-aware paths: `kubernetes/apps/<cluster>/storage/k8up/` for the operator/values/config, corresponding `kubernetes/argo/apps/<cluster>/storage/k8up.yaml`, and namespace policy/adapter resources alongside their owning apps. Keep one owner for cluster-scoped CRDs per cluster; apply the pinned CRD bundle before the chart and dependent policies, use appropriate Application health/sync ordering, and never prune CRDs casually during rollback. Do not assume Helm upgrades existing CRDs. App/infra operators must work independently even while Argo remains the current hub.

1. **Prepare safety boundaries:** NAS writer permissions/export ACLs/snapshots, repository keys and independent escrow, namespace target claims, scoped RBAC and an external alert route. Do not rotate current app credentials as an incidental part of installation.
2. **Install only the operator/CRDs in an approved pilot namespace:** opt-in only, UTC, conservative resources, exact versions; no production annotations/schedules or prune. Verify Talos/Kubernetes compatibility and CRD ownership. Use a synthetic namespace/policy and disposable repositories first.
3. **Prove discovery/storage:** two worker-local RWO PVCs on different workers, a stopped source, NFS local backend and every operation's mount; negative cases for missing nodes, excluded media/targets/caches, unknown profiles and zero matches. Prove one profile cannot execute another profile's capture command and one-off app capture does not widen selection.
4. **Prove capture/restore:** synthetic PG export/import including producer failure and partial output; native-archive content verification; filesystem restore to a different prepared worker; wrong app/path/ID rejected. Exercise independent-key recovery without the original Snapshot CRs/controller.
5. **Enroll critical live DB/DNS exports:** use least-privilege app credentials and exact-instance DNS targets; take a one-off backup, restore to isolated fresh storage and verify the app. Only then enable their six-hour schedules and capture-age alerts.
6. **Enroll remaining classes:** verified native app exports first, then explicit hostPath/cold-copy adapters after scoped GitOps pause, shutdown grace and independent-watchdog failure tests. Coordinate/test photo sets separately; respect the original-phone-data boundary.
7. **Enable maintenance:** repository-lock race tests, retention dry-run, corruption/missing-key checks and delivered failure/dead-man notifications. Enable check/prune/drill schedules after acceptance; retain upgrade checkpoints and document measured capacity/recovery times.

The pilot is a go/no-go decision for K8up, not permission to leave some existing state silently unprotected. If a constraint cannot be met, record that source as uncovered and bring back a concrete alternative before rollout; do not solve it by copying live databases or broadening mounts/RBAC without review. All work remains GitOps-driven with repeatable Task entry points. Nothing here changes the two physical infra nodes, Proxmox or Terraform.

Rollback: stop the new scheduling through Git and allow active work to finish/terminate under the tested watchdog; restore any scoped app reconciliation/replica state; preserve source storage, target repositories, passwords and recovery catalogs. Keep CRDs/operator until pending restores and cleanup are understood. Removing enrollment must not delete old snapshots immediately. Never delete source PVCs, erase the NAS dataset or uninstall CRDs as a rollback shortcut.

## Evidence and references

Verified design sources: official K8up 2.16 documentation and source at operator tag **v2.16.1** / chart **4.10.1**. Worker grouping and backup selection remain inspected implementation behavior, not live data-path validation. Argo has installed the digest-pinned controllers on both clusters; the runbook records runtime verification. No production K8up backup/restore policy is enabled, and the remaining pilot must provide actual file/DB recovery and failure evidence.

Local draft checks: Helm rendered chart 4.10.1 to operator image v2.16.1 with
opt-in enabled and timezone UTC; that operator-only render contained no Backup,
Schedule or Restore CR. Both reference objects (PodConfig and Schedule) validated
against the published v2.16.1 CRD schemas using kubeconform. YAML examples parsed
and relative document links resolved. Temporary schemas were removed. That
design-only check installed no resources; the subsequent operator-only rollout
is recorded in the runbook. Neither check replaces the application data-path pilot.

-   [Annotations and opt-in](https://docs.k8up.io/k8up/2.16/references/annotations.html)
-   [Backend, Schedule, PodConfig, retention and Restore API](https://docs.k8up.io/k8up/2.16/references/api-reference.html)
-   [Application-aware streaming](https://docs.k8up.io/k8up/2.16/how-tos/application-aware-backups.html)
-   [PreBackupPod behavior](https://docs.k8up.io/k8up/2.16/how-tos/prebackuppod.html)
-   [Restore limitations and time-filter fallback](https://docs.k8up.io/k8up/2.16/how-tos/restore.html)
-   [Pinned chart values and image version](https://github.com/k8up-io/k8up/blob/k8up-4.10.1/charts/k8up/values.yaml)
-   [Pinned worker grouping and no-source success behavior](https://github.com/k8up-io/k8up/blob/v2.16.1/operator/backupcontroller/executor.go)
-   [Pinned policy/pod selection and namespace executor binding](https://github.com/k8up-io/k8up/blob/v2.16.1/operator/backupcontroller/backup_utils.go)
-   [Pinned stream failure and command logging](https://github.com/k8up-io/k8up/blob/v2.16.1/restic/kubernetes/pod_exec.go)
-   [Velero filesystem backend and hostPath limitations](https://velero.io/docs/v1.18/file-system-backup/)

## Next actions

Operator installation is complete; **application backup protection is not**.
Use the [rollout acceptance criteria](#gitops-rollout-and-acceptance) to close
the remaining gates, not operator health alone.

-   [x] Install independent, digest-pinned operators and protected CRDs through Argo on both clusters.
-   [x] Verify worker placement, opt-in discovery, UTC, live metrics and reproducible operator Tasks; confirm no production K8up schedules or operations were created.
-   [ ] Harden NAS writer/export permissions and snapshot protection; establish repository keys, independent escrow and namespace-local target claims.
-   [ ] Pass the multi-worker storage/selection pilot, including missing sources, exclusions, zero matches and cross-policy isolation.
-   [ ] Pass file, streamed-database and native-export restores to fresh isolated targets, including failed/partial captures, wrong snapshot/path rejection and independent-key recovery.
-   [ ] Deliver failure, stale-source and external dead-man alerts before relying on unattended protection.
-   [ ] Enroll critical DB/DNS sources only after their real capture/restore checks pass; then enable their six-hour policies.
-   [ ] Prove scoped GitOps quiesce/restart and independent watchdog recovery before enabling cold-copy policies for remaining app/hostPath state.
-   [ ] Validate matched Immich database/original-photo recovery sets and measure capacity and recovery time before enabling the photo policy.
-   [ ] Pass retention dry-runs and repository-lock safety checks before scheduled pruning; enable recurring integrity checks and isolated restore drills.
-   [ ] Add and restore-test an independent offsite copy; do not count same-NAS repositories or snapshots as completion of that requirement.
