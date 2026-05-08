# AGENTS.md

## Purpose

This repository captures the design and implementation plan for a personal homelab.
All automation, IaC, and documentation should optimize for **repeatability**, **security**, and **clear rollback paths**.
This repository is also the main deployment home for the Talos cluster and the host-level Docker services that support it.

## Working rules for agents

1. **Plan before build**: update architecture/design docs before introducing new infrastructure code.
2. **Never commit secrets**: API keys, tokens, private keys, kubeconfigs, `.envrc`, generated Docker runtime files, and `.env` files must stay out of Git.
3. **Small, reversible changes**: keep PRs scoped; include migration/rollback notes for impactful changes.
4. **Document assumptions**: every design decision should list assumptions and validation checks.
5. **Use explicit environments**: `dev`, `stage`, and `prod` (or `lab`) should be modeled separately.

## Repository conventions

-   High-level architecture documents live under `docs/architecture/`.
-   Implementation task breakdowns live under `docs/plan/`.
-   Scripts should be idempotent where practical.
-   Prefer Markdown checklists for progress tracking.
-   Host-level Docker services live under `infra/docker/`, not in NixOS modules.
-   Each Docker service should have its own subdirectory and be included from `infra/docker/docker-compose.yml`.
-   Rendered Docker runtime config belongs in `infra/docker/runtime/` and must remain ignored.
-   Local source secret material belongs in `infra/docker/secrets/` and must remain ignored.
-   The root `.envrc` is the local source for Docker deployment secrets.

## Docker Deployment Rules

-   Use `task stack:render` before validating Compose config.
-   Use `task stack:deploy` from this repo checkout to deploy the Docker stack to `morpheus` over SSH.
-   The default Docker deployment target is `fs@10.0.40.19:/opt/project-homelab/infra/docker`; override it only intentionally.
-   Omni is intentionally not part of the Docker deployment; use Terraform/Talos-native flows for cluster provisioning.

## Kubernetes App Conventions

### Structure
-   All apps should follow the established directory structure: `kubernetes/apps/<category>/<app>/`
-   Each app should have: `values.yaml`, `kustomization.yaml`, and `config/` subdirectory
-   Use the app-template chart pattern for new apps

### Storage Standards

#### Configuration Storage
-   **Default**: Use `storageClass: cephfs` for all config/configMaps PVCs
-   This applies to all namespaces unless explicitly justified otherwise
-   Example pattern:
    ```yaml
    persistence:
      config:
        type: persistentVolumeClaim
        accessMode: ReadWriteMany
        storageClass: cephfs
        size: 2Gi
    ```

#### Permanent Storage (Media/Data)
-   **Default**: Use the established `media-library-pvc` (NFS share) for all permanent data
-   The NFS share is at `10.0.40.2:/media` (managed in jellyfin app)
-   **Never** create new PVs with `Delete` reclaim policy - use `Retain` only
-   Use `existingClaim: media-library-pvc` for any app requiring media storage, regardless of namespace
-   Example pattern:
    ```yaml
    persistence:
      media:
        enabled: true
        existingClaim: media-library-pvc
        globalMounts:
          - path: /media
      downloads:
        enabled: true
        existingClaim: media-library-pvc
        globalMounts:
          - path: /downloads
            subPath: downloads/complete
    ```

**CONFIRMATION**: Currently, all media apps (jellyfin, radarr, sonarr, qbittorrent, sabnzbd, immich, prowlarr, jellyseerr) use:
-   `storageClass: cephfs` for config
-   `existingClaim: media-library-pvc` (NFS) for media/downloads

## Definition of done (for infra tasks)

-   Architecture or design doc updated.
-   Security impact considered (network, secrets, access control, backups).
-   Validation steps included (lint/plan/test/deploy checks).
-   Rollback approach documented.
