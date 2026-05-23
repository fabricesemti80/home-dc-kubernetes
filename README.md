# project-homelab

This repository is the main source of truth for the homelab. It manages:

-   the host-level Docker stack under `infra/docker/`
-   the imported Talos / Argo cluster workflow at the repo root
-   the OpenTofu stacks under `infra/terraform_*`

## Start Here

-   Documentation hub: [docs/README.md](docs/README.md)
-   Architecture plan: [docs/architecture/ARCHITECTURE_PLAN.md](docs/architecture/ARCHITECTURE_PLAN.md)
-   Cluster migration notes: [docs/architecture/ARGO_CLUSTER_MIGRATION.md](docs/architecture/ARGO_CLUSTER_MIGRATION.md)
-   Agent guidance: [AGENTS.md](AGENTS.md)

## Documentation Map

-   Docker stack: [docs/infrastructure/docker-stack.md](docs/infrastructure/docker-stack.md)
-   OpenTofu setup: [docs/infrastructure/terraform.md](docs/infrastructure/terraform.md)
-   Talos / Argo / cluster docs: [docs/cluster/README.md](docs/cluster/README.md)
-   Storage docs: [docs/storage/overview.md](docs/storage/overview.md)
-   Troubleshooting: [docs/operations/troubleshooting.md](docs/operations/troubleshooting.md)

## Core Tasks

Ensure `mise` is installed, then:

```bash
mise install
task deps
```

Common workflows:

```bash
# Host-level Docker stack
task stack:deploy

# OpenTofu stacks
task tf:init
task tf:plan

# Talos / cluster bootstrap flow
task talos:genconfig
task talos:bootstrap
task apps:bootstrap
task verify:cluster
```

Task execution now lives in structured files under `.taskfiles/`. `mise.toml` remains the source of truth for tool installation and environment setup.

## Repository Notes

-   `kubernetes/` and `bootstrap/` are the active GitOps source for cluster apps.
-   `talos/`, `cluster.yaml`, and `nodes.yaml` are still part of the active Talos config-generation workflow.
-   Older placeholder folders were removed from Git where they no longer backed any active workflow.
