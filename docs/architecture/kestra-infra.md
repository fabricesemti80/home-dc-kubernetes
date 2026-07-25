# Kestra Infra Deployment

Deploy Kestra on the infra cluster as the homelab automation service.

## Architecture

-   Namespace: `kestra`
-   Runtime: upstream regular `kestra` Helm chart.
-   Database: dedicated PostgreSQL Helm release in the same namespace.
-   Object storage: in-cluster `versitygw` service backed by local-path storage.
-   Storage bootstrap: infra local-path provisioner creates retained local PVs for Kestra support services.
-   Networking: internal HTTPRoute exposes Kestra through the infra Envoy gateway.

## Security

-   Kestra basic auth, PostgreSQL credentials, and object-store credentials are synced from Doppler (`project-homelab/dev_homelab`).
-   No secrets are committed to Git.
-   Local storage is intentionally infra-cluster scoped; it should not be scheduled onto the app cluster.

## Validation

1. `kubectl kustomize kubernetes/apps/automation/kestra-infra`
2. `kubectl kustomize kubernetes/apps/storage/local-path-provisioner-infra`
3. Confirm Argo sync for `kestra-infra` and `local-path-provisioner-infra`.
4. Check `kubectl -n kestra get pods,pvc,httproute`.
5. Open the internal Kestra route and verify login.

## Rollback

1. Revert the PR or delete the `kestra-infra` Argo Application.
2. Argo prunes the chart resources and repo-managed manifests.
3. Retained local-path data remains on disk; remove it manually only after confirming no rollback is needed.
4. Recreate the Argo Application from Git to restore the deployment from the retained data.
