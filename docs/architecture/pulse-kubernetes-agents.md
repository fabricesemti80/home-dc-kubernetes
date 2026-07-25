# Pulse Kubernetes Agents

Deploy Pulse agents into both Kubernetes clusters so the host-level Pulse server can monitor Kubernetes workloads.

## Architecture

-   `pulse-agent-infra` runs in the infra cluster and connects to `http://pulse.monitoring.svc.cluster.local:7655`.
-   `pulse-agent-app` runs in the app cluster and connects through the infra internal gateway via `pulse-infra.monitoring.svc.cluster.local`.
-   Both agents use the Pulse app-template chart layout and run as DaemonSets.
-   Each agent enables Kubernetes inventory only and disables host monitoring.

## Security

-   `PULSE_TOKEN` is synced from Doppler (`project-homelab/dev_homelab`) into each cluster with `DopplerSecret`.
-   The app-cluster agent uses plain HTTP across the local inter-cluster network. This is an accepted risk for the current homelab because both endpoints are local and private.
-   Service account access is limited to the Pulse RBAC resources in each agent app.

## Validation

1. `kubectl kustomize kubernetes/apps/monitoring/pulse-agent-infra`
2. `kubectl kustomize kubernetes/apps/monitoring/pulse-agent-app`
3. Check Pulse UI for `infra-cluster` and `app-cluster` agents.
4. Check agent logs if either cluster is missing.

## Rollback

1. Revert the PR or delete the two Argo Applications.
2. Argo prunes the DaemonSets, RBAC, and DopplerSecret resources.
3. Remove stale agents from Pulse if they remain visible after pruning.
