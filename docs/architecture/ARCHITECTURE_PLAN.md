# 🏛️ Homelab Architecture Plan

## 🎯 Objective

Operate the Talos/Kubernetes homelab from this repository as the active deployment home for applications and infrastructure services.

## 🌱 Lineage & Origin

This codebase was originally bootstrapped using [ajaykumar4/cluster-template](https://github.com/ajaykumar4/cluster-template) (utilizing Talos Linux, Argo CD, and `bjw-s/app-template` Helm chart patterns). It has since been customized into a **dual-cluster operational topology** managed by a single central Argo CD hub.

## 🏗️ Active Structure

```mermaid
flowchart TD
    subgraph Git["Git Repository"]
        Manifests[Kubernetes Manifests]
        TF[OpenTofu Stacks]
    end
    subgraph App["app-cluster Proxmox VMs"]
        ArgoCD[Argo CD Hub]
        Apps[Application Workloads]
    end
    subgraph Infra["infra-cluster Physical Mini PCs"]
        Core[Core Infra Services]
    end
    Git -->|GitOps| ArgoCD
    ArgoCD -->|Manages| Apps
    ArgoCD -->|Manages| Core
    TF -->|Provisions| App
    TF -->|Provisions| Infra
```

-   `app-cluster`: Primary application cluster running on Proxmox Talos VMs, hosting general workloads and the central Argo CD hub.
-   `infra-cluster`: Physical mini-PC infrastructure cluster running core baseline services (`pulse-infra`, `kestra-infra`, `reloader-infra`).
-   `infra/terraform_proxmox/`: Proxmox VMs and Talos cluster infrastructure.
-   `infra/terraform_cloudflare/`: Kubernetes Cloudflare tunnel, DNS, Access resources, and tunnel credentials.
-   `infra/terraform_localdns/`: Kubernetes local DNS OpenTofu stack.
-   `talos/`, `kubernetes/`, `bootstrap/`, and `.taskfiles/`: Talos, Argo CD, and Kubernetes workspace migrated from the legacy cluster repo.
-   `kubernetes/apps/app-cluster/default/`: lightweight default-namespace apps used for baseline GitOps validation and small utility workloads.
-   `kubernetes/apps/app-cluster/` & `kubernetes/apps/infra-cluster/`: Workload manifests separated by destination cluster.
-   `kubernetes/argo/apps/app-cluster/` & `kubernetes/argo/apps/infra-cluster/`: Argo CD Applications separated by destination cluster.

## 🚧 Current Migration Direction

-   `home-dc-kubernetes` is the active source of truth for the cluster.
-   Argo CD targets this repository.
-   The active Talos cluster is modeled as three control-plane nodes only.
-   Historical worker VMs remain infrastructure artifacts for rollback or later reuse, but are no longer part of the committed Talos node inventory.
-   Former host-level Docker services are being retired or migrated into Kubernetes.

> **Supersedes:** [Argo Cluster Relocation](../archive/ARGO_CLUSTER_MIGRATION.md) (2026-03). The migration from the legacy `home-argo-cluster-2025` repository into `home-dc-kubernetes` has been completed; the topology and source-of-truth statements above reflect the steady state after that cutover.

## 🤔 Assumptions

-   The imported cluster should keep using its current Proxmox IDs, node IPs, Talos secrets, and Terraform state.
-   Secrets and runtime artifacts remain local-only and gitignored.
-   Doppler project names and existing external integrations can stay unchanged during the repo migration.
-   Removing workers from Talos configuration does not require deleting the underlying VM definitions on the same change.
-   Splitting OpenTofu directories must preserve Kubernetes resource addresses so existing tunnels, DNS records, and Access apps are not recreated.

## ✅ Validation Checks

-   `task tf:init`
-   `task tf:plan`
-   `task tf:proxmox:plan`
-   `task tf:cloudflare:plan`
-   `task tf:localdns:plan`
-   `kubectl get nodes`
-   `talosctl --talosconfig talos/app/clusterconfig/talosconfig config info`
-   `task sync-argo-bootstrap`

## ↩️ Rollback

**Pre-cutover** (before Argo CD has been switched to this repository):

-   Discard the new workspace and continue operating from the original repository.

**Post-cutover** (Argo CD already targets `home-dc-kubernetes`):

1.  Reapply the bootstrap manifests from the `home-argo-cluster-2025` repository to repoint Argo CD back at that repository.
2.  Reconcile Argo CD so it restores the `home-argo-cluster-2025` desired state.
3.  If the old repo's workspace is no longer available, restore its bootstrap manifests from Git history or backups.
4.  Restore any copied local-only runtime files from the old workspace if the new one is discarded.
5.  Reintroduce worker nodes by restoring them to `nodes.yaml`, regenerating `talos/app/talconfig.yaml`, and re-running Talos config generation.
6.  If the OpenTofu stack split needs to be reversed before apply, move the directories and local state files back to the previous layout.
