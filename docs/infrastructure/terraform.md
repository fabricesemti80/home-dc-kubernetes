# OpenTofu Setup

This repository keeps OpenTofu stacks under `infra/` so provider state and lifecycle can be handled independently.

## Stack Layout

-   `infra/terraform_proxmox/`: Proxmox VMs and Talos cluster infrastructure
-   `infra/terraform_service_hosts/`: standalone service guests and tailnet policy
-   `infra/terraform_cloudflare/`: Kubernetes Cloudflare tunnel, DNS, Access policies, and tunnel credentials
-   `infra/terraform_localdns/`: Kubernetes local DNS infrastructure

## Inputs and Local State

-   `infra/terraform_proxmox/*.auto.tfvars` holds local cluster-specific inputs and remains gitignored
-   `infra/terraform_service_hosts/terraform.tfstate` is copied locally from `/Users/fs/Documents/repositories/infrastructure/home-dc-service-hosts/terraform/terraform.tfstate` during migration and remains gitignored
-   `nodes.yaml` is still updated from Terraform outputs for the Talos workflow
-   local state is kept in the repo working copy for now and must be treated as operator-local secret material
-   `.terraform/`, `.terraform.lock.hcl`, `*.tfstate`, `*.tfvars`, `*.auto.tfvars`, and `tfplan*` are ignored across all stack directories

## Common Commands

```bash
task tf:init
task tf:plan
task tf:apply
```

Execution order:

-   `task tf:init` initializes Proxmox/Talos, service hosts, Cloudflare, then local DNS
-   `task tf:plan` plans the same order
-   `task tf:apply` applies the same order
-   `task tf:destroy` runs the reverse order so Proxmox VMs are last

Each stack also has a scoped task path:

```bash
task tf:proxmox:plan
task tf:service-hosts:plan
task tf:cloudflare:plan
task tf:localdns:plan
```

## Migration Notes

-   Proxmox resource addresses remain unchanged, especially `module.talos.*`, so existing VMs stay attached to their current state.
-   The former mixed root `terraform/` state was split locally into `infra/terraform_proxmox/terraform.tfstate` and `infra/terraform_cloudflare/terraform.tfstate`.
-   The service-hosts state is not committed. Copy it once from the old repo before the first plan:

```bash
cp /Users/fs/Documents/repositories/infrastructure/home-dc-service-hosts/terraform/terraform.tfstate \
  infra/terraform_service_hosts/terraform.tfstate
tofu -chdir=infra/terraform_service_hosts state rm \
  module.docker_svc_0.proxmox_virtual_environment_vm.this \
  proxmox_virtual_environment_file.docker_svc_0_guest_agent
```

-   Create `infra/terraform_service_hosts/proxmox.auto.tfvars` locally with `proxmox_endpoint`, `proxmox_insecure`, `proxmox_token_id`, `proxmox_token_secret`, and `root_ssh_public_keys`.
-   Docker-specific Cloudflare and local DNS resources moved to `/Users/fs/Documents/repositories/infrastructure/home-DC-docker`.
-   Stale copied root outputs should be pruned by a scoped plan/apply after a stack split so each stack only reports its own outputs.
-   Rollback is a directory/state-file move back to the previous layout before applying changes; no remote resources are changed by the split itself.

## Related Documents

-   [Architecture Plan](../architecture/ARCHITECTURE_PLAN.md)
-   [Argo Cluster Migration](../architecture/ARGO_CLUSTER_MIGRATION.md)
-   [Cluster Docs Overview](../cluster/README.md)
