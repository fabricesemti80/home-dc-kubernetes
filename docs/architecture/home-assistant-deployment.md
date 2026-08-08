# Home Assistant Deployment

## Decision

Date: 2026-08-08

Deploy Home Assistant to the app-cluster (`app-cluster`, Talos) as a single-replica stateful workload in the `home` namespace, using the official `ghcr.io/home-assistant/home-assistant` container image managed through the `bjw-s` app-template Helm chart (v5.0.1) via Argo CD. Internal access only, through the Envoy internal gateway at `ha.krapulax.home` (VLAN 30).

## Assumptions

-   The official Home Assistant container is used because the non-root community build (`onedr0p/home-assistant`) is abandoned (last tag 2025.3.3). The official image is designed to run as root, so the pod runs as UID 0 with all capabilities dropped and a read-only root filesystem.
-   `/config` is a CephFS PVC (`storageClass: cephfs`, 5 GiB, RWX). CephFS is already the established config storage class for the app-cluster media stack.
-   HA is single-instance. A second replica against the same `/config` PVC would contend on the recorder SQLite database and double-fire automations, so the controller uses `Recreate` — never overlapping instances.
-   Envoy internal gateway (namespace `network`, `envoy-internal` HTTPRoute section) terminates internal HTTP for `ha.krapulax.home`. Envoy forwards via proxy headers, so HA must trust the cluster ranges: pod CIDR `10.42.0.0/16`, service CIDR `10.43.0.0/16`.
-   First-boot configuration is provided by the `home-assistant-config` ConfigMap (mounted read-only at `/config/configuration.yaml`); the Reloader annotation restarts HA when it changes. No initial onboarding through the proxy is required — trusted proxies are already configured.
-   HA's own UI state (`.storage`, automations, recorder DB) is written to `/config` on the PVC; YAML-level configuration is managed from this repository (GitOps).

## Security Impact

-   **Network**: HA is reachable only on VLAN 30 via `ha.krapulax.home`; no public HTTPRoute/Cloudflare exposure. The VLAN 30 firewall profile is governed by the repo's network configuration.
-   **Pod**: UID 0 is required by the official image, mitigated by `allowPrivilegeEscalation: false`, `capabilities: drop ALL`, read-only rootfs, and writable paths limited to `/config` (PVC), `/run` and `/tmp` (emptyDirs).
-   **Secrets**: no credentials are embedded; any integrations needing tokens will use the repo's established secret strategy (SOPS/Doppler) rather than plaintext values.
-   **Backup**: HA state is on CephFS; the repo's database-backup strategy covers the recorder DB, and CephFS snapshots are the recovery baseline for `/config`.
-   **ServiceAccount**: a dedicated `home-assistant` ServiceAccount exists with `automountServiceAccountToken: false`; the pod does not mount the token.

## Validation

-   `task validate` (repo CI) passes; kustomize renders the `config/` resources; Helm values are schema-validated by the app-template chart.
-   After apply: `ha.krapulax.home` loads from a LAN client without HTTP 400; `/config` PVC is created; startup probe passes (`/` on 8123); HA logs show no `untrusted proxy` rejections.
-   Lint: prettier and pre-commit hooks pass on all changed files.

## Rollback

-   Disable the Argo application `kubernetes/argo/apps/app-cluster/home/home-assistant.yaml` (or `kubectl -n argo-system delete app home-assistant`).
-   Remove the HTTPRoute `home-assistant-internal` to withdraw `ha.krapulax.home` DNS/route; the `external-dns` annotation is on the route, so deletion removes the record.
-   The `/config` PVC is retained (CephFS), so re-enabling the application restores HA state — no data-loss path in the rollback.
-   Git revert: `git revert` the feature commit; Argo self-heal returns the cluster to the previous state.
