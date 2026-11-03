# Hermes Agent on the app cluster

Deploy one Nous Research Hermes Agent for the lab. Argo CD renders the pinned
Hermeum operator chart and applies the agent custom resource after the CRD.
The operator watches only the dedicated `hermes` namespace. The agent uses
a service account without an API token and exposes an authenticated ClusterIP
API for port-forwarding. Operator telemetry is disabled.

Use LiteLLM's TLS endpoint with the `openai/gpt-5-mini` alias. Create a dedicated
LiteLLM virtual key restricted to that alias with a budget, and set
`HERMES_LITELLM_API_KEY` in Doppler `home-dc-kubernetes/apps` before syncing.
The cluster must be able to reach `litellm.krapulax.dev` on TCP 443.

Agent state uses a retained 5 GiB `local-path` claim. This pilot opts out of
Backrest because the operator lets the scheduler choose the volume's worker
and the exporter configuration requires a fixed node. Sessions and memories
can be lost if that worker's disk fails.

## Rollout and rollback

- [ ] Create the scoped LiteLLM key and populate Doppler.
- [ ] Manually sync the `hermes` Argo Application. Check the operator Deployment,
  HermesAgent status, StatefulSet readiness, and the bound `hermes-data` claim.
- [ ] Port-forward the `hermes` Service on port 8642 and send a test
  completion with the operator-generated `API_SERVER_KEY`. Confirm LiteLLM
  records the request against the dedicated virtual key.
- [ ] To roll back, delete the HermesAgent while the operator is still running.
  Revert the Git change and sync the parent before deleting the `hermes` Argo
  Application. Preserve the `hermes-data` claim and namespace for recovery.
  Revoke the virtual key if retiring the pilot.
