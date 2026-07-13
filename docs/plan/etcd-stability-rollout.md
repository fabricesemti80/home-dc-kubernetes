# Etcd Stability And Talos Improvement Runbook

## Objective

Improve etcd stability on the existing Proxmox and Ceph-backed control planes without changing Terraform, VM hardware, network devices, or disk placement.

The mandatory change increases only the etcd election timeout. The Talos OS upgrade is optional in principle, but it is the recommended path because the repository now generates v1.13.4 machine configuration and the upgrade updates the kernel, container runtime, and etcd while preserving the deployed VM configuration.

## Target State

| Component             | Current | Target  | Scope                |
| --------------------- | ------- | ------- | -------------------- |
| Talos                 | v1.12.4 | v1.13.4 | Optional, in-place   |
| Intermediate Talos    | n/a     | v1.12.8 | Required upgrade hop |
| Kubernetes            | v1.35.1 | v1.35.1 | No change            |
| etcd election timeout | 1000 ms | 3000 ms | Mandatory            |
| etcd heartbeat        | 100 ms  | 100 ms  | No change            |
| etcd backend quota    | 2 GiB   | 2 GiB   | No change            |
| automatic defrag      | none    | none    | No scheduled job     |

## Measured Findings

-   Each control plane has 8 vCPU and 16 GiB RAM with low current utilization.
-   Inter-host RTT is below 0.5 ms.
-   Ceph reports about 10 ms OSD commit latency.
-   etcd logs show repeated 100-700 ms operations and delayed-heartbeat warnings attributed to slow disk.
-   Each etcd backend is only about 62-64 MB, with about 20 MB in use.

The Talos-only change cannot reduce storage latency. It can reduce unnecessary elections during short storage stalls. The optional Talos upgrade also moves etcd from v3.6.7 to v3.6.12.

## Safety Rules

-   Operate on exactly one control-plane node at a time.
-   Apply or upgrade etcd followers before the current leader.
-   Stop immediately if fewer than three healthy etcd members are visible before starting a node.
-   Continue only after the changed node is `Ready`, etcd is healthy, and Raft indexes converge.
-   Do not run `task tf:proxmox:apply`.
-   Do not run `task talos:upgrade-k8s` in this runbook.
-   Keep the snapshot and generated configuration outside Git.

## Phase 0: Prepare

1. Ensure the working tree is on the merged commit containing this runbook.
2. Install the final repository tools:

    ```bash
    talosctl version --client
    ```

    Expected final client: `v1.13.4`.

3. Confirm the repository targets Talos v1.13.4 and Kubernetes v1.35.1:

    ```bash
    yq -r '.talosVersion, .kubernetesVersion' talos/talenv.yaml
    ```

4. Confirm generated secrets and machine configs remain ignored:

    ```bash
    git status --short
    ```

## Phase 1: Capture Baseline

Record the output in the change log or terminal transcript:

```bash
kubectl get nodes -o wide
kubectl top nodes
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 version
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd status
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd members
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd alarm list
```

Also capture recent slow-operation and election warnings:

```bash
for ip in 10.0.40.90 10.0.40.91 10.0.40.92; do
  talosctl --talosconfig talos/clusterconfig/talosconfig \
    -n "$ip" logs etcd --tail 500 |
    rg 'leader failed|election|took too long|slow'
done
```

**Go gate:** three healthy non-learner members, no active etcd alarm, and all Kubernetes nodes `Ready`.

## Phase 2: Back Up

Take a fresh etcd snapshot:

```bash
mkdir -p backups/etcd
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90 etcd snapshot \
  backups/etcd/etcd-before-stability-$(date +%Y%m%d-%H%M%S).snapshot
```

The `backups/` path is ignored. Confirm:

```bash
git status --short
```

## Phase 3: Optional Talos v1.12.4 To v1.12.8

Choose one route before continuing:

-   **Route A, etcd-only:** skip Phases 3-5 and use the targeted patch command in Phase 6. This changes only `cluster.etcd.extraArgs.election-timeout` on the running v1.12.4 nodes.
-   **Route B, recommended:** complete Phases 3-5, then use the generated machine configuration in Phase 6. This upgrades Talos in place without changing Kubernetes or Proxmox resources.

Talos recommends using a client matching the currently running minor version and upgrading through the latest patch release of each intermediate minor.

Use a temporary v1.12.8 client without changing the repository's final v1.13.4 pin:

```bash
curl -fsSL -o /tmp/talosctl-v1.12.8 \
  https://github.com/siderolabs/talos/releases/download/v1.12.8/talosctl-linux-amd64
chmod +x /tmp/talosctl-v1.12.8
/tmp/talosctl-v1.12.8 version --client
```

Determine the current leader:

```bash
/tmp/talosctl-v1.12.8 --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd status
```

Upgrade both followers first, one at a time:

```bash
task talos:upgrade-node IP=<follower-ip> VERSION=v1.12.8
```

After each node:

```bash
/tmp/talosctl-v1.12.8 --talosconfig talos/clusterconfig/talosconfig \
  -n <node-ip> health
kubectl get nodes
```

Re-check leadership and upgrade the remaining controller last. Then verify all nodes report v1.12.8 and etcd is healthy.

**Stop gate:** do not begin v1.13.4 until all three nodes are v1.12.8 and healthy.

## Phase 4: Optional Talos v1.12.8 To v1.13.4

Use the repository-pinned client:

```bash
talosctl version --client
```

Expected: `v1.13.4`.

Repeat the same follower-first sequence:

```bash
task talos:upgrade-node IP=<follower-ip>
```

The omitted `VERSION` defaults to `talosVersion: v1.13.4`.

After each node:

```bash
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n <node-ip> health
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd status
kubectl get nodes
```

Re-check leadership before upgrading the final controller.

**Go gate:** all three nodes report v1.13.4, all are `Ready`, and all etcd members are healthy.

## Phase 5: Generate Final Machine Configuration For Route B

Generate configuration only after all nodes are on v1.13.4:

```bash
task --yes configure
task talos:generate-config
```

Check that the generated control-plane configuration keeps Kubernetes at v1.35.1 and uses the v1.13.4 installer:

```bash
rg 'kubelet:v1.35.1|kube-apiserver:v1.35.1|installer:v1.13.4' \
  talos/clusterconfig/controlplane.yaml
```

Confirm generated files remain ignored:

```bash
git status --short
```

## Phase 6: Apply Etcd Election Timeout

Applying machine configuration is separate from upgrading the Talos image. Use only the route selected in Phase 3.

Determine the current leader, then apply both followers first:

```bash
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd status
```

For **Route A**, use the v1.12.8 client to apply only the etcd timeout:

```bash
/tmp/talosctl-v1.12.8 --talosconfig talos/clusterconfig/talosconfig \
  -n <follower-ip> patch machineconfig --mode=auto \
  --patch '{"cluster":{"etcd":{"extraArgs":{"election-timeout":"3000"}}}}'
```

For **Route B**, apply the generated v1.13.4 machine configuration:

```bash
task talos:apply-node IP=<follower-ip>
```

After either command:

```bash
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n <follower-ip> health
```

Repeat the selected route for the second follower. Re-check leadership and apply the remaining controller last.

Verify the effective configuration:

```bash
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 get etcdconfig -o yaml
```

Expected extra arguments:

```yaml
listen-metrics-urls: http://0.0.0.0:2381
election-timeout: "3000"
```

## Phase 7: Validate And Observe

Immediately validate:

```bash
talosctl --talosconfig talos/clusterconfig/talosconfig health
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd status
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd alarm list
kubectl get nodes
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
```

Observe for at least 24 hours. Compare with the baseline:

-   Leader changes and Raft term growth.
-   Delayed-heartbeat warnings.
-   Slow etcd transactions.
-   Kubernetes API responsiveness.
-   Node readiness and control-plane component restarts.

Success means election churn is reduced without worse API responsiveness. Slow transactions may remain because the underlying storage is unchanged.

## Phase 8: Conditional Defragmentation

Do not run defrag on a fixed schedule. Check backend size first:

```bash
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n 10.0.40.90,10.0.40.91,10.0.40.92 etcd status
```

Run defrag only when database size is materially larger than in-use size and a maintenance window is available:

```bash
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n <follower-ip> etcd defrag
```

Confirm health, repeat for the second follower, then run on the leader last. Defrag is resource-intensive and can block the member while it runs.

## Rollback

### Etcd Configuration

For Route A, remove only the added argument, follower-first:

```bash
/tmp/talosctl-v1.12.8 --talosconfig talos/clusterconfig/talosconfig \
  -n <node-ip> patch machineconfig --mode=auto \
  --patch '[{"op":"remove","path":"/cluster/etcd/extraArgs/election-timeout"}]'
```

For Route B, remove `election-timeout` from the controller template, regenerate configuration, and apply follower-first using the Phase 6 sequence.

### Talos OS

Roll back exactly one node at a time:

```bash
talosctl --talosconfig talos/clusterconfig/talosconfig \
  -n <node-ip> rollback
```

Wait for the node and etcd member to recover before another rollback. If automatic rollback already occurred after a failed boot, verify the running version and cluster health before proceeding.

### Disaster Recovery

If quorum is lost, stop routine changes. Preserve the snapshot and current machine configuration. Restore etcd only through the documented Talos recovery procedure; do not independently restore the same snapshot onto multiple members.

## Deferred Work

The following changes may improve request latency but are intentionally outside this PR:

-   Lower-latency control-plane VM storage.
-   Moving write-heavy workloads to worker nodes.
-   Kubernetes v1.35.1 to v1.36.1 upgrade.
-   Proxmox, Terraform, VM hardware, network, or disk changes.
