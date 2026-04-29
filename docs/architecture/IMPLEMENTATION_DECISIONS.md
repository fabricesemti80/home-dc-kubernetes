# Implementation Decisions

## Confirmed

-   Network: VLAN30 (`10.0.30.0/24`).
-   Access model: Tailscale for both node-level and subnet routing scenarios.
-   CNI: Cilium (target configuration enables kube-proxy replacement).
-   Ingress: the migrated cluster currently uses Envoy Gateway; Traefik remains only a historical design idea.
-   Storage: the migrated cluster currently uses Ceph CSI; Longhorn remains optional future work rather than current state.
-   GitOps: Argo CD.
-   Media service: remains on NAS Docker initially, routed via cluster ingress as external upstream.
-   Cluster relocation: keep the old `home-argo-cluster-2025` repo intact, but operate the migrated cluster directly from the `project-homelab` repo root with local state copied over.
-   Worker handling during cutover: keep worker VMs represented in Terraform state, but allow them to remain provisioned and powered off by using per-node `started = false`.

## Active Decisions

### Multi-replica control-plane and edge services

Decision:

-   Run `cloudflare-tunnel`, `cert-manager`, and the `cilium` operator with 2 replicas to reduce outage risk during node failure, pod eviction, and rolling updates.
-   Defer scaling `cloudflare-dns` until the deployed `external-dns` version supports leader election in this cluster path.

Assumptions:

-   The active Talos cluster has enough schedulable capacity across control-plane nodes to carry a second replica for these lightweight services.
-   `cloudflared` can maintain multiple concurrent connectors for the same tunnel without requiring route changes.
-   `external-dns` should only be scaled after leader election is available so only one replica writes DNS changes at a time.

Validation checks:

-   `kubectl get deploy -n network cloudflare-tunnel cloudflare-dns`
-   `kubectl get deploy -n cert-manager cert-manager`
-   `kubectl get deploy -n kube-system cilium-operator`
-   `kubectl get pods -n network -l app.kubernetes.io/name=cloudflare-tunnel -o wide`
-   `kubectl rollout status deploy/cloudflare-tunnel -n network`
-   `kubectl rollout status deploy/cert-manager -n cert-manager`
-   `kubectl rollout status deploy/cilium-operator -n kube-system`

Rollback:

-   Reduce the replica counts back to `1` for the three scaled workloads if resource pressure, chart behavior, or failover behavior is not acceptable.
-   Keep `cloudflare-dns` at a single replica until its deployed version gains a supported leader-election path.

## Pending final user confirmation

-   Initial 5 application services to onboard after platform baseline.
-   RPO/RTO tier definitions for critical services.
