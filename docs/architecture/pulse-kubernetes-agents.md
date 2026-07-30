# 💓 Pulse Kubernetes Agents

Deploy the Pulse agent only into the infra cluster so the infra Pulse server can monitor the independent infra runtime without ingesting app-cluster workload volume.

## 🏛️ Architecture

-   `pulse-agent-infra` runs in the infra cluster and connects to `http://pulse.monitoring.svc.cluster.local:7655`.
-   The app-cluster agent is intentionally removed because reporting every app-cluster pod/deployment appears to overload the Pulse browser UI.
-   The infra agent uses the Pulse app-template chart layout and runs as a DaemonSet.
-   The agent enables Kubernetes and host monitoring and runs one replica per infra node.
-   Host networking, host PID visibility, and privileged mode expose node CPU, memory, disk, and network statistics to the host module.

## 📌 Security

-   `PULSE_TOKEN` is synced from Doppler (`home-dc-kubernetes/infra`) into the infra cluster with `DopplerSecret`.
-   Service account access is limited to the Pulse RBAC resources in the infra agent app.
-   Privileged mode is limited to the Pulse infra agent DaemonSet because host metrics require access to node namespaces.

## 🤔 Assumptions

-   Infra-cluster monitoring is more important than app-cluster detail while Pulse UI stability is being restored.
-   Removing app-cluster pod/deployment ingestion should reduce Pulse UI load without affecting the infra Pulse server.
-   The live `pulse-agent-app` Argo Application must be deleted once because the app-of-apps uses `Prune=false`.

## ✅ Validation

1. `kubectl kustomize kubernetes/apps/infra-cluster/monitoring/pulse-agent-infra`
2. Delete the live app-cluster agent Application:
   `kubectl --kubeconfig kubeconfig -n argo-system delete application pulse-agent-app`
3. Confirm app-cluster agent resources are gone:
   `kubectl --kubeconfig kubeconfig -n monitoring get daemonset,serviceaccount,clusterrole,clusterrolebinding,dopplersecret | rg pulse-agent`
4. Check Pulse UI remains reachable and no longer receives the `app-cluster` agent.
5. Check infra agent logs if `infra-cluster` is missing.

## ↩️ Rollback

1. Restore the deleted `pulse-agent-app` Argo Application and app manifests from Git history.
2. Re-sync the app-of-apps or apply the restored Application.
3. Confirm the `app-cluster` agent appears in Pulse again.
