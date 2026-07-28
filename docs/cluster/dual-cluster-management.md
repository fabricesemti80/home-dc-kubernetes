# Dual Cluster Management

This repository now treats the Kubernetes estate as two clusters managed by one Argo CD hub.

| Cluster       | Argo name       | Kubeconfig                            | Role                                                |
| ------------- | --------------- | ------------------------------------- | --------------------------------------------------- |
| App cluster   | `app-cluster`   | `./kubeconfig`                        | General workloads and Argo CD hub                   |
| Infra cluster | `infra-cluster` | `./.private/infra-cluster/kubeconfig` | Small physical cluster for infrastructure workloads |

Argo CD runs on `app-cluster` and manages both clusters. Do not install a second Argo CD on `infra-cluster` unless this hub model is deliberately replaced.

## Lens

Lens can use one kubeconfig containing both contexts. Generate the local-only merged file:

```bash
task clusters:lens-kubeconfig
```

Add this file to Lens:

```text
.private/lens.kubeconfig
```

The file is ignored by Git and contains credentials. Regenerate it after either source kubeconfig changes.

Expected contexts:

```text
app-cluster
infra-cluster
```

The Lens kubeconfig is separate from the repo `./kubeconfig`. The repo kubeconfig keeps the `argocd` context for Argo CD CLI `--core` commands. The Lens kubeconfig keeps only cluster browsing contexts.

## Task Namespaces

Use cluster-explicit task names for new work:

```bash
task talos:app:generate-config
task talos:app:bootstrap
task talos:app:apply-node IP=...
task talos:app:upgrade-node IP=...

task talos:infra:bootstrap
task talos:infra:kubeconfig
task talos:infra:cilium
task talos:infra:status
task talos:infra:verify

task clusters:lens-kubeconfig
task clusters:status
```

Legacy app-cluster task names still exist for compatibility, but new docs should prefer the explicit `app` or `infra` names.

## Folder Boundaries

Current source layout:

-   `talos/app/`: app-cluster Talos source and generated app-cluster Talos config
-   `talos/infra/`: infra-cluster Talos source patches
-   `.private/infra-cluster/`: generated infra-cluster Talos config, talosconfig, and kubeconfig
-   `kubernetes/argo/apps/app-cluster/<namespace>/*.yaml`: Argo Applications targeting `app-cluster`
-   `kubernetes/argo/apps/infra-cluster/<namespace>/*.yaml`: Argo Applications targeting `infra-cluster`
-   `kubernetes/apps/app-cluster/<namespace>/<app>/`: app-cluster workload manifests and values
-   `kubernetes/apps/infra-cluster/<namespace>/<app>/`: infra-cluster workload manifests and values
-   `docs/INFRA_CLUSTER_BOOTSTRAP.md`: physical infra-cluster build runbook

Keep kubeconfigs, Talos generated configs, and private keys under `.private/` or ignored local files.

## Application Placement

For an app-cluster workload:

```yaml
destination:
    name: app-cluster
```

For an infra-cluster workload:

```yaml
destination:
    name: infra-cluster
```

Infra-cluster apps should start with small, dependency-light services. The Doppler operator and Reloader are good initial candidates because later infra workloads can reuse the same secret and reload patterns. Avoid moving DNS, monitoring, or storage until a simple app has synced and stayed healthy.

## Validation

```bash
task clusters:status
argocd app get reloader-infra --core
kubectl --kubeconfig .private/infra-cluster/kubeconfig get pods -A
```
