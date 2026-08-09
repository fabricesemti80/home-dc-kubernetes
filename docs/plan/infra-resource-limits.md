# ⚖️ Infra-Cluster Resource Limits

## Motivation

`infra-cluster` is a 2-node Talos cluster (`infra-cp-01`: 5.95 CPU / 15.5Gi,
`infra-wk-01`: 3.95 CPU / 7.5Gi). An audit on 2026-08-06 showed several
git-managed workloads with **no resource limits**, which is risky once NetBox
(PR #256) lands on the same node:

-   Kestra standalone, its dind sidecar, postgres, versitygw — all zero limits
-   reloader, local-path-provisioner, tailscale-operator — zero limits
-   pulse and envoy — memory limit but no CPU limit

Unbounded pods on a small cluster can exhaust the node and take down
everything else (including Kestra itself, which runs critical automation).

## Changes

| Workload               | Requests     | Limits       | Notes                  |
| ---------------------- | ------------ | ------------ | ---------------------- |
| kestra standalone      | 500m / 1Gi   | 2 / 2Gi      | Java app; JVM headroom |
| kestra dind            | 100m / 256Mi | 1 / 1Gi      | builds flow containers |
| kestra init (aws-cli)  | 10m / 32Mi   | 100m / 128Mi | one-shot bucket check  |
| kestra postgres        | 250m / 512Mi | 500m / 1Gi   |                        |
| versitygw              | 50m / 64Mi   | 250m / 256Mi | S3 gateway, light      |
| reloader               | 10m / 64Mi   | 250m / 256Mi |                        |
| local-path-provisioner | 50m / 64Mi   | 250m / 256Mi |                        |
| tailscale-operator     | 50m / 64Mi   | 250m / 256Mi |                        |
| pulse                  | 250m / 512Mi | 1 / 2Gi      | OOMKilled at 1Gi       |
| envoy (gateway)        | 100m / 128Mi | 500m / 512Mi | added CPU limit        |
| Argo CD app controller | 100m / 512Mi | 500m / 1Gi   | OOMKilled at 512Mi     |

Total added ≈ 1.4 CPU / 2.5Gi requests on infra-cp-01 (Kestra's node) — fits
the ~4.8 CPU / ~10Gi headroom, alongside NetBox (~1.2 CPU / 2Gi).

## Out of scope

-   `kube-system` components (cilium, kube-apiserver, coredns,
    controller-manager, scheduler) are Talos-managed, not in this repo.
-   `envoy-gateway` shutdown-manager and autokuma come from upstream charts
    with their own defaults; tracked as a follow-up if needed.

## Validation

-   [ ] `kubectl get pods -A -o json | jq '.items[].spec.containers[].resources'`
        → no zero-limit workloads remain for git-managed infra apps
-   [ ] `kubectl get pods -A -o json | jq '.items[].spec.initContainers[].resources'`
        → no zero-limit init containers remain (e.g. pulse fix-perms)
-   [ ] `kubectl top nodes` → infra-wk-01 memory stays under ~75% of limits
-   [ ] Kestra still starts and runs a flow end-to-end
-   [ ] `kubectl rollout status -n kestra deploy/kestra-standalone`

## Rollback

-   Revert this PR; Argo self-heals back to the previous (unbounded) state.
-   No data is touched — this only changes resource requests/limits.
