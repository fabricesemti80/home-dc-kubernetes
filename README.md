# home-dc-kubernetes

This repository is the main source of truth for the homelab. It manages:

-   the imported Talos / Argo cluster workflow at the repo root
-   the Kubernetes/Talos OpenTofu stacks under `infra/terraform_*`

Host-level Docker services moved to `/Users/fs/Documents/repositories/infrastructure/home-dc-docker`.

## Start Here

-   Documentation hub: [docs/README.md](docs/README.md)
-   Architecture plan: [docs/architecture/ARCHITECTURE_PLAN.md](docs/architecture/ARCHITECTURE_PLAN.md)
-   Cluster migration notes: [docs/architecture/ARGO_CLUSTER_MIGRATION.md](docs/architecture/ARGO_CLUSTER_MIGRATION.md)
-   Agent guidance: [AGENTS.md](AGENTS.md)

## Documentation Map

-   OpenTofu setup: [docs/infrastructure/terraform.md](docs/infrastructure/terraform.md)
-   Talos / Argo / cluster docs: [docs/cluster/README.md](docs/cluster/README.md)
-   Storage docs: [docs/storage/overview.md](docs/storage/overview.md)
-   Troubleshooting: [docs/operations/troubleshooting.md](docs/operations/troubleshooting.md)

## Core Tasks

Use the devcontainer, then:

```bash
task deps
```

Common workflows:

```bash
# OpenTofu stacks
task tf:init
task tf:plan

# Talos / cluster bootstrap flow
task talos:genconfig
task talos:bootstrap
task apps:bootstrap
task verify:cluster
```

Task execution lives in structured files under `.taskfiles/`. Tooling is defined in `.devcontainer/` for repeatable local or Codespaces-style shells.

## Repository Notes

-   `kubernetes/` and `bootstrap/` are the active GitOps source for cluster apps.
-   `talos/`, `cluster.yaml`, and `nodes.yaml` are still part of the active Talos config-generation workflow.
-   Host-level Docker services are intentionally managed outside this repo.
-   Older placeholder folders were removed from Git where they no longer backed any active workflow.
