# AGENTS.md

## Purpose

This repository captures the design and implementation plan for a personal homelab.
All automation, IaC, and documentation should optimize for **repeatability**, **security**, and **clear rollback paths**.
This repository is the main deployment home for the Talos clusters, Kubernetes resources, and homelab applications.

## Working rules for agents

1. **Plan before build**: update architecture/design docs before introducing new infrastructure code.
2. **Never commit secrets**: API keys, tokens, private keys, kubeconfigs, `.envrc`, generated Docker runtime files, and `.env` files must stay out of Git.
3. **Small, reversible changes**: keep PRs scoped; include migration/rollback notes for impactful changes.
4. **Document assumptions**: every design decision should list assumptions and validation checks.
5. **Use explicit environments**: `dev`, `stage`, and `prod` (or `lab`) should be modeled separately.
6. **Branch policy**: minor fixes may be made directly on `main`; larger or risky changes need a separate branch and PR.

## Repository conventions

-   High-level architecture documents live under `docs/architecture/`.
-   Implementation task breakdowns live under `docs/plan/`.
-   Scripts should be idempotent where practical.
-   Prefer Markdown checklists for progress tracking.
-   Kubernetes resources must remain under `kubernetes/`, `bootstrap/`, `talos/`, and Kubernetes-specific Terraform stacks in this repo.
-   Originally bootstrapped from [ajaykumar4/cluster-template](https://github.com/ajaykumar4/cluster-template) and evolved into a dual-cluster architecture.

## Kubernetes App Conventions

### Structure

-   All apps should follow the established cluster-aware directory structure:
    -   `kubernetes/apps/app-cluster/<namespace>/<app>/` for app-cluster workloads
    -   `kubernetes/apps/infra-cluster/<namespace>/<app>/` for infra-cluster workloads
-   Corresponding Argo Applications live under: `kubernetes/argo/apps/<cluster>/<namespace>/<app>.yaml`
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
