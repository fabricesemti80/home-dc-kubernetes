# Homelab Architecture Plan

## Objective

Operate the homelab from a single primary repository while keeping changes small, reversible, and explicit about security and rollback.

## Active Structure

-   `infra/docker/`: host-level Docker services that support the homelab outside Kubernetes.
-   `infra/terraform_proxmox/`: Proxmox VMs and Talos cluster infrastructure.
-   `infra/terraform_cloudflare/`: Kubernetes and host-level Cloudflare tunnels, DNS, and Access resources.
-   `infra/terraform_localdns/`: reserved local DNS OpenTofu stack.
-   `talos/`, `kubernetes/`, `bootstrap/`, and `.taskfiles/`: Talos, Argo CD, and Kubernetes workspace migrated from the legacy cluster repo.
-   `kubernetes/apps/default/`: lightweight default-namespace apps used for baseline GitOps validation and small utility workloads.

## Current Migration Direction

-   `project-homelab` becomes the main source of truth.
-   The old `home-argo-cluster-2025` repo stays intact during transition.
-   Argo CD will be repointed to `project-homelab`.
-   The active Talos cluster is now modeled as three control-plane nodes only.
-   Historical worker VMs remain infrastructure artifacts for rollback or later reuse, but are no longer part of the committed Talos node inventory.

## Assumptions

-   The imported cluster should keep using its current Proxmox IDs, node IPs, Talos secrets, and Terraform state.
-   Secrets and runtime artifacts remain local-only and gitignored.
-   Doppler project names and existing external integrations can stay unchanged during the repo migration.
-   Removing workers from Talos configuration does not require deleting the underlying VM definitions on the same change.
-   Splitting OpenTofu directories must preserve Proxmox state addresses so existing VMs are not recreated.

## Validation Checks

-   `task tf:init`
-   `task tf:plan`
-   `task tf:proxmox:plan`
-   `kubectl get nodes`
-   `talosctl --talosconfig talos/clusterconfig/talosconfig config info`
-   `task sync-argo-bootstrap`

## Rollback

-   Repoint Argo CD back to `home-argo-cluster-2025`.
-   Continue operating from the original repo because its state and files remain untouched.
-   Restore any copied local-only runtime files from the old workspace if the new one is discarded.
-   Reintroduce worker nodes by restoring them to `nodes.yaml`, regenerating `talos/talconfig.yaml`, and re-running Talos config generation.
-   If the OpenTofu stack split needs to be reversed before apply, move the directories and local state files back to the previous layout.
