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

## Secrets and environment variables inventory

[`docs/secrets-and-env-vars.md`](docs/secrets-and-env-vars.md) is the authoritative inventory of every secret and environment variable in this repository.

-   Update it **in the same change** whenever you add, rename, remove or move any of the following: a `DopplerSecret` or one of its keys/`processors`; a `*.sops.yaml` file or its keys; a Doppler project/config or operator token; a template secret input in `cluster.schema.cue`; a local identity file; or an environment variable read by a Taskfile, script, `flake.nix` or workflow.
-   Retiring an app means moving its keys to the "Retained but unused" note, or deleting them there once they're removed from Doppler.
-   Mark Doppler cross-project references with their source project/config. When a shared value changes (`TUNNEL_*`, `PVE_MONITORING_TOKEN_SECRET`, `PBS_MONITORING_TOKEN_SECRET`, `MONITORING_HW_*`), update the source repository's `docs/secrets-and-env-vars.md` as well (`home-dc-terraform`, `home-dc-proxmox`).
-   Record names, locations, writers, readers and purpose only. Never write secret values into the file, a commit, a log or chat.
-   Before finishing, check for drift: `grep -rl "kind: DopplerSecret" kubernetes`, `find . -name "*.sops.yaml"` and `grep -rnE "os\.environ|getenv|\\$\{?[A-Z_]{4,}" scripts hack .taskfiles`. Every result must be reflected in the inventory.

## Documentation, README and diagrams

Keep the documentation in step with the code **in the same change**.

-   Update [`README.md`](README.md) (stages, prerequisites, commands) and the matching file under `docs/` (design with assumptions, validation and rollback) whenever behaviour, commands, prerequisites, hostnames, ports or ownership change.
-   Update `docs/cluster/app-catalog.md` for every app added, removed or renamed (hostname, cluster, namespace, storage class).
-   Update the diagrams whenever the topology changes: [`docs/architecture.svg`](docs/architecture.svg) and any diagram in the affected architecture doc (clusters and components, storage backends, ingress and DNS, secret flows, dependencies on the other `home-dc-*` repositories). If you cannot update a diagram, name the stale one in the PR instead of leaving it silently wrong.
-   Update the secrets and environment variables inventory (previous section). Follow-up work is tracked as [GitHub issues](https://github.com/fabricesemti80/home-dc-kubernetes/issues) (order and gates: the "Roadmap: order of work and gates" issue): close or comment on the issue you finished, and open one for any follow-up you leave behind.
-   Before finishing, search for stale references to anything you renamed or removed (hostnames, tasks, paths).

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

### Exposure and DNS

-   **Internal by default.** Every new app with a web UI or API gets an internal route: an `HTTPRoute` (`config/http-route-internal.yaml`) attached to `envoy-internal` (`sectionName: http`) with hostname `<app>.krapulax.home` and the annotation `external-dns.alpha.kubernetes.io/target: kubernetes.krapulax.home`. The Technitium ExternalDNS instance (zone `krapulax.home`, `--gateway-name=envoy-internal`) publishes the record automatically once the route exists: no manual DNS record, and no Cloudflare record. Copy an existing route (`storage/backrest`, `storage/longhorn`, the media apps). After the sync, `dig +short <app>.krapulax.home` must equal `kubernetes.krapulax.home` (`10.0.40.102`).
-   **External exposure is opt-in and must be asked about.** Before adding any public route (a Cloudflare tunnel hostname under `krapulax.dev`, an external `HTTPRoute`, a Cloudflare Access application or any `home-dc-terraform` Cloudflare change), **ask the user whether the app needs external exposure**. Never assume it, and say which access policy would apply (`bypass` or Access with allowed emails). The default answer is no.
-   An app with no web service (operator, CronJob, controller) needs no route; say so in the design doc.
-   If an app's UI has no authentication (for example Longhorn), say so in the design doc and keep it internal. Do not offer external exposure for it without an authentication layer.
-   Record the hostname in `docs/cluster/app-catalog.md` and in the app's architecture doc.
-   **Homepage.** Every app with a UI should appear on the Homepage dashboard. Public apps (a `.dev` route) get `gethomepage.dev/*` annotations generated by `scripts/ensure-homepage-annotations.py` (a workflow runs it on `main`). Internal-only apps are not discovered: add a static entry to that script (see `STATIC_APP_STORAGE` for Longhorn and `STATIC_APP_TRADING` for Freqtrade: icon, internal `http://<app>.krapulax.home` href, one-line description, group `App Cluster - <area>`), run the script, and commit the regenerated `services.yaml` and `settings.yaml` under `kubernetes/apps/app-cluster/web/homepage/config/`.

### Storage Standards

#### Configuration Storage

-   **Default**: Use an explicit `existingClaim` pointing at a Longhorn PVC (`storageClassName: longhorn`, declared in the app's `config/pvc-<name>-longhorn.yaml`) for config, state, caches and queues on the app-cluster. Declare the claim yourself with `Prune=false,Delete=false`: an app-template `persistence` entry with `storageClass` would be rendered with the chart and removed with it.
-   Longhorn (`longhorn` StorageClass, the cluster default class) replicates each volume three times across the workers (single host failure domain, not a backup; see `docs/operations/longhorn.md`). All app-cluster app claims run on it since 2026-11-10. `local-path` remains only for the retained pre-migration claims (rollback copies) and for the physical infra-cluster. Always set `storageClass` explicitly: leaving it empty silently selects Longhorn.
-   Use `ReadWriteOnce` access mode and a `Retain` reclaim policy so PVC deletion preserves the underlying PV data for restore. A ReadWriteOnce volume attaches to one node at a time: single-replica workloads use `strategy: Recreate`, and `app-protect` entries use `selector` (follow the pod), not `node`.
-   Keep workloads that share a volume co-located; node pins that exist only for hardware (the Jellyfin GPU) stay.
-   Moving an existing app between classes is never an in-place change: follow `docs/operations/local-path-to-longhorn.md` (offline copy with `scripts/longhorn-copy-offline.sh`, one app per PR, old claim retained).
-   Example pattern (claim in `config/pvc-config-longhorn.yaml`):
    ```yaml
    persistence:
        config:
            type: persistentVolumeClaim
            existingClaim: myapp-longhorn
    ```

#### Shared Media and Downloads

-   **Media/downloads only**: Use the established `media-library-pvc` NFS share at `10.0.40.2:/media` for large shared files. Database and app configuration state stay on backed-up Longhorn volumes.
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

**TARGET STATE** (reached 2026-11-10): App-cluster config/state, cache and queue PVCs use Longhorn (`ReadWriteOnce`, `Retain`). Apps that consume shared media or downloads also mount `media-library-pvc` (NFS). The separate physical infra-cluster's storage is unchanged. The old local-path claims were deleted on 2026-11-10 (see issue #578); rollback for an app is its Backrest restore.

### Backup Enrollment

-   Apps with config/state on a local volume are **protected by default**: add an entry to `kubernetes/apps/<cluster>/storage/app-protect/values.yaml` plus an `app-<name>` plan in the cluster's `backrest/config/config.json`. See `docs/operations/backrest.md#protecting-and-opting-out-apps`.
-   Apps that do not need backup (test/throwaway, caches, stateless, Git-reconstructable) are opted out explicitly with `protect: false` on their `app-protect` entry and no Backrest plan. Never leave a stateful app unlisted.

## Definition of done (for infra tasks)

-   Architecture or design doc updated.
-   Security impact considered (network, secrets, access control, backups).
-   Validation steps included (lint/plan/test/deploy checks).
-   Rollback approach documented.
