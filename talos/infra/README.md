# ☸️ Infra Cluster Talos

`infra-cluster` is generated outside Git into `.private/infra-cluster/`.

Committed files in this directory are source inputs only:

-   `cilium-patch.yaml`
-   `controlplane-patch.yaml`
-   `worker-patch.yaml`

Local generated files:

```text
.private/infra-cluster/generated/controlplane.yaml
.private/infra-cluster/generated/worker.yaml
.private/infra-cluster/generated/talosconfig
.private/infra-cluster/kubeconfig
```

Use:

```bash
task talos:infra:kubeconfig
task talos:infra:status
task talos:infra:verify
```
