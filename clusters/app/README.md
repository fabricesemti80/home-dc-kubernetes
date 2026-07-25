# App Cluster

`app-cluster` is the existing Talos VM cluster on Proxmox. It hosts Argo CD and general workloads.

Current app-cluster Talos source remains in `talos/` for compatibility with the existing bootstrap flow. Use the explicit wrapper tasks for new docs:

```bash
task talos:app:generate-config
task talos:app:bootstrap
```
