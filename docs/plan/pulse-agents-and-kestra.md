# Plan: Pulse Agents (Kubernetes) + Kestra on infra-cluster

## Goal

1. Monitor every Kubernetes node with Pulse automatically via GitOps/Argo CD.
2. Deploy Kestra on the infra-cluster.

Both must fit existing conventions (app-template, Doppler for secrets, CephFS for config, internal/external Envoy Gateway, Cloudflare tunnel).

---

## 1. Pulse Agents on Kubernetes

### Why a DaemonSet is the right pattern

The [Pulse Kubernetes docs](https://github.com/rcourtman/Pulse/blob/main/docs/KUBERNETES.md) recommend a `DaemonSet` for Kubernetes monitoring. This is future-proof: any new node that joins the cluster automatically gets an agent pod.

### Options considered

| Approach                             | Pros                                                                   | Cons                                                             | Verdict                          |
| ------------------------------------ | ---------------------------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------- |
| Ansible role on every node (current) | Works for Proxmox hosts, no K8s privilege                              | Does not scale with auto-scaling K8s nodes, drift                | Keep for Proxmox/Bare metal only |
| Kubernetes DaemonSet                 | GitOps-native, auto-schedules on new nodes, one deployment per cluster | Requires RBAC, token management, optional privileged host mounts | **Use for K8s nodes**            |
| Sidecar on every workload            | Per-workload telemetry                                                 | Huge overhead, not node-level monitoring                         | Not suitable                     |

### Recommended design

Deploy one Argo app per cluster:

-   `kubernetes/apps/monitoring/pulse-agent-app/` for the **app-cluster**.
-   `kubernetes/apps/monitoring/pulse-agent-infra/` for the **infra-cluster**.

Each is a small app-template `DaemonSet` with:

-   Image: `docker.io/rcourtman/pulse:6` (the same image contains `/usr/local/bin/pulse-agent` as an arch-resolved symlink).
-   Command: `/usr/local/bin/pulse-agent`
-   Args/env:
    -   `--enable-kubernetes`
    -   `--enable-host=false` (Kubernetes metrics only; avoids privileged mode).
    -   `--enable-commands` (optional; only if we want Patrol actions on nodes).
    -   `--insecure` or `--allow-plaintext-http` because the internal URL is HTTP.
-   `PULSE_URL`:
    -   infra-cluster: `http://pulse.monitoring.svc.cluster.local:7655` (in-cluster service, no gateway/LB dependency).
    -   app-cluster: `http://pulse-infra.monitoring.svc.cluster.local:80` via an in-cluster `Service`/`Endpoints` pointing to the infra internal gateway IP (`10.0.40.106`), plus an extra HTTPRoute hostname on the infra internal gateway.
-   `PULSE_AGENT_ID`:
    -   `infra-cluster` or `app-cluster` (required; all DaemonSet pods share one logical agent identity).
-   `PULSE_KUBE_INCLUDE_ALL_PODS=true`
-   `PULSE_KUBE_INCLUDE_ALL_DEPLOYMENTS=true`
-   Token from a **DopplerSecret** (`PULSE_TOKEN`) scoped with `kubernetes:report` + `agent:report`.
-   Reloader annotation (`reloader.stakater.com/auto: "true"`) so token rotation restarts pods.
-   RBAC:
    -   `ServiceAccount` in `monitoring` namespace.
    -   `ClusterRole` with read-only `get/list/watch` on nodes, pods, deployments.
    -   `ClusterRoleBinding`.

### Future-proofing

-   New nodes: handled by DaemonSet.
-   Token rotation: DopplerSecret + Reloader.
-   Agent binary updates: Pulse agent auto-updates hourly from the server, so the container image tag can stay pinned.
-   Cluster additions: copy the Argo app, change `PULSE_AGENT_ID` and `PULSE_URL`.

### Security notes

-   Agent pods do **not** need `hostNetwork` or `hostPID` for Kubernetes-only monitoring.
-   If we later want host-level metrics (CPU temp, disk SMART, etc.) on K8s nodes, we must add `privileged: true` and host mounts (`/proc`, `/sys`, `/`). That should be a separate opt-in flag.
-   The agent token should be scoped to `kubernetes:report` and `agent:report`, not an admin token.

### Decisions

-   **Kubernetes-only monitoring** (`--enable-host=false`). No privileged mode or host mounts.
-   **App-cluster → Pulse server** uses an in-cluster Kubernetes `Service` + `Endpoints` pointing at the infra internal gateway IP (`10.0.40.106`), plus an extra HTTPRoute on the infra gateway to route the in-cluster service hostname. This avoids relying on `.home` DNS from inside app-cluster pods.

---

## 2. Kestra on infra-cluster

### Options considered

| Approach                                                                | Pros                                     | Cons                                                                | Verdict                             |
| ----------------------------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------- | ----------------------------------- |
| `kestra-starter` Helm chart (bundles Postgres + Versity object storage) | One chart, one Argo app, quick to deploy | Bundled deps are marked evaluation-only; heavier on a single worker | **Reasonable for homelab**          |
| `kestra` chart + external Postgres + external S3                        | Production-grade, dependency isolation   | Requires managed Postgres and object storage we do not have yet     | Better long-term, more moving parts |
| `kestra` chart + bundled Postgres subchart + bundled MinIO              | Middle ground                            | Chart does not bundle Postgres/MinIO; would need separate apps      | More complex than starter           |

### Storage constraint on infra-cluster

The infra-cluster has **no Ceph storage class** and only one worker (`infra-wk-01`). Stateful pods must be pinned to that node so PVCs do not drift and lose data.

### Recommended design

1. **Deploy `local-path-provisioner` on infra-cluster** as its own Argo app.
    - Gives a `local-path` StorageClass backed by hostPath on the node.
    - Created PVs have `nodeAffinity`, so pods cannot move to another node without losing the volume.
2. **Deploy Kestra with `kestra-starter`** Helm chart.
    - Use `StorageClass: local-path`.
    - Pin all pods to `infra-wk-01` with `nodeSelector`.
    - Standalone mode.
    - Internal HTTPRoute `kestra.krapulax.home` on infra internal Envoy gateway.
    - External access only if needed via Cloudflare tunnel.
    - DopplerSecret for basic-auth credentials.

### Trade-offs

-   `local-path` volumes are tied to one node. If `infra-wk-01` fails, Kestra data is lost unless backed up.
-   `kestra-starter` is marked evaluation-only, but is the simplest path for a homelab. If Kestra becomes critical, migrate to the `kestra` chart with external Postgres (CloudNativePG) and S3-compatible storage (Ceph RGW / MinIO).

### Future migration path

If Kestra becomes critical, migrate from `kestra-starter` to the `kestra` chart with external Postgres and S3-compatible storage. Document this as a follow-up task.

---

## 3. Files to create (after approval)

### Pulse agent (K8s)

For each cluster:

-   `kubernetes/apps/monitoring/pulse-agent-<cluster>/values.yaml`
-   `kubernetes/apps/monitoring/pulse-agent-<cluster>/config/rbac.yaml`
-   `kubernetes/apps/monitoring/pulse-agent-<cluster>/config/doppler-secret.yaml`
-   `kubernetes/apps/monitoring/pulse-agent-<cluster>/config/kustomization.yaml`
-   `kubernetes/apps/monitoring/pulse-agent-<cluster>/kustomization.yaml`
-   `kubernetes/argo/apps/monitoring/pulse-agent-<cluster>.yaml`

### Kestra

-   `kubernetes/apps/storage/local-path-provisioner-infra/` (storage class app)
-   `kubernetes/apps/automation/kestra-infra/values.yaml`
-   `kubernetes/apps/automation/kestra-infra/config/namespace.yaml`
-   `kubernetes/apps/automation/kestra-infra/config/doppler-secret.yaml`
-   `kubernetes/apps/automation/kestra-infra/config/kustomization.yaml`
-   `kubernetes/apps/automation/kestra-infra/kustomization.yaml`
-   `kubernetes/argo/apps/automation/kestra-infra.yaml`

---

## 4. Validation plan

1. Argo syncs the new apps.
2. `kubectl get ds -n monitoring` shows `pulse-agent` pods on every node.
3. Pulse UI Infrastructure/Workloads pages show the cluster, nodes, and pods.
4. Kestra pod reaches Ready and UI loads at `http://kestra.krapulax.home`.

---

## 5. Rollback

-   Delete the Argo app(s) to remove the DaemonSet / Kestra release.
-   For Kestra, PVCs should use `Retain` reclaim policy if data matters; document snapshot before removal.
