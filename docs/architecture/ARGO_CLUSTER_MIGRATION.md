# Argo Cluster Relocation

## Goal

Relocate the existing Talos/Argo cluster workflow from `home-argo-cluster-2025` into `project-homelab` without destroying the old repo, without recreating the VMs, and without forcing the worker nodes back online.

## What Was Imported

-   Tracked cluster workspace files were merged into the `project-homelab` repo root.
-   Local-only runtime files were copied into the new workspace and remain gitignored.
-   The current OpenTofu state was copied into `infra/terraform_proxmox/terraform.tfstate`.
-   Argo bootstrap manifests now point to `https://github.com/fabricesemti80/project-homelab.git`.
-   Argo application paths now target the root-level `kubernetes/...` paths in this repo.
-   The encrypted Argo repository secret was re-encrypted with the new repo URL.

## Important Constraint

The imported Terraform module originally forced every Talos VM to `started = true`. That would have powered the workers back on during the first apply from the new repo. The imported workspace now supports a per-node `started` flag so worker VMs can remain provisioned but powered off.

## Current Steady State

-   Argo CD now points at `project-homelab`.
-   The active Talos cluster is intentionally reduced to the three control-plane nodes.
-   Legacy worker VMs are treated as rollback capacity only and are not part of the committed Talos node inventory.

## Assumptions

-   The control-plane-only topology is sufficient for current workloads.
-   Worker VM definitions may still exist in Terraform or Proxmox while Talos no longer targets them.
-   Removing workers from Talos config is safer than leaving drained `NotReady` nodes referenced indefinitely, because daemonset-based apps otherwise remain `Progressing`.

## Recommended Cutover Sequence

1. Push `project-homelab` with the imported cluster workspace to GitHub.
2. In `infra/terraform_proxmox/nodes.auto.tfvars`, keep worker nodes `started = false` and control-plane nodes `true` unless you are also removing the VM definitions in the same change.
3. Run `task tf:init`.
4. Run `task tf:plan` and confirm the plan is limited to the repo/path-related changes you expect.
5. Power on only the control-plane VMs if they are currently off.
6. Verify Talos and Kubernetes health from the imported workspace.
7. Apply the Argo bootstrap resources from the imported workspace so the cluster pulls from `project-homelab`.
8. Remove the workers from `nodes.yaml` and regenerate Talos cluster config once you decide the steady state is control-plane-only.
9. Leave the worker VMs powered off, or remove them from Terraform later as a separate change.

## Validation

-   `task tf:plan`
-   `kubectl get nodes -o wide`
-   `talosctl --talosconfig talos/clusterconfig/talosconfig health`
-   `kubectl get applications -n argo-system`
-   `task sync-argo-bootstrap`

## Security Notes

-   No secrets were added to Git; copied runtime files stay ignored by the root `.gitignore`.
-   The imported workspace still uses the existing age recipient and Doppler project references.
-   If the GitHub deploy key is scoped to the old repository only, add the same public key to `project-homelab` before switching Argo over.

## Rollback

-   Keep using `home-argo-cluster-2025` as the operator workspace.
-   Reapply the old bootstrap manifests to point Argo back at the old repository.
-   Remove the imported workspace later once the new repo has proven stable.
-   Restore worker entries in `nodes.yaml` and regenerate Talos config if you need to bring workers back into service.
