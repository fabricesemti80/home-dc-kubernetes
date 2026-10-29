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
-   Kubernetes resources and configuration belong under `kubernetes/`, `bootstrap/`, and `talos/`; host and guest infrastructure are managed in the standalone infrastructure repositories.
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

-   **Default**: Use `storageClass: local-path` for all config/configMaps PVCs on the app-cluster.
-   Volumes are node-local worker user volumes provisioned by the `local-path-provisioner`; they are bound to the worker that first consumes them.
-   Use `ReadWriteOnce` access mode and a `Retain` reclaim policy so PVC deletion preserves the underlying PV data for restore.
-   Keep workloads that share a volume co-located on the same worker; do not move a pod to another worker without restoring its data.
-   This applies to all namespaces unless explicitly justified otherwise.
-   Example pattern:
    ```yaml
    persistence:
        config:
            type: persistentVolumeClaim
            accessMode: ReadWriteOnce
            storageClass: local-path
            size: 2Gi
    ```

#### Shared Media and Downloads

-   **Media/downloads only**: Use the established `media-library-pvc` NFS share at `10.0.40.2:/media` for large shared files. Database and app configuration state stay on backed-up local worker volumes.
-   **Never** create new PVs with `Delete` reclaim policy; use `Retain`.
-   A PVC is namespace-scoped: provision a corresponding retained NFS claim in each namespace that needs media access.
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

**TARGET STATE**: App-cluster media app config/state PVCs use `local-path` (`ReadWriteOnce`, `Retain`). Apps that consume shared media or downloads also mount `media-library-pvc` (NFS). The separate physical infra-cluster's storage is unchanged.

## Definition of done (for infra tasks)

-   Architecture or design doc updated.
-   Security impact considered (network, secrets, access control, backups).
-   Validation steps included (lint/plan/test/deploy checks).
-   Rollback approach documented.
