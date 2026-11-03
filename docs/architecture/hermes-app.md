# Hermes Agent on the app cluster

Deploy one Nous Research Hermes Agent for the lab. Argo CD renders the pinned
Hermeum operator chart and applies the agent custom resource after the CRD.
The operator watches only the dedicated `hermes` namespace. The agent uses
a service account without an API token and exposes an authenticated ClusterIP
API for port-forwarding. Operator telemetry is disabled.

Set these three values in Doppler `home-dc-kubernetes/apps` before the first
sync. The starting profile uses OpenRouter's free NVIDIA Nemotron 3 Ultra.

| Parameter | Starting value |
| --- | --- |
| `HERMES_LLM_ADDRESS` | `https://openrouter.ai/api/v1` |
| `HERMES_LLM_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b:free` |
| `HERMES_LLM_API_KEY` | Dedicated OpenRouter API key |

Switch to another OpenAI-compatible provider by updating the three values
together. After Doppler updates `hermes/hermes-llm`, restart the Hermes pod
if it has not already restarted so it reads the new environment. The cluster
must be able to reach the chosen endpoint.

Agent state uses a retained 5 GiB `local-path` claim. This pilot opts out of
Backrest because the operator lets the scheduler choose the volume's worker
and the exporter configuration requires a fixed node. Sessions and memories
can be lost if that worker's disk fails.

## Rollout and rollback

- [ ] Create the dedicated OpenRouter key and populate the three Doppler values.
- [ ] Manually sync the `hermes` Argo Application. Check the operator Deployment,
  HermesAgent status, StatefulSet readiness, and the bound `hermes-data` claim.
- [ ] Port-forward the `hermes` Service on port 8642 and send a test
  completion with the operator-generated `API_SERVER_KEY`. Confirm the request
  succeeds and OpenRouter records usage under the free model ID.
- [ ] To roll back, delete the HermesAgent while the operator is still running.
  Revert the Git change and sync the parent before deleting the `hermes` Argo
  Application. Preserve the `hermes-data` claim and namespace for recovery.
  Revoke the inference key if retiring the pilot.
