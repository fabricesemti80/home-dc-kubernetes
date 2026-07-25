# App Cluster

`app-cluster` is the existing Talos VM cluster on Proxmox. It hosts Argo CD and general workloads.

App-cluster Talos source lives in `talos/app/`. Use the explicit wrapper tasks:

```bash
task talos:app:generate-config
task talos:app:bootstrap
```
