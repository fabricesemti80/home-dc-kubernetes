# Argo CD repository server startup resources

## Decision

The `gitops-tools` init container receives a 256 MiB request and 512 MiB limit. It copies the tool bundle into an `emptyDir` before the repository server starts; the prior 256 MiB limit OOM-killed the copy and left replacements in `Init:CrashLoopBackOff`.

## Validation and rollback

After Argo syncs, confirm both `argocd-repo-server` pods are Ready and their `gitops-tools` init containers have no OOM kills. Revert the resource change only after the tool bundle is reduced below the lower limit.
