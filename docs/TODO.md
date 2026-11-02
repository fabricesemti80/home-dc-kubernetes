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
