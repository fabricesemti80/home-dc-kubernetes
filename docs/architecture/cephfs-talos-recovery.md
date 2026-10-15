# CephFS on Talos after maintenance

## Decision (2026-10-14)

Use FUSE for CephFS mounts on the app cluster. Talos currently lacks the `ceph` kernel module. New PVs receive `mounter: fuse` through the StorageClass; existing PVs require a separate Retain rebind with the same Ceph volume handle. StorageClass parameters and PV CSI source fields cannot be patched in place.

Credentials belong only in the SOPS-encrypted `csi-cephfs-secret`, referenced by the StorageClass. The credential generation source is Doppler `home-dc-kubernetes/apps` `CEPH_KEYRING`. The current key is for `client.admin`, so both CSI identities must be `admin`. `csiConfig` holds only the public cluster ID and monitor addresses because the chart serializes it into a ConfigMap.

CSI node plugins use `OnDelete`: a Helm sync does not automatically replace plugins serving mounted application volumes. An operator must deliberately replace each plugin after reviewing the change. The provisioner remains a single replica, matching the current lab architecture; this limits provisioning availability if that pod fails.

## Assumptions and security

These choices apply to the current Talos nodes and Ceph cluster. Recheck kernel capabilities before changing mount mode. Keep the PV reclaim policy `Retain`; no recovery procedure may delete CephFS subvolumes. The admin credential is broader than a dedicated CSI identity and was duplicated in a ConfigMap; audit other clients and rotate it in a controlled follow-up rather than during a recovery merge.

## Validation

CI rejects a non-FUSE or non-Retain StorageClass and credentials in CSI ConfigMap settings. Before maintenance, review active PV mount modes and compare the scoped Doppler and encrypted CSI keys with the live Ceph identity without printing values. After recovery, require Bound PVCs, Ready pods, ready Service endpoints and application health. For Jellyfin, both startup and readiness require the `/health` body `Healthy`; HTTP status alone is insufficient.

## Rollback

Revert chart values or probe changes through GitOps after inspecting affected workloads. Do not revert repaired PVs to kernel mounting on these nodes. If rebinding is necessary, stop all volume consumers, save the current objects, retain the original Ceph handles and Retain policy, then verify each new PVC UID matches its PV claim reference before restoring workloads. A StorageClass change needs a reviewed recreation of the class while preserving all existing volumes.

## Disconnected client recovery

When a CephFS consumer reports `Transport endpoint is not connected` while
CephFS and its MDS remain available, test a fresh client mount before restarting
stateful consumers. Change the pod-template
`kubectl.kubernetes.io/restartedAt` annotation on the non-critical
`storage/nginx-test` Deployment through GitOps. Keep its existing PVC, PV, CephFS
handle and `Retain` policy unchanged. Use the `Recreate` Deployment strategy so
the old pod unmounts its node's CSI staging path before the replacement starts.
Verify the replacement pod can read the test page and that
`df -T /usr/share/nginx/html` reports CephFS. If the pilot fails, stop and
preserve all claims; do not restart databases or mass-roll CSI plugins. If it
succeeds, recover affected applications one at a time through
reviewed pod-template changes, checking database logs, PVC binding, service
endpoints and application health after each restart. This remounts the client
but does not repair Ceph redundancy; keep the cluster degraded until the
missing host/OSD is recovered.

Assumptions: the active MDS and placement groups remain available for I/O, the
pilot PVC contains disposable test data, and restarting one test pod is safe.
Before restarting any database, verify its backup or account for PostgreSQL
crash recovery on the existing retained CephFS volume. Rollback by reverting the
annotation through GitOps; the PVC and data remain unchanged.

## Next actions

-   [ ] Review the 12 unused legacy PVs before any new consumer mounts them.
-   [ ] Audit all consumers of the admin key and perform a controlled credential rotation.
-   [ ] Verify a CephFS backup restore.
-   [ ] Add Kubernetes/application readiness verification to Kestra using an explicitly scoped credential; the existing flow verifies host/Ceph/guest state only.

The [incident report](../operations/2026-10-14-cephfs-mount-outage.md) records the live recovery and remaining limitations.
