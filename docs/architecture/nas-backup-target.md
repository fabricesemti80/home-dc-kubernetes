# NAS backup target and infra workload retirement

## Decision and scope

Use `10.0.40.2:/k8s-backup` directly over NFS for encrypted Restic repositories. Do not deploy an S3 gateway or REST server: a filesystem backend meets the current requirement without another service, TLS/auth bootstrap, metadata database or cluster dependency. This delivers a backup **target**, not scheduled or application-consistent backups. Offsite copies, database dumps, retention, monitoring and per-app restore exercises remain on the roadmap.

The [application backup inventory and recovery plan](../cluster/database-backups.md)
records the verified PVC/hostPath sources, actual database engines, consistency
methods, proposed retention and per-app restore acceptance. It is a design, not
an enabled application-backup schedule.

The [Backrest design](backrest.md) replaces the superseded K8up framework while
retaining this target, NAS account and access controls.

Each cluster has a retained `backups/k8s-backup` RWX claim. Backrest uses separate
`<cluster>/backrest/repository` paths. Existing app configuration remains on its
original worker; no source application state is migrated to NFS.

The `1Ti` claim is not a NAS quota. UID `1004` / GID `65534` writer backup/restore
and unrelated-UID denial were verified on both clusters. Physical infra Talos
configuration is unchanged.

## Security and recovery boundaries

NFS runs on the trusted storage LAN, not public ingress. There is no public hostname or Kubernetes Service. The export advertises `10.0.40.0/24`, narrowed from the initial `/16`, with root-only squash. The NAS share root is owned by UID `1004`, mode `0755`; cluster prefixes are owned by UID `1004`, mode `0700`. Both cluster access gates now verify writer access and unrelated UID `65534` write denial. Guest-login settings and a NAS password do not authenticate NFS AUTH_SYS clients, and privileged allowed clients can impersonate numeric identities. Namespace/PVC separation does **not** isolate data on the same export. A compromised writer with NFS access may delete other repositories. Separate NAS datasets/exports and identities are needed for a stronger per-cluster boundary.

Use encrypted Restic repositories, with persistent repository passwords held in the secret manager **and** an independently accessible recovery copy. The smoke test uses an ephemeral password and disposable repository only. Never reuse its password for production. Enable NAS-managed snapshots whose deletion credentials are unavailable to Kubernetes; snapshots on this NAS are still not offsite backups. Do not give the planned media file manager access to this export.

If Kubernetes is unavailable, mount the export on a trusted recovery host and use Restic directly with the recovery password; the target needs no running in-cluster server. An NFS claim is not proof of application consistency: database-native dumps or an application-specific quiesce procedure remain mandatory.

## GitOps rollout and validation

Argo Applications `nas-backup-app` and `nas-backup-infra` own the retained claims. `task backups:target-smoke CLUSTER=app-cluster` (or `infra-cluster`) checks disposable encrypted backup/restore. Backrest deployment, restore and legacy retirement commands are in the [runbook](../operations/backrest.md).

Pre-merge smoke evidence (2026-10-29): both clusters mounted temporary claims rendered from these manifests using NFS 4.1. Restic 0.19.1 initialized an encrypted repository, backed up known content, read/verified every pack, rejected an incorrect password, restored and byte-compared the file successfully. Temporary repositories, Jobs, claims, PVs and namespaces were removed. Permanent target resources remain GitOps-only and deploy after merge. These checks prove target access/restore, not application backup consistency.

Rollback: revert the two Argo Application registrations to stop managing the target. Namespace, PVC and PV carry Argo `Prune=false,Delete=false` safeguards; keep them and NAS data until explicitly reviewed for removal. Reverting this PR must not erase backup repositories. Retain the NAS dataset regardless of claim lifecycle.

## Kestra / KubeVirt retirement

User approved retiring Kestra and the KubeVirt trial, including Manager and CDI, from infra-cluster. Read-only preflight found zero VirtualMachines, VirtualMachineInstances and DataVolumes. Kestra has `data-versitygw-0` and `kestra-postgres` PVCs; preserve both, their PVs and namespace. Preserve all involved namespaces and any PVCs as an additional safeguard. No NAS files, secrets in Doppler, physical node settings or unrelated workloads are deleted.

Before merging the removal PR, run `task infrastructure:prepare-infra-retirement`. It rechecks the absence of guests/imports, records a private resource/PVC inventory and checks retained backing volumes. It refuses cascading Application finalizers: these four Applications currently have none. Preparation is read-only against Kubernetes. The PR removes their Application registrations and source manifests. The parent has global `Prune=false`, so after merge run `task infrastructure:unregister-infra-retirement`: it requires Argo to mark each remaining registration `requiresPruning`, checks the saved infra cluster identity and absent cascading finalizers, then deletes only these four registrations with orphan propagation. Do not disable global prune safeguards or enable cascading deletion: that could delete Kestra's namespace and PVCs.

After the four child Applications disappear, run `task infrastructure:retire-infra`. It requires the saved inventory, verifies the same infra cluster and absent child Applications, rechecks guests/retention, then removes only inventoried resources in order: Manager, runtime CRs, operators, Kestra. It skips all namespaces, PVCs and PVs, waits for runtime CR finalizers while operators still run, waits for retired pods to disappear after controller deletion, and verifies the saved PVC bindings afterward. The task fails if runtime pods, KubeVirt/CDI CRDs or associated webhook configurations remain; inspect leftovers rather than force-removing finalizers. Retained namespaces/PVCs and PVs are intentional, not a failed uninstall.

Rollback: revert the removal commit and reconcile Argo. Retained namespaces and Kestra PVCs permit redeployment using the original names, but do not replace an application-consistent backup. Capture/export any Kestra flows worth keeping before final data deletion; this PR does not delete that data. Keep the private preflight inventory as incident/recovery evidence.

Pre-merge retirement evidence: the preparation task completed against live infra and saved both retained Kestra PVC bindings privately. Calling the removal task before merge refused at the first still-registered Application without deleting resources. An offline scenario using the captured inventory verified that namespace/PVC/PV deletes are skipped and both runtime CRs precede their operator deletions. Destructive live retirement is deliberately not exercised before review/merge.

Post-merge evidence (2026-10-29): both permanent Argo Applications are Synced/Healthy and both `backups/k8s-backup` claims are Bound. Their encrypted backup/check/restore probes passed and removed their test Jobs/repositories. The four retired Application registrations were removed without cascade because the parent's global `Prune=false` deliberately skipped them. Ordered live retirement completed: no remaining Kestra/KubeVirt runtime pods, KubeVirt/CDI CRDs or associated webhooks; both Kestra PVCs remain Bound to their original retained PVs. Kestra used its configured 360-second shutdown grace; the procedure now waits for pod deletion before checking completion and budgets at least the configured grace plus 60 seconds. Parent `apps` and all child Applications reported Healthy after convergence. These are target and retirement checks, not evidence of scheduled application backups.

### Live reconciliation (2026-11-09, issue #555)

Read-only check against infra-cluster, ~11 days after the retirement. Git
registrations being gone was not taken as proof; each item below was queried.

Removed (verified absent):

-   No Kestra, VersityGW, KubeVirt, CDI or Manager pods in any namespace.
-   No `*kubevirt*`/`*cdi*` CRDs, validating/mutating webhooks, APIServices,
    ClusterRoles/ClusterRoleBindings or PriorityClasses.
-   No Kestra/KubeVirt/CDI Argo Applications; all 56 Applications on the
    Argo controller (app-cluster) are Synced/Healthy.
-   No `DopplerSecret` CRs for Kestra/VersityGW remain in
    `doppler-operator-system`.
-   Namespaces have no `metadata.finalizers` and are `Active` (only the
    standard `spec.finalizers: [kubernetes]`), so nothing is stuck.

Operator-authorized cleanup (2026-11-09, done by the agent with the
operator's explicit approval; Kubernetes objects only, no Talos or node
changes, nothing in Doppler or on the NAS):

| Step          | Deleted / changed                                                                                                                                                                                                                                                  | Evidence                                                                                                                                                                                                                                |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Node residue  | 511 `*.node.kubevirt.io/*` labels on infra-cp-01 and 327 on infra-wk-01; annotations `kubevirt.io/heartbeat` and `kubevirt.io/ksm-handler-managed` on both; `devices.kubevirt.io/{kvm,tun,vhost-net,sev}` from `status.capacity` and `status.allocatable` on both. | After 20 s: 0 KubeVirt labels, annotations and extended resources on either node; both nodes `Ready`.                                                                                                                                   |
| Leases        | `kubevirt/{61e1d0f4.kubevirt.io,virt-controller,virt-operator}`, `cdi/{cdi-controller-leader-election-helper,cdi-operator-leader-election-helper}` (holders were long-gone pods).                                                                                  | Deleted; namespaces removed afterwards.                                                                                                                                                                                                 |
| Stale Secrets | `kestra/{kestra-basic-auth,kestra-homelab-ops,kestra-postgres,versitygw-root}`; Pulse `DopplerSecret`s `doppler-operator-system/{pulse-agent-token,pulse-secrets}` and their `monitoring/{pulse-agent-token,pulse-secrets}` Secrets.                               | Before deletion: no pod or workload template, ConfigMap (Backrest/app-protect config), Argo Application or Git manifest referenced them; none had owners or finalizers. Afterwards: none listed. The Doppler projects were not touched. |
| Namespaces    | `kubevirt`, `kubevirt-lab`, `kubevirt-manager`, `cdi`, `kestra`.                                                                                                                                                                                                   | All `NotFound`; no namespace `Terminating`. Both Kestra PVs are `Released` with `Retain`; local-path-provisioner logged no delete. All 56 Argo Applications Synced/Healthy afterwards.                                                  |

Not deleted (no approval): the two Kestra PV objects and their directories,
and the unrelated `Released` PV `pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542`
(`ai/litellm-postgres`, `Retain`).

Retained data recorded on 2026-11-09 before deleting the `kestra` namespace.
The 2026-11-11 live recheck confirmed the infra-cluster PVs remain `Released`
with `Retain`; no app-cluster PV is `Released`. See the current read-only
preflight and conditional deletion procedure below before any future cleanup.

| Former claim                | PV                                         | PV capacity | Node        | Directory (`hostPath`, `rancher.io/local-path`)                                                | Read-only size observation  |
| --------------------------- | ------------------------------------------ | ----------- | ----------- | ---------------------------------------------------------------------------------------------- | --------------------------- |
| `kestra/data-versitygw-0`   | `pvc-fd07c4d1-8b6e-41b4-b620-e7da2d24387b` | 20Gi        | infra-cp-01 | `/var/local-path-provisioner/pvc-fd07c4d1-8b6e-41b4-b620-e7da2d24387b_kestra_data-versitygw-0` | 255832 KiB (`du -sk`)       |
| `kestra/kestra-postgres`    | `pvc-f966ded9-9ade-46a9-a226-878444653d1d` | 10Gi        | infra-cp-01 | `/var/local-path-provisioner/pvc-f966ded9-9ade-46a9-a226-878444653d1d_kestra_kestra-postgres`  | Incomplete: `pg` unreadable |
| `ai/litellm-postgres` (old) | `pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542` | 10Gi        | infra-cp-01 | `/var/local-path-provisioner/pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542_ai_litellm-postgres`     | Incomplete: `pg` unreadable |

`du` was run read-only through the infra node-exporter pod's read-only
`/host` mount. PostgreSQL `pg` directories returned `Permission denied`; the
reported 4 KiB top-level entries are not a directory-size measurement. Do not
substitute PV capacity for used bytes. The exact used size of both PostgreSQL
directories is unknown.

The infra PV list contained exactly those three `Released` PVs at recheck; all
are `Retain`, `ReadWriteOnce`, with node affinity to `infra-cp-01`. The old
LiteLLM PV has no live claim: the current `ai/litellm-postgres` PVC is Bound to
different PV `pvc-70207c00-0e3b-4a13-b325-2bbb35f477f4`. However, LiteLLM and
its Backrest export are active, and the old PV remains an archival recovery
candidate. Kestra has no current PVC or workload consumer, but the existing
rollback instructions below still rebind these claims. No archive restore
validation was established by this recheck. Therefore **none of these three
PV/data pairs is approved for deletion by this change**.

Both Kestra PVs were `ReadWriteOnce`, StorageClass `local-path`. The PV UIDs of
the old claims equal the PV names after `pvc-`.

#### Live preflight and conditional deletion runbook

This is a review-gated runbook, not authorization to execute it. Deletion of a
PV object and its directory is irreversible. There is **no rollback** for
deleted data or Doppler keys; restore is possible only from a pre-existing
Backrest snapshot, if one exists and covers the exact data. Existing Backrest
coverage for these three directories has not been established. Decide on any
final archive/Backrest capture and verify its restore before a human approves
deletion.

Before each future deletion, use the infra kubeconfig explicitly and recheck
the exact PV name, phase, `Retain` policy, claimRef, capacity, hostPath,
nodeAffinity, live PVCs, pod/workload/Argo references, app-protect and Backrest
plans, and current directory identity/size. Stop if any field differs from
this record, if a consumer or rollback note remains, or if recovery evidence
is incomplete. Do not include the Freqtrade PV
`pvc-1b6eb81e-faec-4c9d-a3e3-b5505965345b` (#551).

For a human-approved candidate only:

1. Set the PV and exact directory values from that candidate's live PV spec;
   validate them manually against the table. Never use a wildcard.
2. Delete only that PV object using the infra kubeconfig. Confirm it is gone.
3. Start a short-lived helper pod pinned to the spec's node (`infra-cp-01` for
   the three recorded PVs). Mount only the parent
   `/var/local-path-provisioner`, at `/data`, using `hostPath.type: Directory`.
   Run `rm -rf -- /data/<exact-directory-basename-from-that-PV-spec>` and
   verify `/data/<exact-directory-basename>` is absent. Never mount a parent
   above `/var/local-path-provisioner`, run a glob, or remove that parent.
   The manifest must contain only this hostPath mount and the exact target
   command; do not reuse a helper with an unreviewed target.
4. Verify the directory is absent and delete the helper pod. Record the
   operator, time, PV, node, exact path and verification result.

Every `kubectl` command in that future procedure, including helper-pod apply,
logs and deletion, **MUST** use
`--kubeconfig /Users/fs/Documents/repositories/infrastructure/home-dc-kubernetes/.private/infra-cluster/kubeconfig`
(or `KUBECONFIG` set to that exact file). Never use the app-cluster
`kubeconfig`.

The following commands/manifests are templates for a future human-approved
run, not commands to execute in this change. Apply **one** candidate's
procedure only after its exact PV spec and approval have been rechecked. The
helper manifests are separate so each embeds one exact directory basename.

Set and retain the infra kubeconfig explicitly, then delete only the reviewed
PV object:

```sh
INFRA_KUBECONFIG=/Users/fs/Documents/repositories/infrastructure/home-dc-kubernetes/.private/infra-cluster/kubeconfig
kubectl --kubeconfig "$INFRA_KUBECONFIG" delete pv pvc-fd07c4d1-8b6e-41b4-b620-e7da2d24387b
```

For that PV only, save this manifest as `pv-cleanup.yaml`, then apply it,
inspect completion/logs, verify the exact path is absent and delete the pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
    name: pv-cleanup-fd07c4d1
    namespace: default
spec:
    restartPolicy: Never
    nodeSelector:
        kubernetes.io/hostname: infra-cp-01
    containers:
        - name: cleanup
          image: busybox:1.36.1
          command: ["sh", "-ec"]
          args:
              - test -d /data/pvc-fd07c4d1-8b6e-41b4-b620-e7da2d24387b_kestra_data-versitygw-0 && rm -rf -- /data/pvc-fd07c4d1-8b6e-41b4-b620-e7da2d24387b_kestra_data-versitygw-0 && test ! -e /data/pvc-fd07c4d1-8b6e-41b4-b620-e7da2d24387b_kestra_data-versitygw-0
          volumeMounts:
              - name: local-path-parent
                mountPath: /data
    volumes:
        - name: local-path-parent
          hostPath:
              path: /var/local-path-provisioner
              type: Directory
```

```sh
kubectl --kubeconfig "$INFRA_KUBECONFIG" apply -f pv-cleanup.yaml
kubectl --kubeconfig "$INFRA_KUBECONFIG" wait --for=jsonpath='{.status.phase}'=Succeeded pod/pv-cleanup-fd07c4d1 --timeout=120s
kubectl --kubeconfig "$INFRA_KUBECONFIG" logs pod/pv-cleanup-fd07c4d1
kubectl --kubeconfig "$INFRA_KUBECONFIG" delete pod pv-cleanup-fd07c4d1
```

For `pvc-f966ded9-9ade-46a9-a226-878444653d1d`, substitute that exact PV name
in the PV deletion command, and use this separately reviewed helper manifest:

```yaml
apiVersion: v1
kind: Pod
metadata:
    name: pv-cleanup-f966ded9
    namespace: default
spec:
    restartPolicy: Never
    nodeSelector:
        kubernetes.io/hostname: infra-cp-01
    containers:
        - name: cleanup
          image: busybox:1.36.1
          command: ["sh", "-ec"]
          args:
              - test -d /data/pvc-f966ded9-9ade-46a9-a226-878444653d1d_kestra_kestra-postgres && rm -rf -- /data/pvc-f966ded9-9ade-46a9-a226-878444653d1d_kestra_kestra-postgres && test ! -e /data/pvc-f966ded9-9ade-46a9-a226-878444653d1d_kestra_kestra-postgres
          volumeMounts:
              - name: local-path-parent
                mountPath: /data
    volumes:
        - name: local-path-parent
          hostPath:
              path: /var/local-path-provisioner
              type: Directory
```

Use `pv-cleanup-f966ded9` for the corresponding explicit
`kubectl --kubeconfig "$INFRA_KUBECONFIG" apply`, `wait`, `logs` and `delete
pod` commands. For `pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542`, use that exact
PV name in the deletion command and this separate helper:

```yaml
apiVersion: v1
kind: Pod
metadata:
    name: pv-cleanup-7f6beb16
    namespace: default
spec:
    restartPolicy: Never
    nodeSelector:
        kubernetes.io/hostname: infra-cp-01
    containers:
        - name: cleanup
          image: busybox:1.36.1
          command: ["sh", "-ec"]
          args:
              - test -d /data/pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542_ai_litellm-postgres && rm -rf -- /data/pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542_ai_litellm-postgres && test ! -e /data/pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542_ai_litellm-postgres
          volumeMounts:
              - name: local-path-parent
                mountPath: /data
    volumes:
        - name: local-path-parent
          hostPath:
              path: /var/local-path-provisioner
              type: Directory
```

Use `pv-cleanup-7f6beb16` for the corresponding explicit
`kubectl --kubeconfig "$INFRA_KUBECONFIG" apply`, `wait`, `logs` and `delete
pod` commands. Before applying any manifest, confirm the named PV has already
been deleted and revalidate the actual directory name from its recorded spec.

For the second PV, use this exact deletion command:

```sh
kubectl --kubeconfig "$INFRA_KUBECONFIG" delete pv pvc-f966ded9-9ade-46a9-a226-878444653d1d
```

Then, only after deleting that PV, apply its manifest and verify/remove its
helper:

```sh
kubectl --kubeconfig "$INFRA_KUBECONFIG" apply -f pv-cleanup.yaml
kubectl --kubeconfig "$INFRA_KUBECONFIG" wait --for=jsonpath='{.status.phase}'=Succeeded pod/pv-cleanup-f966ded9 --timeout=120s
kubectl --kubeconfig "$INFRA_KUBECONFIG" logs pod/pv-cleanup-f966ded9
kubectl --kubeconfig "$INFRA_KUBECONFIG" delete pod pv-cleanup-f966ded9
```

For the old LiteLLM PV, use this exact deletion command:

```sh
kubectl --kubeconfig "$INFRA_KUBECONFIG" delete pv pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542
```

Then, only after deleting that PV, apply its manifest and verify/remove its
helper:

```sh
kubectl --kubeconfig "$INFRA_KUBECONFIG" apply -f pv-cleanup.yaml
kubectl --kubeconfig "$INFRA_KUBECONFIG" wait --for=jsonpath='{.status.phase}'=Succeeded pod/pv-cleanup-7f6beb16 --timeout=120s
kubectl --kubeconfig "$INFRA_KUBECONFIG" logs pod/pv-cleanup-7f6beb16
kubectl --kubeconfig "$INFRA_KUBECONFIG" delete pod pv-cleanup-7f6beb16
```

Use the same exact command sequence for the first candidate with helper name
`pv-cleanup-fd07c4d1` shown above. These sequences are documentation only.
Do not execute them without the separate human decision and recovery gates.

Proposed directory basenames (not approved for deletion):

```text
pvc-fd07c4d1-8b6e-41b4-b620-e7da2d24387b_kestra_data-versitygw-0
pvc-f966ded9-9ade-46a9-a226-878444653d1d_kestra_kestra-postgres
pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542_ai_litellm-postgres
```

#### Rebinding a retained Kestra PV (rollback)

A `Released` PV keeps the deleted claim's UID in `spec.claimRef` and will not
bind until that UID is cleared. local-path-provisioner never removes a
`Retain` PV's directory.

```sh
export KUBECONFIG=.private/infra-cluster/kubeconfig
PV=pvc-f966ded9-9ade-46a9-a226-878444653d1d   # or pvc-fd07c4d1-… for VersityGW
kubectl get pv "$PV" -o jsonpath='{.spec.persistentVolumeReclaimPolicy} {.status.phase}{"\n"}'  # expect: Retain Released
kubectl create namespace kestra
# Keep claimRef namespace/name so only the original claim can bind; drop uid/resourceVersion.
kubectl patch pv "$PV" --type=merge -p '{"spec":{"claimRef":{"uid":null,"resourceVersion":null}}}'
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: kestra-postgres          # or data-versitygw-0
  namespace: kestra
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: local-path
  volumeName: pvc-f966ded9-9ade-46a9-a226-878444653d1d
  resources:
    requests:
      storage: 10Gi              # 20Gi for data-versitygw-0
YAML
kubectl -n kestra get pvc   # expect Bound to the same PV
```

The PV's node affinity pins any consumer to infra-cp-01. To read the data
without redeploying Kestra, bind the PVC as above and mount it read-only in a
throwaway pod; Talos has no host shell. Final data deletion (PV object and
directory) needs separate approval.

## Next actions

-   [x] Install retained NAS claims and verify encrypted target backup/restore on both clusters; move disposable smoke to non-root UID `1004`.
-   [x] Retire the approved Kestra/KubeVirt/CDI/Manager workloads while preserving the two Kestra claims.
-   [x] Remove retirement residue and the five namespaces, keeping both Kestra PVs `Retain`/`Released` (2026-11-09, #555).
-   [ ] Decide whether to retain or delete all three `Released` infra-cluster
        PVs and directories listed in the live preflight (separate approval,
        archive/restore evidence, exact directory sizes, and no remaining rollback
        references required first).
-   [x] Verify root-only squash, UID `1004` encrypted target backup/restore and unrelated UID `65534` write denial on both clusters.
-   [x] Deploy and verify the [Backrest replacement](backrest.md); complete database/original recovery checks and restore-gated legacy retirement on both clusters (2026-10-30).
-   [ ] Add and restore-test an independent offsite copy; the NAS target is not offsite protection.
