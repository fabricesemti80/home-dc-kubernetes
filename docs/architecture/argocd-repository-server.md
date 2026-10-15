# Argo CD repository server startup resources

## Decision

The `gitops-tools` init container receives a 256 MiB request and 512 MiB limit. It copies the tool bundle into an `emptyDir` before the repository server starts; the prior 256 MiB limit OOM-killed the copy and left replacements in `Init:CrashLoopBackOff`.

Run two repository-server replicas and spread them across hostnames with
`maxSkew: 1` and `DoNotSchedule`. Preferred anti-affinity alone allowed both
replicas onto `k8s-ctrl-03`, so a failure or drain of that node could remove the
manifest-generation service. With fewer than two eligible nodes, one replica may
remain Pending while the other stays available.

## Validation and rollback

After Argo syncs, confirm both `argocd-repo-server` pods are Ready on different
nodes and their `gitops-tools` init containers have no OOM kills. Revert the
spread constraint if the cluster intentionally has fewer than two eligible nodes.
