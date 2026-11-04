# 📋 TODO

This document captures architectural and automation work that is intentionally deferred. Items should be converted into implementation pull requests when time permits.

## 🐙 Adapt Argo CD repo-server to the new gitops-tools plugin layout

`ghcr.io/ajaykumar4/gitops-tools` is pinned to `2026.8.0` and held in Renovate. Version `2026.11.0` renamed the helm-secrets plugin directories (`helm-plugins/helm-secrets/...` became `secrets/`, `secrets-getter/` and `secrets-post-renderer/`, helm-secrets 4.7.10), so the init script in `kubernetes/apps/app-cluster/argo-system/argo-cd/values.yaml` fails with `cp: can't stat .../helm-secrets-cli/plugin.yaml` and `argocd-repo-server` never starts (incident on 2026-11-02; details in `docs/architecture/IMPLEMENTATION_DECISIONS.md`).

### 🔹 Completion criteria

-   adapt the init script for the new layout; in a local simulation, deleting the `cp .../helm-secrets-cli/plugin.yaml` line was enough for the `secrets`, `secrets-getter` and `secrets-post-renderer` plugins to load under `quay.io/argoproj/argocd:v3.5.6` (Helm 4.2.1);
-   prove an end-to-end `helm secrets` decrypt of a real `*.sops.yaml` in a scratch repo-server before touching production;
-   bump the tag, remove the Renovate hold, and confirm `argo` and `apps` stay Healthy;
-   consider grouping `gitops-tools` with the Argo CD chart in Renovate so they are not bumped independently.

## ☸️ Upgrade Talos to 1.14 and plan the Kubernetes version path

Renovate proposed kubelet `v1.37.2`, but Talos 1.13 supports Kubernetes 1.31 to 1.36 only: `talosctl upgrade-k8s --to 1.37.2` is refused ("version of Kubernetes 1.37.2 is too new to be used with Talos 1.13.8"; the 1.13 client says `unsupported upgrade path 1.36->1.37`). Talos 1.13 is also out of community support now that 1.14 is released (latest `v1.14.5`). Current state: app-cluster Talos `v1.13.8` with Kubernetes `v1.36.3` (one control plane, so one etcd member), infra-cluster Talos `v1.13.6` with Kubernetes `v1.36.2`.

Talos 1.14 supports Kubernetes 1.33 to 1.37, but the platform does not yet: Cilium 1.20 (latest `v1.20.4`), cert-manager 1.21 (latest `v1.21.3`) and Envoy Gateway 1.9 document support through 1.36 only. Stay on Kubernetes 1.36.x (a `--to 1.36.6` dry run passes on both clusters) and revisit 1.37 once those releases add it.

### 🔹 Completion criteria

-   fix the repo before upgrading the app-cluster configuration: `talhelper` (3.1.13 in the dev shell, 3.1.17 in nixpkgs) cannot generate Talos 1.14.5 configs. The five conflicts are `.machine.network.nameservers`, `.cluster.apiServer`, `.cluster.controllerManager`, `.cluster.scheduler` and `.cluster.proxy` (migrate to `ResolverConfig`, `KubeAPIServerConfig`, `KubeControllerManagerConfig`, `KubeSchedulerConfig` and `KubeProxyConfig`), and the `$patch: delete` of `cluster.apiServer.admissionControl` in `talos/app/patches/controller/cluster.yaml` fails under the 1.14 contract. The OS upgrade itself does not need this, because existing `v1alpha1` configs keep working on 1.14 (documented, not yet tested here);
-   the infra-cluster installs from `ghcr.io/siderolabs/installer`, which has no 1.14 tag. Use `factory.talos.dev/metal-installer/<schematic-id>:v1.14.5` (the app-cluster nodes already use the Image Factory with schematic `3765...` for plain nodes and `af8eb8...` for the GPU worker, which carries the NVIDIA LTS extensions) and update `machine.install.image` for the infra-cluster as well;
-   fix the Renovate hints in `talos/app/talenv.yaml`: `talosVersion` tracks the ghcr installer and so can never see 1.14 (switch to `siderolabs/talos` GitHub releases), and add an upper bound below 1.37 for `kubernetesVersion` until the platform supports it;
-   upgrade the dev shell (`talosctl` 1.14.5 is in nixpkgs-unstable; the lock pins 1.13.5) after the node upgrades, and note that `talosctl upgrade-k8s` rewrites live component images, so keep `kubernetesVersion` in `talenv.yaml` in step;
-   upgrade Talos one node at a time with an etcd snapshot first: workers, then the GPU worker (verify the NVIDIA driver and a Jellyfin transcode), then the control plane (the API is unavailable while the single control plane reboots). On the infra-cluster confirm both Technitium instances are Ready between nodes. Roll back with `talosctl rollback`;
-   then run `talosctl upgrade-k8s --to 1.36.x` with the 1.14 client, using `--dry-run` first.

## 📈 Collect per-pod resource usage and right-size memory limits

Container metrics (cAdvisor) and kubelet volume metrics are not collected in either cluster because the Talos kubelet serving certificates are not signed by the cluster CA, and the monitoring stack deliberately does not skip TLS verification (see `docs/architecture/victoriametrics.md`). Without per-pod usage, limits cannot be lowered safely: on 2026-11-03 `k8s-wrkr-03` had about 150% memory limits (running pods only) while the node itself used 16-25% of its memory.

### 🔹 Completion criteria

-   establish a verified kubelet scrape path (trusted serving certificates or an authenticated proxy with RBAC), without `insecureSkipVerify`;
-   re-vendor the Kubernetes dashboard (Grafana 15661) so its cAdvisor panels show data, and re-check the pruned panels;
-   review the largest memory limits against measured usage; set limits close to requests only where usage supports it;
-   revisit the Argo CD dashboard (14584) separately: Argo CD v3.5.6 exposed no `argocd_app_*` series on 2026-11-02.

## 💾 Test Proxmox CSI volumes for pods that need to move between workers

Most app volumes are `local-path` and bound to the worker that first used them, which blocks rebalancing. The Proxmox CSI plugin may allow a volume on a local ZFS pool to detach from one worker VM and attach to another on the same Proxmox host; that is community-reported only and is not yet proven here. Per `home-dc-terraform`'s `nodes.auto.tfvars` the worker disks currently sit on `local-hdd`, the old 4 TB HDD, so a `local-nvme` StorageClass would also take load off that drive.

### 🔹 Completion criteria

-   create a scoped Proxmox API token for the plugin (Doppler, plus `docs/secrets-and-env-vars.md`);
-   install the plugin with a `local-nvme` StorageClass and the node topology labels it needs;
-   run a throwaway PVC test: write data, cordon the node, recreate the pod on another worker, confirm the data and the attach/detach time;
-   confirm how Proxmox VM backups treat the attached CSI disks, and keep Backrest as the real backup;
-   if the test fails, drop the plan and reconsider (the decision depends on this test).

## 🚚 Move stateful pods off `k8s-wrkr-03`

Nine pods on `k8s-wrkr-03` are tied to node-local volumes. The largest are `immich-machine-learning` (1 GiB requested) and `sabnzbd` (512 MiB, after its memory fix); the rest are small. Moving one means restoring its data onto another worker's volume and changing its `nodeSelector`.

### 🔹 Completion criteria

-   do this after the Proxmox CSI test above, or by restoring from a fresh Backrest snapshot onto a new `local-path` volume on the target worker;
-   move one app per change, keep the old volume (`Retain`) until the app is verified, and document rollback;
-   re-check node requests with the corrected dashboard (`docs/architecture/workload-placement.md`) before and after.

## 🐘 Upgrade the Immich database from PostgreSQL 14 (final release 2026-11-12)

`kubernetes/apps/app-cluster/media/immich/values.yaml` runs `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`. PostgreSQL 14's final release is **2026-11-12** (postgresql.org versioning policy, checked 2026-11-04). Renovate proposes `16-vectorchord0.4.3-pgvectors0.2.0`, but a major-version tag bump cannot start on the existing data directory (`immich-postgres-data`), so it must not be merged as a plain image update.

### 🔹 Completion criteria

-   take a fresh logical export with the `immich-db` Backrest plan and prove a restore into a scratch PostgreSQL 16 instance of the same image family;
-   follow Immich's supported upgrade path for the VectorChord image and check the extension versions after the restore (`vchord`, `vector`);
-   run the cutover in a window: stop Immich, restore into a new volume, switch the image, verify search, ML jobs and the external-library scan, keep the old volume (`Retain`) until verified;
-   document rollback (old image and old volume) and update `docs/cluster/database-backups.md`.

## 🎞️ Plan the Jellyfin 12 upgrade

Jellyfin is pinned to `lscr.io/linuxserver/jellyfin:10.11.11`; upstream is at 12.4 (linuxserver `latest` carries `12.4ubu2604-ls58`). Direct upgrades from 10.11.x are supported, but the 12.0 release notes say the database changes prevent rolling back without a full restore, that all non-built-in plugins should be removed first, that a full library scan is required afterwards, and that legacy `/emby/*` and `/mediabrowser/*` routes and legacy authorization were removed (old third-party clients may stop working).

### 🔹 Completion criteria

-   take a Backrest snapshot of `/config` and test the migration on a copy of the config volume first (as done for Seerr), including the NVIDIA hardware transcoding settings on the GPU worker;
-   check client compatibility (the apps and TVs in use) and the Seerr, Sonarr and Radarr integrations against the 12.x API;
-   run it in a maintenance window, then a full library scan, and document the restore path.

## ☁️ Validate ExternalDNS upgrades before re-enabling Renovate

ExternalDNS chart `1.22.0` changed Cloudflare Tunnel HTTPRoute reconciliation: it attempted to publish proxied A records for the private Envoy address (`10.0.40.103`) instead of the configured tunnel CNAME targets. Cloudflare rejected those records and withdrew public `*.krapulax.dev` DNS during sync.

### 🔹 Completion criteria

-   reproduce and resolve the `1.22.0` reconciliation behavior in a non-production zone or cluster;
-   confirm HTTPRoute records remain CNAMEs to `external-apps.krapulax.dev` or `external-infra.krapulax.dev`;
-   validate both public DNS and HTTPS after upgrade;
-   remove the ExternalDNS Renovate hold only after the validation succeeds.

## 🔧 Create GitHub Actions for Taskfile tasks that do not need to be manual

Review the repository Taskfile targets and identify deterministic tasks that should run automatically in GitHub Actions rather than relying on a developer to remember them.

Candidate categories include:

-   generated configuration and documentation;
-   formatting and linting;
-   Kubernetes manifest validation;
-   Helm and Kustomize rendering checks;
-   drift detection;
-   repository consistency checks.

### 🔹 Completion criteria

-   classify relevant Taskfile targets as manual, local helper, validation, or automation;
-   create focused GitHub Actions for tasks that are safe and useful to automate;
-   avoid duplicating task logic inside workflow YAML where the workflow can invoke the existing Taskfile target;
-   document any tasks that must remain manual and why.

## ☸️ Separate app-cluster and infra-cluster folder structure [COMPLETED]

_Status: Completed in PR #210 (canary) and PR #211 (full migration)._

Refactored the Kubernetes repository layout so resources targeting `app-cluster` and `infra-cluster` are explicitly separated under:

-   `kubernetes/apps/app-cluster/...` & `kubernetes/apps/infra-cluster/...`
-   `kubernetes/argo/apps/app-cluster/...` & `kubernetes/argo/apps/infra-cluster/...`

### 🔹 Completion criteria

-   [x] define and document the target folder convention;
-   [x] migrate resources without changing their effective runtime configuration;
-   [x] update Argo CD Application and ApplicationSet source paths;
-   [x] update scripts, validation, documentation, and generators that reference the old paths;
-   [x] verify both clusters reconcile successfully after migration.
-   [ ] add validation that prevents new app manifests from using the legacy mixed folders.

## ☸️ Separate app-cluster and infra-cluster DNS validation

Complete validation and ownership checks for DNS records split between the application and infrastructure clusters.

Public services use canonical cluster endpoints:

```text
external-apps.krapulax.dev  -> application-cluster Cloudflare Tunnel
external-infra.krapulax.dev -> infrastructure-cluster Cloudflare Tunnel
```

Service records should continue pointing to the appropriate cluster endpoint rather than directly referencing tunnel UUIDs or ambiguous legacy aliases.

The design should also define ownership of internal DNS records and which cluster or controller is authoritative for each DNS zone.

### 🔹 Completion criteria

-   document internal DNS ownership boundaries;
-   add validation that prevents new records from bypassing the canonical endpoints.

## ☸️ Separate app-cluster and infra-cluster Doppler configs

Split shared Doppler configuration into independent config boundaries for the application and infrastructure clusters.

This should reduce secret exposure, clarify ownership, and allow credentials and service tokens to be rotated independently.

The chosen naming model is:

```text
home-dc-kubernetes/apps
home-dc-kubernetes/infra
```

Canary and full migration PRs should move DopplerSecret manifests and local Doppler CLI tasks to these configs.

### 🔹 Completion criteria

-   inventory existing secrets and classify them by cluster and workload;
-   create separate Doppler projects or configurations with least-privilege access;
-   issue independent operator or service tokens for each cluster;
-   migrate `DopplerSecret` resources without exposing secret values in Git;
-   remove obsolete shared access after successful migration;
-   document secret ownership, rotation, and recovery procedures.
