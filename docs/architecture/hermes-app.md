# Hermes Agent on the app cluster

Deploy one Nous Research Hermes Agent for the lab. Argo CD renders the pinned
Hermeum operator chart and applies the agent custom resource after the CRD.
The operator watches only the dedicated `hermes` namespace. The agent uses
a service account without an API token and exposes an authenticated ClusterIP
API for port-forwarding. Operator telemetry is disabled.

Use OpenCode Zen's OpenAI-compatible endpoint with MiniMax M3. Create a
dedicated OpenCode Console API key for Hermes and set `OPENCODE_ZEN_API_KEY`
in Doppler `home-dc-kubernetes/apps` before syncing. The cluster must be able
to reach `opencode.ai` on TCP 443.

Agent state uses a retained 5 GiB `local-path` claim. This pilot opts out of
Backrest because the operator lets the scheduler choose the volume's worker
and the exporter configuration requires a fixed node. Sessions and memories
can be lost if that worker's disk fails.

## Rollout and rollback

- [ ] Create the dedicated OpenCode Console key and populate Doppler.
- [ ] Manually sync the `hermes` Argo Application. Check the operator Deployment,
  HermesAgent status, StatefulSet readiness, and the bound `hermes-data` claim.
- [ ] Port-forward the `hermes` Service on port 8642 and send a test
  completion with the operator-generated `API_SERVER_KEY`. Confirm the request
  succeeds and OpenCode Console records MiniMax M3 usage.
- [ ] To roll back, delete the HermesAgent while the operator is still running.
  Revert the Git change and sync the parent before deleting the `hermes` Argo
  Application. Preserve the `hermes-data` claim and namespace for recovery.
  Revoke the OpenCode Console key if retiring the pilot.
