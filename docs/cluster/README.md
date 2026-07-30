# Cluster Documentation

This section covers the Talos, Argo CD, and Kubernetes-side configuration that now lives directly in this repository.

## Core Documents

-   [Architecture Plan](../architecture/ARCHITECTURE_PLAN.md)
-   [Argo Cluster Migration](../architecture/ARGO_CLUSTER_MIGRATION.md)
-   [Phase 0/1 Blueprint](../architecture/PHASE_0_1_BLUEPRINT.md)
-   [Implementation Decisions](../architecture/IMPLEMENTATION_DECISIONS.md)

## Day-to-Day Guides

-   [Root rebuild guide](../../README.md)
-   [Dual Cluster Management](dual-cluster-management.md)
-   [Secret Strategy](secret-strategy.md)
-   [Adding Applications](adding-applications.md)
-   [App Catalog](app-catalog.md)
-   [Domain Configuration](domains.md)
-   [Database Backups](database-backups.md)
-   [Troubleshooting](../operations/troubleshooting.md)

## Source of Truth

-   `kubernetes/`: Argo application definitions and workload manifests
-   `bootstrap/`: bootstrap ordering and initial Helmfile installs
-   `talos/app/`: app-cluster Talos configuration and patches
-   `talos/infra/`: infra-cluster Talos source patches
-   `.private/infra-cluster/`: local-only infra-cluster generated Talos config and kubeconfig
-   `clusters/`: lightweight cluster ownership notes
-   `infra/terraform_proxmox/`: imported cluster OpenTofu stack
-   `cluster.yaml` and `nodes.yaml`: local template inputs still used by the current config-generation workflow
