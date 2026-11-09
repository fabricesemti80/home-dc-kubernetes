> Historical sizing plan: Kestra/Postgres/VersityGW are now approved for retirement,
> so their rows and flow checks below are historical rather than deployment targets.
> Remaining headroom was reassessed on 2026-11-09 after the
> [ordered retirement](../architecture/nas-backup-target.md#kestra--kubevirt-retirement);
> see [the reassessment](#reassessment-after-the-kestrakubevirt-retirement-2026-11-09-issue-555).

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

## Validation (original 2026-08 plan)

-   [ ] `kubectl get pods -A -o json | jq '.items[].spec.containers[].resources'`
        → no zero-limit workloads remain for git-managed infra apps
        (superseded by the 2026-11-09 reassessment below)
-   [ ] `kubectl get pods -A -o json | jq '.items[].spec.initContainers[].resources'`
        → no zero-limit init containers remain (pulse is retired; see below
        for uptime-kuma `fix-perms`)
-   [x] Node memory headroom checked (2026-11-09, below). `kubectl top` is
        unavailable on infra-cluster (no metrics-server); kubelet
        `stats/summary` was used instead.
-   ~~Kestra still starts and runs a flow end-to-end~~ — Kestra retired.
-   ~~`kubectl rollout status -n kestra deploy/kestra-standalone`~~ — Kestra retired.

## Reassessment after the Kestra/KubeVirt retirement (2026-11-09, issue #555)

Read-only evidence from the live infra-cluster (Talos v1.13.6, Kubernetes
v1.36.2). Usage is a single kubelet `stats/summary` sample, not a peak, so
limits keep generous headroom above it.

### Node headroom

| Node        | Allocatable    | Requests (CPU / mem)       | Limits (CPU / mem)           | Usage (CPU / working set) | Available mem |
| ----------- | -------------- | -------------------------- | ---------------------------- | ------------------------- | ------------- |
| infra-cp-01 | 5950m / 14.8Gi | 1731m (29%) / 4864Mi (32%) | 2850m (47%) / 14292Mi (94%)  | 653m / 7945Mi             | 7822Mi        |
| infra-wk-01 | 3950m / 7.1Gi  | 791m (20%) / 1741Mi (23%)  | 4250m (107%) / 7424Mi (101%) | 286m / 3265Mi             | 4522Mi        |

Both nodes have ample request headroom: the ~1.4 CPU / 2.5Gi that Kestra,
its dind sidecar, Postgres and VersityGW reserved on infra-cp-01 is gone.
infra-wk-01 working set is ~43% of capacity, well under the 75% target.
Memory **limits** are overcommitted (~94% / ~101% now; ~98% / ~105% after
this change). That is accepted: scheduling uses requests, and the sum of
observed working sets is far below allocatable. If several workloads burst
at once, the kernel OOM-kills the container furthest above its request, not
the node.

### Findings and changes

| Workload                                                          | Finding                                                                                                                                                                                               | Change                                                                                                                               |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| reloader (infra **and** app cluster)                              | Live pod has **no** requests/limits. `values.yaml` set `reloader.resources`, but chart 2.2.19 only reads `reloader.deployment.resources`, so PR #257's values were silently ignored. Usage 0m / 18Mi. | Moved the same values (10m/64Mi → 250m/256Mi) to `reloader.deployment.resources` in both clusters. `helm template` now renders them. |
| tailscale `ts-infra-router` (2 pods)                              | Operator default 1m / 1Mi requests, no limit; usage 1–15m / 23–49Mi.                                                                                                                                  | `ProxyClass infra-router` sets `tailscaleContainer` 10m/64Mi requests, 256Mi memory limit.                                           |
| uptime-kuma / autokuma `fix-perms` init                           | No requests/limits (busybox `chown`).                                                                                                                                                                 | 10m/16Mi → 100m/64Mi.                                                                                                                |
| local-path-provisioner, tailscale operator, envoy proxies         | Match the plan table.                                                                                                                                                                                 | None.                                                                                                                                |
| backrest `configure` init, litellm `postgres-init`                | No requests/limits on short-lived init containers.                                                                                                                                                    | Follow-up; usage of completed init containers is not observable from one sample, so values would be guesses.                         |
| monitoring stack, technitium, cloudflared, envoy-gateway, litellm | Requests plus memory limits, no CPU limit.                                                                                                                                                            | None: memory limits are what protect the node; CPU is compressible.                                                                  |
| cilium, coredns, kube-apiserver/scheduler/controller-manager      | Talos/Cilium managed.                                                                                                                                                                                 | Out of scope (unchanged).                                                                                                            |
| pulse, Argo CD app controller                                     | Pulse is retired; Argo CD runs on the app-cluster.                                                                                                                                                    | Rows in the table above are historical.                                                                                              |

### Assumptions

-   One usage sample is representative enough to size small controllers;
    limits are 4–5× observed usage.
-   CPU limits are intentionally not added where the chart sets only a memory
    limit.
-   Changing the `ProxyClass` restarts the two `ts-infra-router` pods (one per
    node). Tailnet access to infra subnets blips during the roll.

### Validation (this change)

-   [x] `helm template` reloader 2.2.19 with both values files renders
        `requests 10m/64Mi, limits 250m/256Mi`.
-   [x] `helm template` app-template 5.3.0 for uptime-kuma-infra renders the
        `fix-perms` resources on both Deployments.
-   [x] `kustomize build kubernetes/apps/infra-cluster/network/tailscale-infra`
        renders `tailscaleContainer.resources`; the live `ProxyClass` CRD
        schema has `tailscaleContainer.resources`.
-   [x] `task validate` and `yamllint` pass.
-   [ ] After merge: `kubectl -n kube-system get deploy reloader -o jsonpath='{.spec.template.spec.containers[0].resources}'`
        is non-empty on both clusters.
-   [ ] After merge: both `ts-infra-router` pods are Running with the new
        requests and `tailscale status` on a tailnet client still reaches
        infra subnets.
-   [ ] After merge: `kubectl describe node` request totals rise by only
        ~30m / ~200Mi in total.

## Rollback

-   Revert the PR; Argo self-heals back to the previous resources (reloader
    returns to unbounded, the tailscale routers to operator defaults).
-   No data is touched — this only changes resource requests/limits.
