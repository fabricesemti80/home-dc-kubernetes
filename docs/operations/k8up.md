# K8up operator operations

## Scope

Install independent K8up operators in `backups` on both clusters through Argo. This is the operator-only rollout from the [automation design](../architecture/k8up-backup-automation.md), not production backup enrollment. The NAS target is already deployed; no existing PVC, hostPath state, app credentials or physical Talos configuration is moved or changed. No Backup, Schedule, Restore or prune policy is created by this installation. Existing native Immich database dumps are unchanged.

K8up has no bundled backup web UI. Do not create a misleading `backup.krapulax.home` HTTPRoute to its metrics endpoint. Use the existing Argo UI to inspect its Applications/resources, and the Task entry points below for operator verification. App-aware snapshot browsing/import/restore Tasks remain a separate implementation gate; installing the operator does not supply a restore portal or make applications protected.

## GitOps and repeatability

Each cluster's `storage/k8up` Application renders the pinned upstream chart plus its own CRD source. CRDs are applied in an earlier sync wave and carry `Prune=false,Delete=false`; Helm CRD rendering is disabled to avoid duplicate ownership. The existing NAS Application owns the `backups` Namespace. `CreateNamespace=true` supports bootstrap before that Application reconciles, without adding a second Namespace manifest.

`task backups:operator-bootstrap CLUSTER=app-cluster` and `CLUSTER=infra-cluster` register the Applications with the existing Argo hub. Argo, not this task, installs workload resources into each destination cluster. Default source revision is `main`. For pre-merge verification only, `REVISION=refactor` bootstraps from the reviewed branch; after merge the parent app-of-apps adopts the same Application names and restores the checked-in `main` revision. The branch must be pushed before invoking that override. This override must never silently change the pinned upstream chart version.

`task backups:operator-status CLUSTER=...` reports Argo status, Deployment and pods. `task backups:operator-verify CLUSTER=...` waits for CRDs and rollout, verifies opt-in/UTC/image configuration, exercises the controller metrics endpoint through the Kubernetes API, and checks that no backup Schedule was accidentally created. The current deployment intentionally has zero enrolled applications. Commands always require an explicit cluster; the hub and target kubeconfigs are never interchangeable.

## Security and rollback

The chart's trusted manager can create workloads and namespace runner bindings. Its executor role permits pod exec within namespaces where it is bound; it is not an unprivileged file copier. Keep these roles under GitOps review, use separate installations/credentials per cluster, and do not add cluster-admin. No public ingress, ServiceMonitor, PrometheusRule or new secret-manager integration is enabled by the operator-only installation.

The operator's image and backup-runner image must be digest-pinned. Opt-in is enforced globally, timezone is UTC, resource requests/limits are explicit, and the operator is placed on a worker. No global source-runner nodeSelector is set: future RWO backup Jobs must follow source volume placement. NAS write-access verification now passes; production enrollment remains blocked on the remaining storage/selection/restore/failure pilot, repository-key escrow and alert delivery described in the design.

Rollback: stop any future schedules and finish/abort restores safely before removing the operator. Preserve CRDs, NAS repositories, Snapshot metadata and keys; never uninstall CRDs to undo this rollout. There are no production K8up policies to suspend in this operator-only phase. Do not remove namespace or source data. Revert the Application/values commit and reconcile the reviewed prior configuration if the operator image/config must be rolled back.

The pinned chart includes a Helm lifecycle cleanup hook for legacy K8up RBAC:
`pod-executor-namespaced` RoleBindings and `pod-executor` Roles across namespaces.
Both clusters were checked before first installation and had no matching objects.
The hook is part of the upstream chart, not a backup/prune of application data;
its temporary account/RBAC/Job have explicit worker placement and resources.
Review this hook and any same-named RBAC before future upgrades, rather than
assuming every upstream hook is harmless.

## Verified rollout

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

The updated non-root smoke test passed on both clusters: encrypted Restic backup,
full data verification, incorrect-password rejection and byte-identical restore
all succeeded as UID `1004` / GID `65534`. The full access gate then correctly
failed on both clusters because unrelated UID `65534` could write at both paths.
Controlled emptyDir checks also proved that genuine permission denial passes the
guard, while a read-only-filesystem error does not falsely count as access control.
All disposable repositories, permission probes and diagnostic Jobs from these
checks were removed after inspection. No production data or repository keys were
written, and no production K8up source/policy was enabled while this NAS gate remained open.

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
-   Infra-cluster failed **before K8up capture**: provisioning source-b on
    `infra-wk-01` timed out because the local-path helper's explicit hostname
    selector required `infra-cp-01`. Helper events reported `NodeAffinity`.
    The PR removes only that helper selector. A disposable helper rendered without
    the conflicting selector ran successfully on `infra-wk-01`; provisioner
    Deployment placement remains `infra-cp-01`. The live ConfigMap was not patched.
    After merge/Argo reconciliation, rerun `task backups:pilot-files CLUSTER=infra-cluster`;
    the full infra backup/restore pilot is **not yet passed**.
-   Both completed and failed pilot namespaces, temporary Secrets, repositories,
    bound-claim files/PV objects and the separate scheduling-smoke pod were removed.
    The Retain caveat above applies to empty backing directories.

The infra repair is a Kubernetes helper-placement correction, not a physical
node/storage migration. Its design, validation and rollback are recorded in the
[architecture plan](../architecture/k8up-backup-automation.md#infra-local-path-helper-scheduling-repair).
