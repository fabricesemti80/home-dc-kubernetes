# 📚 Cluster Documentation

This section covers the Talos, Argo CD, and Kubernetes-side configuration that now lives directly in this repository.

## 📌 Core Documents

-   [Installation & Deployment Guide](installation.md)
-   [Architecture Plan](../architecture/ARCHITECTURE_PLAN.md)
-   [App-cluster standalone migration](../plan/app-cluster-standalone-refactor.md)
-   [Implementation Decisions](../architecture/IMPLEMENTATION_DECISIONS.md)

## 📌 Day-to-Day Guides

-   [Root rebuild guide](../../README.md)
-   [Dual Cluster Management](dual-cluster-management.md)
-   [Secret Strategy](secret-strategy.md)
-   [Adding Applications](adding-applications.md)
-   [App Catalog](app-catalog.md)
-   [Domain Configuration](domains.md)
-   [Database Backups](database-backups.md)
-   [Troubleshooting](../operations/troubleshooting.md)

## 📌 Source of Truth

-   `kubernetes/`: Argo application definitions and workload manifests
-   `bootstrap/`: bootstrap ordering and initial Helmfile installs
-   `talos/app/`: app-cluster Talos configuration and patches
-   `talos/infra/`: infra-cluster Talos source patches
-   `.private/infra-cluster/`: local-only infra-cluster generated Talos config and kubeconfig
-   `clusters/`: lightweight cluster ownership notes
-   `../home-dc-proxmox/` and `../home-dc-terraform/`: host and guest infrastructure management, outside this repository
-   `cluster.yaml` and `nodes.yaml`: local template inputs still used by the current config-generation workflow
