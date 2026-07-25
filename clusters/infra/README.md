# Infra Cluster

`infra-cluster` is the physical mini-PC Talos cluster.

Local generated credentials and machine configs live under:

```text
.private/infra-cluster/
```

Use the explicit wrapper tasks:

```bash
task talos:infra:kubeconfig
task talos:infra:cilium
task talos:infra:verify
```
