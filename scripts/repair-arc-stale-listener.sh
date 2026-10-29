#!/usr/bin/env bash
set -euo pipefail

: "${KUBECONFIG:?Run through task arc:repair-stale-listener with the app-cluster kubeconfig}"
stale_id="${1:?Pass STALE_ID from the RunnerScaleSetNotFoundException}"
[[ $stale_id =~ ^[1-9][0-9]*$ ]] || {
  echo "STALE_ID must be a positive numeric scale-set ID" >&2
  exit 1
}

namespace=arc-system
scale_set=home-dc-kubernetes
selector="app.kubernetes.io/instance=$scale_set"

kubectl -n "$namespace" get deployment arc-controller-gha-rs-controller -o json |
  jq -e '(.spec.template.spec.containers[0].image | endswith(":0.15.1")) and ((.status.readyReplicas // 0) > 0)' >/dev/null || {
  echo "ARC controller 0.15.1 must be ready before rebuilding its listener" >&2
  exit 1
}

current_id="$(kubectl -n "$namespace" get autoscalingrunnerset "$scale_set" -o json |
  jq -r '.metadata.annotations["runner-scale-set-id"] // ""')"
if [[ $current_id != "$stale_id" ]]; then
  echo "Scale-set ID is already $current_id, not stale ID $stale_id; no deletion needed"
  exit 0
fi

kubectl -n "$namespace" get ephemeralrunners -o json |
  jq -e '.items | length == 0' >/dev/null || {
  echo "Active ephemeral runners exist; wait for jobs to finish before listener repair" >&2
  exit 1
}

listener_count="$(kubectl -n "$namespace" get autoscalinglisteners -l "$selector" -o json |
  jq --argjson id "$stale_id" '[.items[] | select(.spec.runnerScaleSetId == $id)] | length')"
[[ $listener_count == 1 ]] || {
  echo "Expected exactly one listener using stale ID $stale_id, found $listener_count" >&2
  exit 1
}

# The 0.15.1 controller validates the remote ID when recreating a listener.
kubectl -n "$namespace" delete autoscalinglistener -l "$selector" --wait=true
for ((attempt = 0; attempt < 60; attempt++)); do
  new_id="$(kubectl -n "$namespace" get autoscalingrunnerset "$scale_set" -o json |
    jq -r '.metadata.annotations["runner-scale-set-id"] // ""')"
  if [[ $new_id =~ ^[1-9][0-9]*$ && $new_id != "$stale_id" ]]; then
    kubectl -n "$namespace" wait --for=condition=Ready pod -l app.kubernetes.io/component=runner-scale-set-listener --timeout=120s
    echo "ARC re-registered scale set $scale_set as ID $new_id; listener is Ready"
    exit 0
  fi
  sleep 2
done

echo "ARC did not re-register a new scale-set ID; inspect controller logs" >&2
exit 1
