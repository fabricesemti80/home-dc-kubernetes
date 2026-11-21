# Argo CD controller resources

## Repository server placement (2026-10-15)

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

## Application controller memory (2026-10-15)

Raise the application-controller memory limit from 1 GiB to 2 GiB. One
controller replica was OOM-killed during application reconciliation while the
other was handling slow comparisons. The replicas request 512 MiB, so this adds
limit headroom without increasing their scheduling reservation.

Assumptions: each app-cluster node has enough spare memory for the controller's
2 GiB ceiling, and the two replicas remain independently schedulable.

After Argo syncs, confirm both controller replicas are Ready, restart counts stay
stable through a full reconciliation, and the root Application's reconciled
revision advances. If OOM kills continue or memory approaches 2 GiB, inspect
controller workload and concurrency before raising the limit further. Roll back
by restoring the 1 GiB limit if node memory pressure appears.

## Dex replica count (2026-11-21)

The Argo CD chart 10.18.2 rejects `dex.replicas: 2` without a persistent,
shared Dex storage backend. The live deployment has one ready replica and the
live Dex configuration does not specify a storage backend. Set the desired
replica count to one rather than introduce a database for a small installation.
This restores manifest generation without changing the live replica count.

Assumption: the existing single Dex replica is sufficient; Dex is not highly
available and an outage can interrupt SSO login. Existing Argo sessions and
the remaining components are not made highly available by this change.
Validate a rendered chart with the actual encrypted values, then after sync
check the `argo` Application is Synced and Healthy, Dex is Ready, and the
configured sign-in flow works. If Dex is unavailable or SSO is disrupted,
restore the last working chart and values together; reverting the replica count
alone would recreate the chart rendering error. A future two-replica setup needs
a supported shared storage backend and a separate security and recovery design.
