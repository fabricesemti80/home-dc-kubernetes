# Kestra Infra Deployment

Deploy Kestra on the infra cluster as the homelab automation service. It should stay available when the Proxmox-hosted app cluster is offline for maintenance.

## Architecture

-   Namespace: `kestra`
-   Runtime: upstream regular `kestra` Helm chart.
-   Database: dedicated PostgreSQL Helm release in the same namespace.
-   Object storage: in-cluster `versitygw` service backed by local-path storage.
-   Storage bootstrap: infra local-path provisioner creates retained local PVs for Kestra support services.
-   Placement: Kestra, PostgreSQL, VersityGW, and local-path helper pods are pinned to `infra-cp-01`.
-   Networking: internal HTTPRoute exposes Kestra through the infra Envoy gateway at `10.0.40.106`; public DNS points `kestra.krapulax.dev` at `external-infra.krapulax.dev`, and the infra Cloudflare Tunnel routes that hostname directly to the Kestra service.

## Security

-   Kestra basic auth, PostgreSQL credentials, and object-store credentials are synced from Doppler (`project-homelab/dev_homelab`).
-   No secrets are committed to Git.
-   External access is gated by Cloudflare Access before Kestra basic auth.
-   Local storage is intentionally infra-cluster scoped; it should not be scheduled onto the app cluster.
-   Kestra is intended to orchestrate clean Proxmox, Ceph, VM, Kubernetes, and cluster stop/start workflows.

## Assumptions

-   `infra-cp-01` is the preferred node for critical automation because it should remain online while app-cluster VMs are restarted.
-   Argo CD on `app-cluster` may continue syncing this app initially, but the runtime should not depend on app-cluster nodes after sync.
-   `kestra.krapulax.home` should resolve directly to the infra-cluster internal Envoy gateway, not the app-cluster gateway.

## Validation

1. `kubectl kustomize kubernetes/apps/infra-cluster/automation/kestra-infra`
2. `kubectl kustomize kubernetes/apps/infra-cluster/storage/local-path-provisioner-infra`
3. Confirm Argo sync for `kestra-infra` and `local-path-provisioner-infra`.
4. Check `kubectl -n kestra get pods,pvc,httproute`.
5. Confirm Kestra pods are scheduled on `infra-cp-01`.
6. `dig +short kestra.krapulax.home` should return `10.0.40.106`.
7. `dig +short kestra.krapulax.dev CNAME` should return `external-infra.krapulax.dev`.
8. `curl -I https://kestra.krapulax.dev` should reach Kestra through Cloudflare Tunnel.
9. Open the internal Kestra route and verify login.

## Rollback

1. Revert the PR or delete the `kestra-infra` Argo Application.
2. Argo prunes the chart resources and repo-managed manifests.
3. Retained local-path data remains on disk; remove it manually only after confirming no rollback is needed.
4. Recreate the Argo Application from Git to restore the deployment from the retained data.
