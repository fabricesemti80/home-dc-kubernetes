# Workload placement on the app cluster

**Decision date:** 2026-11-03.

## Problem

Measured from live pods on 2026-11-02, `k8s-wrkr-03` carried the most load: 78% of allocatable memory requested, 496% CPU limits and 282% memory limits, against 41% memory requested on `k8s-wrkr-01-gpu` and 66% on `k8s-wrkr-02`. Nine of its 28 pods are pinned there by node-local volumes (`local-path`) and cannot move without a data restore. Fifteen have no volume and no pin; the largest are the two Envoy gateway replicas (1 GiB requested each) and the Argo CD controller.

## Change

The workloads that can move now prefer other nodes than `k8s-wrkr-03`:

-   Envoy gateways (`envoy.sops.yaml`, `EnvoyProxy.spec.provider.kubernetes.envoyDeployment.pod`): a soft node preference away from `k8s-wrkr-03` plus a soft hostname spread. Both gateways share this resource.
-   Argo CD (`argo-cd/values.yaml`, `global.affinity`): the chart's soft pod anti-affinity is kept and a soft node preference is added for all Argo components.

The rules are **preferences**, not requirements. A pod still schedules on `k8s-wrkr-03` if nothing else fits, so a node failure does not leave pods Pending. They only take effect when a pod is recreated; rolling the Deployments (Argo applies the change) moves the current `k8s-wrkr-03` replicas.

## Assumptions and limits

-   No node carries a `NoSchedule` taint except the control plane, so all three workers can take these pods.
-   The 15 movable pods request 1,110m CPU in total. Moving them evenly would raise `k8s-wrkr-02` memory requests from about 66% to about 87%; the preference toward the less-loaded GPU worker is expected to keep that lower. Verify after rollout.
-   Small controllers (cert-manager, doppler-operator, arc-controller, GPU-operator discovery, about 0.9 GiB together) are not covered; they have separate charts.
-   Pods with `local-path` volumes (media apps, backrest, immich) stay where their data is. Moving them needs a restore from Backrest and a `nodeSelector` change per app.
-   Nothing prevents drift back to `k8s-wrkr-03` for workloads without these rules, and an automatic rebalancer (descheduler) is not installed.
-   Memory limits remain heavily overcommitted on every worker; this change does not address that.

## Reading the node table

The Kubernetes dashboard's node table sums `kube_pod_container_resource_requests` and `..._limits`. Finished pods (`Succeeded`/`Failed`) stay in those metrics until they are deleted, although they use nothing. On 2026-11-03 `k8s-wrkr-03` held 24 finished `protect-*` backup pods, which showed 108% CPU requests when the running pods requested 47% (1.85 of 4 cores) and 56% memory requests against an actual 36%. Two changes remove that:

-   The `app-protect` chart keeps one successful job per CronJob (`successfulJobsHistoryLimit: 1`, was 3); failed jobs stay at 3 for diagnosis. The stale-export alert reads the CronJob's last-success time, not its pods.
-   The dashboard queries only count pods that are `Pending` or `Running` (a join on `kube_pod_status_phase`). Panels and any future alert summing these metrics should use the same filter. One finished pod per CronJob remains in the pod list but no longer counts.

Memory limits remain overcommitted (about 150% on `k8s-wrkr-03` counting running pods only). Node memory in use was 16–25% on 2026-11-03. Per-pod usage is not collected (no cAdvisor), so limits should not be lowered blindly.

## Validation

1. After Argo syncs, run `kubectl get pods -A -o wide --field-selector spec.nodeName=k8s-wrkr-03` and confirm the Envoy and Argo pods have left.
2. Check requested memory per node (the Kubernetes dashboard's node table) and that no worker exceeds about 85% requested.
3. Confirm gateway traffic: `curl -sI https://argo.krapulax.dev` and an internal route respond, and Envoy replicas are Ready on different nodes.

## Rollback

Revert the commit. Argo restores the previous scheduling; pods stay where they are until recreated.
