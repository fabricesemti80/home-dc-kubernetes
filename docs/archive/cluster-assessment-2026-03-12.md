# Cluster Assessment — 2026-03-12

Read-only assessment of the homelab Kubernetes cluster architecture, security, networking, operations, and best practices.

## Strengths

### Architecture

-   **6-node topology** (3 controllers + 3 workers) with odd-number etcd quorum
-   **Talos L2 VIP** correctly configured on all three controllers (`10.0.40.101`)
-   **Node interfaces pinned by MAC address** in `talos/talconfig.yaml` — no DHCP ambiguity
-   **Talos patches well-scoped** — global patches for all nodes, controller-specific patches for control plane
-   **CoreDNS and kube-proxy disabled in Talos** — correctly delegated to Helm-deployed CoreDNS and Cilium kube-proxy replacement
-   **Tool versions fully pinned** in `.mise.toml` via mise
-   **Talos/Kubernetes versions Renovate-annotated** in `talos/talenv.yaml`

### GitOps & Argo CD

-   **App-of-apps pattern** correctly implemented via `kubernetes/components/common/apps.yaml`
-   **Hardened sync policies** on all Applications: `ServerSideApply`, `PruneLast`, `selfHeal`, `ApplyOutOfSyncOnly`
-   **Multi-source Applications** keep chart references and values co-located but separate
-   **Argo CD HA-configured** with 2 replicas for server, controller, dex, notifications, repoServer
-   **SOPS/age decryption** correctly wired via helm-secrets in repoServer

### Networking

-   **Cilium properly integrated with Talos** — `k8sServiceHost: 127.0.0.1:7445` (local API proxy), DSR load balancing, native routing, eBPF masquerade
-   **Envoy Gateway dual-gateway architecture** — separate internal (`10.0.40.102`) and external (`10.0.40.103`) gateways with TLS 1.2 minimum, HTTP-to-HTTPS redirects, HTTP/3 support
-   **Cloudflare Tunnel well-hardened** — non-root UID 65534, read-only filesystem, all caps dropped, post-quantum crypto enabled
-   **External DNS dual-source** — `crd` + `gateway-httproute` with Cloudflare proxy enabled
-   **L2 announcement policy** correctly configured for home network (no BGP)

### Security

-   **SOPS/age encryption consistent** — full-file for Talos, `data`/`stringData`-only for Kubernetes manifests
-   **Secrets never in environment variables** — all use `secretRef` / `secretKeyRef` / `apiTokenSecretRef`
-   **Container security posture** — cloudflared and echo both enforce `runAsNonRoot`, `readOnlyRootFilesystem`, `drop: ["ALL"]`
-   **Sensitive files gitignored** — `age.key`, `cloudflare-tunnel.json`, `github-deploy.key`, `kubeconfig`, `terraform.tfstate`
-   **Reloader configured** for automatic pod restarts on secret rotation

### Operations

-   **Bootstrap script** (`scripts/bootstrap-apps.sh`) is defensive with `set -Eeuo pipefail`, environment validation, and clear function structure
-   **Helmfile bootstrap ordering enforced** via `needs:` directives (cilium → coredns → spegel → cert-manager → argo-cd)
-   **All Taskfile targets have preconditions** verifying required tools and files
-   **Renovate covers all dependency types** — argocd, helmfile, helm-values, kubernetes, mise, GitHub Actions, OCI

---

## Issues

### Critical

#### 1. Cloudflare API token in plaintext

-   **Location:** `cluster.yaml` line 64
-   **Detail:** Token exists unencrypted on disk. Although `cluster.yaml` is gitignored, it should be treated as potentially exposed.
-   **Action:** Rotate the Cloudflare API token immediately.

#### 2. Argo CD admin password in plaintext

-   **Location:** `cluster.yaml` lines 88–91
-   **Detail:** Bcrypt hash with plaintext password in a comment in the same file.
-   **Action:** Remove plaintext comment, consider disabling admin account and switching to OIDC/SSO.

### High

#### 3. No monitoring stack deployed

-   **Detail:** All ServiceMonitors, PodMonitors, and Grafana dashboard configurations are present but no Prometheus/Grafana to scrape them. `00-crds.yaml` includes `kube-prometheus-stack` CRDs (v82.4.0), Cilium has `dashboards.enabled: true`, Envoy has a PodMonitor — all orphaned.
-   **Action:** Create `kubernetes/argo/apps/observability/kube-prometheus-stack.yaml`.

#### 4. Helmfile bootstrap timeout not applied

-   **Location:** `bootstrap/helmfile.d/01-apps.yaml`
-   **Detail:** `docs/operations/troubleshooting.md` documents that `timeout: 600` is needed for initial image pulls, but the source file still uses the default 300s.
-   **Action:** Add `timeout: 600` to the helmfile.

#### 5. Unrendered template variable in internal Gateway

-   **Location:** `kubernetes/apps/app-cluster/network/envoy-gateway/config/envoy.sops.yaml`
-   **Detail:** The `envoy-internal` Gateway annotation contains literal `${SECRET_DOMAIN}` instead of `krapulax.dev`. The external Gateway correctly uses the literal domain.
-   **Action:** Investigate whether SOPS decryption or Argo templating resolves this, or fix the literal value.

#### 6. LB IP pool overlaps with node addresses

-   **Location:** `kubernetes/apps/app-cluster/kube-system/cilium/config/networks.yaml`
-   **Detail:** `CiliumLoadBalancerIPPool` covers `10.0.40.0/24` which includes node IPs `.90–.95`. Nothing prevents Cilium from assigning a node IP to a LoadBalancer service.
-   **Action:** Narrow the CIDR to exclude node addresses (e.g., `10.0.40.100/28`).

#### 7. Missing `helm-secrets-private-keys.sops.yaml`

-   **Location:** Expected at `kubernetes/components/common/helm-secrets-private-keys.sops.yaml`
-   **Detail:** Bootstrap script references this file, silently continues when absent (`warn` not `fatal`). Without it, Argo CD repoServer cannot decrypt SOPS-encrypted values files.
-   **Action:** Verify the file exists or fix the path reference in the bootstrap script.

### Medium

#### 8. No memory requests on workloads

-   **Location:** All `values.yaml` files (cloudflare-tunnel, echo, Envoy)
-   **Detail:** Only memory limits are set, no requests. Pods are classified as `BestEffort` QoS — first to be killed under memory pressure.
-   **Action:** Add `resources.requests.memory` equal to limits for critical components.

#### 9. No PodDisruptionBudgets

-   **Detail:** With `allowSchedulingOnControlPlanes: true` and no PDBs, a node drain could evict all replicas of Argo CD, CoreDNS, or Envoy simultaneously.
-   **Action:** Add PDBs for multi-replica workloads (Argo CD server, CoreDNS, Envoy).

#### 10. No pod anti-affinity for CoreDNS

-   **Location:** `kubernetes/apps/app-cluster/kube-system/coredns/values.yaml`
-   **Detail:** CoreDNS has node affinity (control-plane only) but no pod anti-affinity. Both replicas can land on the same node — DNS single point of failure.
-   **Action:** Add `podAntiAffinity` preferring different nodes.

#### 11. No network policies

-   **Detail:** Despite Cilium being fully capable, no `CiliumNetworkPolicy` or `NetworkPolicy` resources exist. All pods can reach all pods across all namespaces.
-   **Action:** Add baseline network policies, at minimum isolating the `network` namespace from workload namespaces.

#### 12. No Pod Security Standards

-   **Detail:** No `pod-security.kubernetes.io/enforce` labels on namespaces. Any pod can request `hostPID`, `hostNetwork`, or privileged containers.
-   **Action:** Add `baseline` or `restricted` PSS labels to non-system namespaces.

#### 13. Admission control plugins deleted

-   **Location:** `talos/patches/controller/cluster.yaml`
-   **Detail:** `admissionControl: $$patch: delete` removes Talos default admission plugins (NodeRestriction, EventRateLimit) with no replacement (OPA/Kyverno not deployed).
-   **Action:** Document the rationale or deploy an admission controller.

### Low

#### 14. AppProject fully open

-   **Location:** `kubernetes/argo/settings/cluster-settings.yaml`
-   **Detail:** `destinations: "*"`, `sourceRepos: "*"`, `clusterResourceWhitelist: "*"` — no restrictions.
-   **Action:** Acceptable for single-admin homelab; tighten if adding contributors.

#### 15. Hubble disabled

-   **Location:** `kubernetes/apps/app-cluster/kube-system/cilium/values.yaml`
-   **Detail:** `hubble.enabled: false` — missing free network observability. The `ignoreDifferences` block already references Hubble certificate secrets.
-   **Action:** Consider enabling for network visibility.

#### 16. Cilium operator single replica

-   **Location:** `kubernetes/apps/app-cluster/kube-system/cilium/values.yaml`
-   **Detail:** `operator.replicas: 1` — if it crashes, new pods won't get IPs until recovery.
-   **Action:** Set to 2 for a 6-node cluster.

#### 17. `task reconcile` waits but doesn't force sync

-   **Location:** `.taskfiles/` (reconcile task)
-   **Detail:** Uses `argocd app wait --sync` which waits for the next self-heal cycle rather than forcing immediate reconciliation.
-   **Action:** Replace with `argocd app sync --force` for each app.

#### 18. `imagePullPolicy: Always` on gitops-tools init container

-   **Location:** `kubernetes/apps/app-cluster/argo-system/argo-cd/values.yaml`
-   **Detail:** Tag `2026.2.0` is pinned but `Always` means every repoServer restart triggers a registry pull. If ghcr.io is unavailable, repoServer fails to start.
-   **Action:** Switch to `IfNotPresent`.

#### 19. Bootstrap Applications use `project: default`

-   **Location:** `kubernetes/components/common/apps.yaml`, `repositories.yaml`, `settings.yaml`
-   **Detail:** Root bootstrap Applications use `project: default` while all child Applications use `project: kubernetes`. Benign inconsistency.

#### 20. cert-manager single replica

-   **Location:** `kubernetes/apps/app-cluster/cert-manager/cert-manager/values.yaml`
-   **Detail:** `replicaCount: 1` — outage during certificate renewal would cause TLS failures.
-   **Action:** Consider increasing to 2.

#### 21. Cloudflare-dns chart source inconsistency

-   **Detail:** Application uses HTTPS Helm repo (`https://kubernetes-sigs.github.io/external-dns`) while bootstrap CRDs use OCI mirror (`oci://ghcr.io/home-operations/charts-mirror/external-dns`).
-   **Action:** Align sources to prevent version skew.

#### 22. All Argo Applications on sync-wave 0

-   **Location:** `kubernetes/argo/apps/`
-   **Detail:** No ordering guarantee between apps — e.g., Envoy Gateway CRDs may not be ready when apps creating HTTPRoutes sync.
-   **Action:** Add sync-wave ordering for CRD-dependent apps if issues arise.

---

## Summary

The cluster has strong foundations: correct Talos/Cilium integration, clean GitOps patterns, good secret management, and comprehensive operational tooling. The main gaps are:

-   **Observability** — monitoring stack configured but not deployed
-   **Defense-in-depth** — no network policies, PDBs, or PSS enforcement
-   **Credential hygiene** — plaintext tokens in gitignored files
-   **Resilience** — missing memory requests, anti-affinity, and disruption budgets
