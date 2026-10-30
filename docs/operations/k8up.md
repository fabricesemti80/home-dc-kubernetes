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

The operator's image and backup-runner image must be digest-pinned. Opt-in is enforced globally, timezone is UTC, resource requests/limits are explicit, and the operator is placed on a worker. No global source-runner nodeSelector is set: future RWO backup Jobs must follow source volume placement. Production enrollment remains blocked on the storage/selection/restore/failure pilot, NAS permissions, repository-key escrow and alert delivery described in the design.

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
