# Backrest operations

## Deployment and access

Merge the replacement PR. The parent app-of-apps discovers `backrest-app` and
`backrest-infra`; both target `backups`. If a registration needs bootstrapping:

```sh
task backups:bootstrap CLUSTER=app-cluster
task backups:bootstrap CLUSTER=infra-cluster
```

These Tasks register Argo Applications, not manually install deployments.
`REVISION=refactor` is an explicit pre-merge preview override, not the normal state.
NAS Applications/claims and Doppler tokens must already exist. Credential setup
is reproducible with `task backups:credentials CLUSTER=...`: it verifies independent
repository-key copies, refuses a nonempty unkeyed repository, and provisions the
marked `backrest_backup` read-only database login without rotating app users.

| Cluster       | Internal UI                         | Doppler config | Native export      | Backrest DB plan |
| ------------- | ----------------------------------- | -------------- | ------------------ | ---------------- |
| app-cluster   | http://backrest.krapulax.home       | apps           | 00/06/12/18:20 UTC | :40              |
| infra-cluster | http://backrest-infra.krapulax.home | infra          | 00/06/12/18:35 UTC | :55              |

Native login: **admin**. Password: Doppler `BACKREST_ADMIN_PASSWORD` in the indicated
config. Do not paste it into Git/issues. `task backups:ui CLUSTER=...` provides a
private `http://127.0.0.1:9898` tunnel if LAN DNS is unavailable. No public route is
created. Internal HTTP assumes the trusted LAN; do not expose it to untrusted networks.

Repositories are `10.0.40.2:/k8s-backup/<cluster>/backrest/repository`. Independent
Keychain service: `home-dc.backrest.<cluster>`, account `restic`. Keep a separately
accessible copy for workstation loss; current Keychain escrow alone does not prove that.

Git owns plans/auth/credential references. Restart materializes current Git inputs
while preserving Backrest's generated identity and existing repository GUID.
Make lasting plan changes in Git, not only the UI. Retention: 24 hourly, 14 daily,
8 weekly, 12 monthly representatives (`app-*` config plans: 14 daily, 8 weekly, 6 monthly). Weekly full-data checks and pruning are
managed by Backrest; locks are not automatically broken. Slack receives failures
and snapshot warnings through the existing monitoring webhook.

## First backup and restore gates

```sh
task backups:status CLUSTER=app-cluster
task backups:export CLUSTER=app-cluster APP=immich-db
task backups:run CLUSTER=app-cluster PLAN=immich-db
task backups:run CLUSTER=app-cluster PLAN=immich-originals
task backups:run CLUSTER=app-cluster PLAN=backrest-config

task backups:export CLUSTER=infra-cluster APP=litellm-db
task backups:run CLUSTER=infra-cluster PLAN=litellm-db
task backups:run CLUSTER=infra-cluster PLAN=backrest-config
```

`run` waits for native backup execution; large photo backups can take hours.
`check` and `restore` queue operations: inspect their completion in the UI or
`backups:status`. The CLI allows up to four hours for mutating native calls.
Task cluster-dependent kubeconfig variables are scoped to each task so the
infra commands cannot inherit the app-cluster kubeconfig during include loading.
Restore creates only the target's parent: Backrest requires the final directory
to be absent and refuses an existing destination. Missing
or older-than-eight-hour DB archives fail the start hook, rather than refreshing
an old artifact and claiming a new database capture. Native exporter failures
leave the previous archive unchanged. Staging is private local storage, not
plaintext NAS files. A lost staging PVC does not erase already encrypted snapshots.

List immutable IDs and restore a chosen point:

```sh
task backups:snapshots CLUSTER=app-cluster PLAN=immich-db
task backups:restore CLUSTER=app-cluster PLAN=immich-db SNAPSHOT=<full-64-hex-id>
```

Repeat for `immich-originals` and infra `litellm-db`. Each Task generates a new
`/backups/<cluster>/backrest/restores/<uuid>` target. On NAS this is
`/k8s-backup/<cluster>/backrest/restores/<uuid>`. Nothing overwrites production.
The UI also supports browsing snapshots and restoring selected files. Remove
only your disposable restore directory after recording successful checks.

## Protecting and opting out apps

Application config is protected by default through Git, not Kubernetes labels.
Each app has one entry in `kubernetes/apps/<cluster>/storage/app-protect/values.yaml`
and a matching `app-<name>` plan in that cluster's `backrest/config/config.json`.
Design and limits: [architecture](../architecture/backrest.md#application-configuration-coverage).

Add a new app (protected):

1. Add an entry: `name`, `namespace`, `node` (where the volume lives), `schedule`
   (daily UTC cron, staggered, outside 03:00-04:00), and `claim` (PVC name) or
   `hostPath`. Add `excludes` for caches/logs/regenerable data (fnmatch on a name
   or relative path). Add `tolerations` for tainted nodes.
2. Copy an existing `app-<name>` plan in `config.json`: path
   `/backups/<cluster>/exports/<name>/current`, start hook checking `.captured-at`
   is newer than 1560 minutes, schedule about 90 minutes after the export.
3. Check it renders: `helm template x kubernetes/charts/app-protect -f kubernetes/apps/<cluster>/storage/app-protect/values.yaml`.
4. After merge: `kubectl create job --from=cronjob/protect-<name> <name>-first -n <ns>`,
   then `task backups:run CLUSTER=<cluster> PLAN=app-<name>`.

Opt out (apps that are only being tested, stateless, or Git-reconstructable):

```yaml
- name: some-test-app
  namespace: media
  node: k8s-wrkr-03
  claim: some-test-app
  schedule: 30 1 * * *
  protect: false # no CronJob is rendered
```

Also delete its `app-<name>` plan from `config.json`; otherwise the plan's start
hook fails on the missing export. Keep the entry with `protect: false` instead of
removing it, so the opt-out is a visible, reviewed decision. Remove an app that
no longer exists entirely, and leave its old `exports/<name>` directory on the NAS
until you decide to delete it. Flipping back to `true` resumes exports; the next
run replaces the stale copy.

Not enrollable this way: databases (use a native exporter as for Immich/LiteLLM)
and Uptime Kuma (embedded MariaDB).

## Database import verification

A restored `.tar` is not a restored database. Extract it into a private temporary
directory; verify `SHA256SUMS`, `app`, `captured-at`, `database.json`, and fully read
the dump with the matching `pg_restore --file=/dev/null database.dump`.

Use a fresh isolated PostgreSQL instance, never the live database. Immich needs
the exact compatible vector-enabled image in its export CronJob; plain PG14 is
not sufficient. LiteLLM needs compatible PG17. Initialize with the recorded
`bootstrap_role` (currently `postgres`); preserve it for PG17 `GRANTED BY` semantics.
Create other roles from `roles.sql`, omitting only the exact `CREATE ROLE` line
for that already-initialized bootstrap role. Apply `ALTER ROLE` and grants; do not
ignore arbitrary SQL errors. The custom dump retains database creation/ownership
metadata: use `pg_restore --exit-on-error --create --dbname=postgres database.dump`
against the fresh instance, with the recorded preload/extension versions. If
creating the database separately, inspect `pg_restore --schema-only --create`
output for the original owner; do not assume the bootstrap role owns the app DB.

Role password hashes are deliberately absent from `roles.sql`. Restore app
credentials from the archive's `secrets/` files through private input, not shell
arguments/logs. Validate Immich users/assets/extensions and authenticated database
access; validate LiteLLM configuration/key identities and its actual app database
login without invoking chargeable upstream APIs. Keep outbound app integrations
blocked throughout the drill. Retain exact snapshot IDs and verification results.

For Immich additionally restore originals and preserve `/data` and
`/external-library` mappings. In deployed Immich v3.0.3, external-library imports
use SHA-1 of `path:<originalPath>` with algorithm `sha1Path`, not a file-content
checksum ([upstream ingestion](https://github.com/immich-app/immich/blob/v3.0.3/server/src/services/library.service.ts#L413)).
Validate those path identities and the existence of every referenced original;
verify restored file contents independently against the Restic snapshot using
native `restore --verify`. Do not diagnose corruption by comparing file SHA-1
with an external path hash. Daily online originals and separate DB dumps are
**not** advertised as a paused matched set. No app shutdown is added
by this PR. Remaining unprotected application classes are listed in the
[inventory](../cluster/database-backups.md).

## Remove superseded K8up and old NAS backups

Only after real file restores **and the isolated SQL imports above** pass:

```sh
task backups:retire-k8up CLUSTER=app-cluster DATABASE_IMPORTS_VERIFIED=yes
task backups:retire-k8up CLUSTER=infra-cluster DATABASE_IMPORTS_VERIFIED=yes
```

The Task requires successful native Backrest restore history for existing
replacement snapshots; `DATABASE_IMPORTS_VERIFIED=yes` is the operator's explicit
attestation of SQL/application checks, not an automated claim. It refuses
unexpected schedules, cascading Argo finalizers and active legacy jobs. Once
legacy scheduling is stopped, an active-job refusal is safe to retry after work
finishes. Retire each cluster separately.

The one-time migration removes legacy registrations, policy resources, CRDs and
labeled operators/RBAC, then erases only these old repository paths:

-   `app-cluster/media/critical-6h`
-   `app-cluster/media/photos-daily`
-   `infra-cluster/ai/critical-6h`
-   `infra-cluster/network/critical-6h` (if present)

The share/account/ACLs, `backups/k8s-backup`, new `backrest` prefixes, original
`/media` photos/movies/downloads and retained retired application volumes are
excluded. Old encryption-key escrow is retained rather than silently deleting
recovery credentials; review obsolete secret-manager items separately once no
old repository copies remain. No cleanup is run merely by merging the PR.

Rollback code is preserved on `backup/k8up-before-backrest-20261030`, commit
`94abc54`. Before destructive retirement, revert/reconcile that code if needed.
After old repository deletion the branch cannot recover the erased backup data.
The new Backrest repository and its keys must remain intact.

## Pre-merge verification (2026-10-30)

-   Both destination APIs accepted the rendered Deployments/PVCs/Services and
    Kustomize resources in server-side dry runs.
-   The pinned Linux image and actual startup initializer ran as UID 1004 with
    read-only root filesystems on both clusters. Each made an encrypted NAS backup,
    restored it through the native API, and byte-compared the result. Disposable
    Pods, credentials, repositories and restored copies were removed.
-   Both real PostgreSQL sources exported successfully with the checked-in
    CronJob commands. A forced connection failure left each previous archive
    byte-identical; temporary export probes were removed.
-   Native Backrest 1.14.1 rejected unauthenticated API access, authenticated the
    configured user, displayed its dashboard in a real browser, and completed
    native backup/restore with identical bytes.
-   A nine-hour-old export failed the fatal start hook with backup/hook error
    operations and no new snapshot.
-   Legacy retirement refused before any deletion because replacement deployment
    was not yet ready. Its positive destructive path is intentionally post-merge.

The cutover gate requires restores of existing snapshots with successful backup
history within eight hours for DB plans and thirty hours for originals. SQL
imports/application checks remain an explicit operator attestation. These smoke
results are not a claim that scheduled production Backrest coverage is already live.

## Post-merge acceptance (2026-10-30)

Both Backrest Applications and the parent `apps` Application are Synced/Healthy.
Both internal DNS names served authenticated dashboards. Deployed native export
Jobs and all Backrest plans completed successfully.

| Recovery point       | Immutable snapshot                                                 | Exercised recovery                                                                                                                                             |
| -------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Immich database      | `a05c8848b82a4229d53238f3e7cbf14408cd47369ae5716dbafedef1a88592c1` | Fresh PG14/vector import on W3 from source W2; matching extensions, app database authentication, 1 user and 3,518 assets                                       |
| LiteLLM database     | `ba9f3dd439a41259a777f3375c253c435603475c4a30b7a35aad209f047949f0` | Fresh PG17 import on infra-wk-01 from source infra-cp-01; matching extensions/ownership/login, 83 tables, 1 user, 11 virtual keys and 1 config entry           |
| Immich original tree | `00e24288a26cfa106de7132eee0e19f2166e680828760e660e32655f9c91b77a` | Full native restore: 15,897 regular files / 34,778,694,995 bytes; every recovered DB original path present and all 3,518 external path-identity hashes matched |

Native `restic restore --overwrite=always --verify` then completed successfully
against the complete restored photo tree using the independently escrowed
Keychain key. `--overwrite=never` is not used as content-readback evidence because
it can skip existing files. Disposable SQL namespaces/PVC contents and successful
restore scratch copies were removed after verification.

Restore-gated retirement completed separately on both clusters: legacy operators,
K8up CRDs/policies and enumerated old repository paths are gone. New repositories
remain populated; cluster-prefix ownership is still UID 1004 / mode 0700. Original
Immich/LiteLLM claims remain Bound to their original production volumes. No
original media, physical infra node configuration or NAS share ACLs were changed.

The follow-up Task/API corrections are in PR #456. The cutover exercised explicit
runs of deployed schedules; the next natural timer executions still need their
normal operational observation. This protects the listed database/original/config
plans, not the remaining application classes in the inventory. Offsite copies,
external dead-man monitoring and NAS immutability remain outstanding.
