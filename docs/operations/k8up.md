# K8up backup and recovery operations

## Scope

Independent K8up operators run in `backups` on both clusters through Argo. The database-first policy adds six-hour logical backups for **Immich PostgreSQL and LiteLLM PostgreSQL**, weekly metadata checks, monthly full-data checks and 15-minute coverage/Slack audits. The policies require PR merge/Argo sync and first scheduled-run verification; real on-demand captures and isolated database restores already passed. No existing source claim, hostPath, app credential or physical Talos configuration is moved or stopped. Native Immich dumps remain unchanged.

K8up has no bundled backup web UI. Use Argo to inspect Applications/resources and the Tasks below for capture, audit and isolated recovery. There is no public restore endpoint. Database recovery does not include Immich photos, DNS, media/monitoring configs, platform state or an offsite copy.

## GitOps and repeatability

Each cluster's `storage/k8up` Application renders the pinned upstream chart, protected CRDs and its namespace policy resources (`config/media` or `config/ai`). CRDs have an earlier sync wave and `Prune=false,Delete=false`; Helm CRD rendering is disabled. The NAS Application owns `backups`; existing app owners retain their namespaces. Namespace-local NFS target claims/PVs use Retain and are protected from Argo prune/delete.

`task backups:operator-bootstrap CLUSTER=app-cluster` and `CLUSTER=infra-cluster` register the Applications with the existing Argo hub. Argo, not this task, installs workload resources into each destination cluster. Default source revision is `main`. For pre-merge verification only, `REVISION=refactor` bootstraps from the reviewed branch; after merge the parent app-of-apps adopts the same Application names and restores the checked-in `main` revision. The branch must be pushed before invoking that override. This override must never silently change the pinned upstream chart version.

`task backups:operator-status CLUSTER=...` reports Argo and runtime state. `operator-verify` checks CRDs, rollout, opt-in/UTC/image and metrics; use `EXPECT_IDLE=true` only for an operator-only bootstrap, not after enrolling policies. All commands require an explicit destination cluster; hub and target kubeconfigs are not interchangeable.

## Security and rollback

The trusted K8up manager creates namespace executor bindings and Jobs. Capture inspectors can only get/list Pods in their namespace; audit accounts can only list Backups, Snapshots, Checks and Jobs there. Helpers run as UID `1004` without privileges/capabilities, with scoped projected tokens, private memory staging and explicit Secret mounts. Do not grant cluster-admin to backup Pods. Recovery creates a fresh default-deny namespace and makes no public Service/ingress.

Operator/runner and helper images are digest-pinned. Opt-in remains global; raw PGDATA and shared media are not enrolled. DB exporters use read-only marked PostgreSQL logins with `pg_read_all_data` and `pg_read_all_settings`. Actual application database passwords are not rotated. Logical bundles include explicit recovery Secrets inside Restic encryption, not the repository password.

Rollback: remove the new K8up Schedule manifests through Git and set the two maintenance/audit CronJobs to `suspend: true`; allow active Jobs to finish or review them before terminating. K8up Schedule has no `spec.suspend` field. Preserve operators/CRDs, target/source claims, NAS repositories and keys. Never uninstall CRDs, expire snapshots or erase data as rollback.

The pinned chart includes a Helm lifecycle cleanup hook for legacy K8up RBAC:
`pod-executor-namespaced` RoleBindings and `pod-executor` Roles across namespaces.
Both clusters were checked before first installation and had no matching objects.
The hook is part of the upstream chart, not a backup/prune of application data;
its temporary account/RBAC/Job have explicit worker placement and resources.
Review this hook and any same-named RBAC before future upgrades, rather than
assuming every upstream hook is harmless.

## Verified operator-only rollout (historical)

Argo bootstrapped `k8up-app` and `k8up-infra` from `refactor` for pre-merge
verification. Both target clusters established the nine protected K8up CRDs,
rolled out the digest-pinned operator on its intended worker, and served live
Go process metrics through the internal service/API proxy. Operator and runner
image configuration, opt-in selection and UTC were verified. Counts of K8up
Schedules, Backups, Restores and Prunes were all zero. No repository password or
production backup enrollment was created. After merge, allow the parent to adopt
the checked-in `main` revisions; do not remove and recreate the running operators.

Both Applications reached `Synced/Healthy` with successful lifecycle operations.
Bootstrap was repeated to exercise idempotent registration and hook-completion
waiting. `operator-verify EXPECT_IDLE=true` passed on both targets, and startup
log inspection found no error-level, panic or fatal entries.

## NAS identity and access gate

The QNAP export now advertises `10.0.40.0/24`. UID `1004`
(`k8s-backup-operator`) passed write/read/delete checks from both clusters at the
export root and each existing cluster prefix. Tests used unprivileged GID `65534`
with no supplemental groups: no assumption about the numeric ID of
`k8s-backup-operators` was needed. This is a tested process identity, not a change
to the controller's own UID or to production capture policies.

**NAS access gate now passes on both clusters.** With root-only squash enabled,
the NAS administrator corrected ownership non-recursively on the share root and
the two existing cluster prefixes. Actual QNAP path:
`/share/CACHEDEV1_DATA/k8s-backup`.

| Directory       | Owner UID | Mode |
| --------------- | --------: | ---: |
| Export root     |      1004 | 0755 |
| `app-cluster`   |      1004 | 0700 |
| `infra-cluster` |      1004 | 0700 |

Both `backups:access-check` runs passed after repair: UID `1004` completed
encrypted backup, full data check, wrong-password rejection and byte-identical
restore; UID `65534` was denied writes at both export root and cluster prefix.
All disposable probe Jobs/repositories were removed. No media share or existing
application data was changed.

Earlier probes allowed anonymous writes with export-root mode `0777`; switching
to root-only squash then exposed anonymous-owned `0700` prefixes and blocked the
real writer. The owner repair resolved that mismatch without loosening squash.
NAS-managed snapshots, independent repository-key recovery and application
capture/restore acceptance remain separate prerequisites; no production schedule
was enabled by this permission correction.

`task backups:smoke CLUSTER=...` now runs its disposable encrypted backup/check/
restore as UID `1004`, GID `65534`, rather than root. For the full access gate,
run `task backups:access-check CLUSTER=app-cluster` and repeat with `infra-cluster`.
It requires both that smoke test and write denial for unrelated UID `65534`.
Permission probes fail promptly on failed Jobs instead of waiting only for a
success condition. Failed diagnostic Jobs remain for inspection/TTL cleanup.
The access gate must pass before production archives/schedules are enabled.

NAS operator actions:

1. Inspect the share's **NFS host access / squash mapping**. Preserve distinct
   client user identities; do not map every client to the backup writer or an
   anonymous identity with write access. Root-squash and all-user squash are not
   equivalent; verify the actual behavior with the access gate.
2. Review the actual export directory and existing backup-prefix **Unix/advanced
   ACL ownership and permissions**, not only SMB/guest access. Grant UID `1004`
   the intended access, remove anonymous/world write access, and ensure existing
   test-created prefixes are not owned/writable solely through an anonymous
   mapping. For a writer-only directory, owner UID `1004` with mode `0700` is a
   possible Unix policy; reconcile QNAP ACL/mapping behavior before applying it.
   Do not recursively change `/media` or other unrelated NAS shares.
3. Keep the `/24` host restriction and rerun both cluster access gates. NAS
   snapshots and independent repository-key recovery remain separate prerequisites.

To repeat the scoped ownership repair, use an authorized NAS administrator shell
with root privileges, confirm the resolved directory is the dedicated backup
share, and run the following non-recursive commands. The numeric writer identity
is part of the NFS contract; do not silently substitute another user's UID.

```sh
set -eu
[ "$(id -u k8s-backup-operator)" = 1004 ]
p=$(readlink -f /share/k8s-backup)
[ -n "$p" ] && [ -d "$p" ] && [ "$(basename "$p")" = k8s-backup ]
[ -d "$p/app-cluster" ] && [ ! -L "$p/app-cluster" ]
[ -d "$p/infra-cluster" ] && [ ! -L "$p/infra-cluster" ]
ls -ldn "$p" "$p/app-cluster" "$p/infra-cluster"
chown 1004 "$p" "$p/app-cluster" "$p/infra-cluster"
chmod 0755 "$p"
chmod 0700 "$p/app-cluster" "$p/infra-cluster"
```

Do not reset these directories to `0777` to solve a future failure. Inspect the
actual owner/squash/ACL result and rerun both access gates. Administrative SSH
credentials remain local/outside Git and are not consumed by backup workloads.

QNAP reference: [configuring NFS host access](https://docs.qnap.com/operating-system/qts/4.5.x/en-us/GUID-4A850D3A-5293-4B13-ABEF-8B66D1384BFC.html).

`K8S_BACKUP_OPERATOR_PW` is a NAS login password, not an NFS AUTH_SYS credential
or a Restic repository key. These tests do not read/use it. Future encrypted
repositories need separate durable keys. Even after this gate passes, numeric
NFS identities are not strong authentication against a privileged allowed
client; export/network trust and NAS-managed snapshots remain important.

## Disposable file data-path pilot

`task backups:pilot-files CLUSTER=...` is a synthetic-only test, not production
enrollment and not a substitute for the NAS isolation gate. It creates a unique
temporary namespace, writes distinct generated payloads to local-path claims on
two nodes, and asks the installed K8up operator to back up explicitly opted-in
claims to a unique disposable NAS repository as UID `1004`. A similarly labeled
but excluded claim tests opt-out behavior. An exact snapshot/path is restored
to a fresh claim on the other source node and verified by SHA-256.

The pilot uses a random temporary repository key stored only in a temporary
Kubernetes Secret, never in Git/output, and no production source is mounted.
Its namespace, Jobs, Secret, test files and repository are removed afterward.
Local-path PVs remain Retain throughout; after test files are erased, temporary
claims/PV objects are removed. Empty backing directories may remain on workers
because Retain deliberately does not invoke destructive provisioner cleanup.
No physical Talos settings or existing app replicas are changed.

If cleanup fails, the Task exits nonzero; inspect the printed unique pilot
namespace and failure before retrying cleanup. Never broaden cleanup to existing
app namespaces or production repositories.

Passing this pilot proves only synthetic worker-local file backup/restore and
selection behavior. It does not prove database/native-import recovery, cold-copy
coordination, alert delivery or protection from NAS loss. Production policies
remain disabled pending the remaining application/key/alert acceptance gates,
even though NAS write isolation now passes.

### Observed pilot results

-   App-cluster passed on `k8s-wrkr-02` / `k8s-wrkr-03`: two selected local-path
    sources backed up as UID `1004`, excluded claim absent from snapshot paths,
    exact source-b snapshot/path restored to a fresh claim on `k8s-wrkr-02`,
    SHA-256 matched. The finalized pinned-image/cleanup path passed too.
-   Infra-cluster now passes after merged PR #453 and Argo reconciliation:
    source claims on `infra-cp-01` / `infra-wk-01` provisioned, both selected
    sources were captured, the excluded claim was absent, and an exact snapshot
    restored onto fresh storage on the other worker with matching SHA-256.
    Only the helper's contradictory hostname selector changed; provisioner
    Deployment placement and physical node/storage configuration did not.
-   Both completed and failed pilot namespaces, temporary Secrets, repositories,
    bound-claim files/PV objects and the separate scheduling-smoke pod were removed.
    The Retain caveat above applies to empty backing directories.

The infra repair is a Kubernetes helper-placement correction, not a physical
node/storage migration. Its design, validation and rollback are recorded in the
[architecture plan](../architecture/k8up-backup-automation.md#infra-local-path-helper-scheduling-repair).

## Repository key bootstrap

`task backups:keys-bootstrap CLUSTER=... NAMESPACE=... PROFILE=...` establishes
one durable random repository password in Doppler and the workstation's default
macOS Keychain. This does not enroll an app, initialize a repository or enable a
Schedule. `backups:keys-verify` compares both copies without printing them.
Run bootstrap from one administrator workstation at a time; a local lock guards
concurrent invocations here, not changes made by other workstations/admins.

Identifiers are deterministic: Doppler project `home-dc-kubernetes`, config
`apps` or `infra`, secret `K8UP_<NAMESPACE>_<PROFILE>_PASSWORD` (uppercase,
hyphens converted to underscores); Keychain service
`home-dc.backups.<cluster>.<namespace>.<profile>`, account `restic`.
An existing key is reused, never silently rotated. Conflicting copies abort.
If only escrow remains, bootstrap restores the same key to Doppler; if only
Doppler remains, bootstrap escrows that same key before reporting success.
If both key stores are missing, bootstrap first runs a UID `1004`, read-only
NAS probe and refuses any nonempty/unreadable repository. Never generate a
replacement password for existing encrypted archives. Empty-target acceptance
and rejection of the real populated infra repository were exercised.
No key is printed, passed as a command argument, or written into a local file.

Recovery can retrieve the Keychain item without either Kubernetes cluster or
its Doppler operator. Keep the service/account names in the recovery record.
This local escrow is not proof of recovery after losing the workstation;
1Password/offsite escrow remains a separate improvement. Do not delete or rotate
old keys while their repositories or retained snapshots still exist.

## Database policy operations

### Bootstrap and rollout

Prerequisites: working destination kubeconfigs, authenticated Doppler CLI,
administrator macOS Keychain and the verified UID `1004` NAS target. Commands
do not print keys. Repeat the NAS access gates before rebuilding protection.

```sh
task backups:keys-bootstrap CLUSTER=app-cluster NAMESPACE=media PROFILE=critical-6h
task backups:keys-bootstrap CLUSTER=infra-cluster NAMESPACE=ai PROFILE=critical-6h
task backups:postgres-credentials-bootstrap CLUSTER=app-cluster
task backups:postgres-credentials-bootstrap CLUSTER=infra-cluster
task backups:alerts-bootstrap
task backups:policy-verify CLUSTER=app-cluster
task backups:policy-verify CLUSTER=infra-cluster
```

Bootstrap reuses existing marked accounts/keys, refuses mismatched ownership or
key copies, and never rotates the real app login. `alerts-bootstrap` copies the
existing app monitoring Slack webhook to infra only if absent; a different
existing infra route is not overwritten. Doppler owns `k8up-source-credentials`
in `media`/`ai`; only its selected repository/source password and Slack keys
are reconciled.

Merge the reviewed PR and let `k8up-app` / `k8up-infra` sync from `main`.
No manual `kubectl apply` is needed. Confirm the target claims are Bound, each
namespace's `critical-6h` Schedule exists, and its first scheduled Backup and
owned Job succeed with a fresh exact-path Snapshot. Run `backups:audit` on each
cluster afterward; a schema dry-run alone is not rollout proof.

| Policy                          | app-cluster `media` (UTC)  | infra-cluster `ai` (UTC)   |
| ------------------------------- | -------------------------- | -------------------------- |
| Logical database capture        | 00:20, 06:20, 12:20, 18:20 | 00:35, 06:35, 12:35, 18:35 |
| Metadata check                  | Sunday 02:20               | Sunday 02:35               |
| Full `check --read-data`        | First of month 05:10       | First of month 05:25       |
| Coverage/capacity/failure audit | Every 15 minutes           | Every 15 minutes           |

Audits require each declared app's exact artifact path and full snapshot ID
inside a successful selected Backup/owned-Job window. They use Backup creation
as a conservative capture-age bound, not upload time; warn beyond eight hours,
on a newer failed capture/check, overdue checks or NAS filesystem free space
below 20%. Failed producers may leave a snapshot: that alone is never accepted.
Matching failures notify once, then daily; changed problems and recovery notify
immediately. Nonsecret suppression state lives beside, not inside, each Restic
repository. Native weekly checks do not perform full data reads.

`policy-smoke` injects a temporary expected-but-missing source, requires a real
failed audit and delivered Slack acknowledgement, then restores the real
inventory and requires a healthy audit/recovery notification. It installs no
Schedule. `check-data` runs the actual GitOps full-check template once; its
completed/failed Job remains for audit evidence with a 36-day TTL. No command
automatically breaks locks or prunes archives. All snapshots are retained until
the separately reviewed retention gate passes.

### Capture, drill and recover

```sh
task backups:run CLUSTER=app-cluster APP=immich-db
task backups:prove CLUSTER=infra-cluster APP=litellm-db
task backups:audit CLUSTER=app-cluster
task backups:check-data CLUSTER=infra-cluster
task backups:restore CLUSTER=app-cluster APP=immich-db SNAPSHOT=<full-64-character-id>
task backups:recover CLUSTER=infra-cluster APP=litellm-db SNAPSHOT=<full-64-character-id>
```

`run` records a capture; `prove` captures and performs a disposable recovery.
**`restore` is a drill: it verifies then erases only its newly created target.**
**`recover` keeps the verified database Pod/PVC, its database-password Secret and
the explicitly archived application Secrets in the printed isolated namespace**
for an explicitly reviewed cutover, including LiteLLM's original salt/key inputs.
The temporary repository reader/key are removed before a retained recovery is
reported. Neither command overwrites production or starts app integrations.
`TARGET_CLUSTER=...` can use the other prepared cluster; repository identity
still refers to the original source. Review capacity/image support first.

Recovery uses the independently escrowed Keychain key, immutable snapshot ID and
source-recorded image digest, not the source Secret operator or Snapshot CR.
It fully checks repository data, verifies byte count/SHA-256 and every archive
member checksum, imports globals/data with ownership/extensions, authenticates
the app's recovered database role, then runs read-only application queries.
PostgreSQL 17 requires the original bootstrap role for `GRANTED BY`; recovery
preserves it and removes only its already-created `CREATE ROLE` statement.
Custom tablespaces are rejected pending an explicit storage mapping.

The decrypted transport is loopback-only via authenticated Kubernetes
port-forward; staging is memory-backed. Metadata-only local records live in
ignored `.private/backup-captures` and `.private/backup-restores`. Private failed
command diagnostics are mode `0600`; do not paste their contents unredacted.
Capture format 2 records the bootstrap role; earlier experimental format-1
snapshots require manual role reconciliation rather than a silent fallback.

For a retained recovery, leave the default-deny policy in place. Review exact
images, source/target volume paths, app Secrets and Argo ownership before
promotion; no automatic production cutover is authorized. After a drill,
Retain may leave empty worker directories, not source data deletions.
Recovery database files run as UID `1004`. Do not simply rebind this cross-namespace
PVC to a normal app Deployment with a different UID; plan a logical transfer or
reviewed ownership/path migration with Argo before production promotion.

### Exercised application evidence — 2026-10-30

Real encrypted NAS snapshots:

-   Immich: `0c1d9d533a525491367b8f84fc4500512f8d94841669a0c31088931df4972806`,
    `/media-immich-db.tar`; recovered 1 user / 3,518 assets, extension versions
    matched, original database credential authenticated.
-   LiteLLM: `a596827eb4e22ccf13367bded874483fa263c10980ef1e32768d21e03575b8b3`,
    `/ai-litellm-db.tar`; recovered 83 application tables, 1 user, 11 virtual keys
    and 1 config entry, matching read-only source queries. Extensions matched
    and the actual application database credential authenticated.

Both restored to fresh local storage on the other worker; production apps were
not stopped. Both actual policy renders passed server-side dry-run; both
full-data template Jobs reported `no errors were found`. Both missing-source
and healthy recovery messages were acknowledged by Slack. Synthetic PG14/PG17
pilots also passed partial/nonzero-producer rejection, invalid archive,
wrong-key/path/snapshot rejection and independent-key import after deleting
original Snapshot CRs/Secret.
The retained-recovery path also passed: the database passed state queries and
every required application Secret's bytes matched the source; the temporary
repository reader/key were absent. An outbound API connection timed out under
the default-deny policy. The test namespace was then explicitly cleaned.

LiteLLM's current `LITELLM_USERDB_USER` does not exist in its live database.
The app actually connects as `LITELLM_POSTGRES_USER`; that principal is tested.
The source owner role is preserved, and all selected Secret keys are archived,
but recovery does not invent a new unused user. Reconcile initialization-only
credential drift separately; no source account was changed to hide it.

One verified orphan lock from a failed pilot capture was removed manually after
confirming its exact owner Pod was absent and no repository operation remained
active. No automation uses force-unlock. Live locks require investigation, not
blind removal.

### Remaining assurance limits

This is **database protection**, not a completed whole-homelab backup.
Immich originals/matched recovery sets, DNS, media/monitoring state, Talos/etcd,
retired archives and offsite replication remain separate work. No restored
Immich frontend/photo retrieval or LiteLLM upstream request was exercised.
Repeat database recovery monthly and before major schema/image changes;
these application drills are explicit Tasks, not a scheduled restore service.

Slack audits need their cluster, DNS/egress and NAS mount to function. An
external dead-man receiver must independently detect loss of those components.
Workstation-loss key escrow and NAS snapshot/immutability protection still need
verification; neither same-NAS storage nor a local Keychain is an offsite copy.
