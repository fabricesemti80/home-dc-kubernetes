# Homelab Architecture Plan

## Objective

Operate the Talos/Kubernetes homelab from this repository while Docker-host services live in their own management repository.

## Active Structure

-   `infra/terraform_proxmox/`: Proxmox VMs and Talos cluster infrastructure.
-   `infra/terraform_cloudflare/`: Kubernetes Cloudflare tunnel, DNS, Access resources, and tunnel credentials.
-   `infra/terraform_localdns/`: Kubernetes local DNS OpenTofu stack.
-   `talos/`, `kubernetes/`, `bootstrap/`, and `.taskfiles/`: Talos, Argo CD, and Kubernetes workspace migrated from the legacy cluster repo.
-   `kubernetes/apps/default/`: lightweight default-namespace apps used for baseline GitOps validation and small utility workloads.
-   `/Users/fs/Documents/repositories/infrastructure/home-DC-docker`: host-level Docker Compose, Docker Cloudflare resources, and Docker local DNS records.

## Current Migration Direction

-   `project-homelab` becomes the main source of truth.
-   The old `home-argo-cluster-2025` repo stays intact during transition.
-   Argo CD will be repointed to `project-homelab`.
-   The active Talos cluster is now modeled as three control-plane nodes only.
-   Historical worker VMs remain infrastructure artifacts for rollback or later reuse, but are no longer part of the committed Talos node inventory.
-   Host-level Docker services are moving to `home-DC-docker`; Kubernetes resources must be unaffected by this split.

## Assumptions

-   The imported cluster should keep using its current Proxmox IDs, node IPs, Talos secrets, and Terraform state.
-   Secrets and runtime artifacts remain local-only and gitignored.
-   Doppler project names and existing external integrations can stay unchanged during the repo migration.
-   Docker secrets may later move to a dedicated Doppler project/config after the repository cutover validates.
-   Removing workers from Talos configuration does not require deleting the underlying VM definitions on the same change.
-   Splitting OpenTofu directories must preserve Kubernetes resource addresses so existing tunnels, DNS records, and Access apps are not recreated.

## Validation Checks

-   `task tf:init`
-   `task tf:plan`
-   `task tf:proxmox:plan`
-   `task tf:cloudflare:plan`
-   `task tf:localdns:plan`
-   `kubectl get nodes`
-   `talosctl --talosconfig talos/clusterconfig/talosconfig config info`
-   `task sync-argo-bootstrap`

## Rollback

-   Repoint Argo CD back to `home-argo-cluster-2025`.
-   Continue operating from the original repo because its state and files remain untouched.
-   Continue operating Docker from the previous repo revision until the Docker repo is validated and deployed.
-   Restore any copied local-only runtime files from the old workspace if the new one is discarded.
-   Reintroduce worker nodes by restoring them to `nodes.yaml`, regenerating `talos/talconfig.yaml`, and re-running Talos config generation.
-   If the OpenTofu stack split needs to be reversed before apply, move the directories and local state files back to the previous layout.
