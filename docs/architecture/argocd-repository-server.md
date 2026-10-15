# Argo CD repository server startup resources

## Decision (2026-10-15)

The `gitops-tools` init container receives a 256 MiB request and 512 MiB limit. It copies the tool bundle into an `emptyDir` before the repository server starts; the prior 256 MiB limit OOM-killed the copy and left replacements in `Init:CrashLoopBackOff`.

Run two repository-server replicas and spread them across hostnames with
`maxSkew: 1`, `minDomains: 2`, and `DoNotSchedule`. Preferred anti-affinity
alone allowed both replicas onto `k8s-ctrl-03`, so a failure or drain of that
node could remove the manifest-generation service. With fewer than two eligible
nodes, the scheduler keeps the replicas on separate hostnames; if only one node
is eligible, one replica can remain Pending while the other serves requests.

Assumptions: eligible nodes have the standard `kubernetes.io/hostname` label,
the chart-generated pod selector identifies repo-server replicas, and two
eligible nodes are normally available for both replicas to run.

## Validation and rollback

After Argo syncs, confirm both `argocd-repo-server` pods are Ready on different
nodes and their `gitops-tools` init containers have no OOM kills. If the cluster
intentionally operates with one eligible node, expect one replica to remain
Pending until a second eligible node is available.
