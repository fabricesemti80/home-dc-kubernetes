# Technitium Infra DNS

## Decision

Date: 2026-07-30

Deploy Technitium DNS Server on the infra cluster as a two-replica StatefulSet. Each replica keeps its own config on a retained static node-local PVC; Technitium clustering is responsible for consistency.

## Assumptions

-   Infra nodes are currently `infra-cp-01` and `infra-wk-01`; two replicas with required hostname anti-affinity place one Technitium pod on each node.
-   Static `technitium-local` PVs bind `technitium-0` storage to `infra-cp-01` and `technitium-1` storage to `infra-wk-01`.
-   Control-plane scheduling remains allowed for infra support services.
-   `10.0.40.53` is free on the LAN and should be used as the home-router DNS target.
-   The intended local DNS zone is `krapulax.home`.
-   Doppler `infra` config contains `TECHNITIUM_ADMIN_PASSWORD`.
-   Doppler `apps` and `infra` configs contain the same `TECHNITIUM_RFC2136_TSIG_KEYNAME` and `TECHNITIUM_RFC2136_TSIG_SECRET`.

## Security Impact

-   Recursive DNS is limited to private RFC1918 ranges.
-   Public recursive lookups are forwarded to Cloudflare DoH instead of direct root recursion from the cluster network.
-   The web console is available internally at `dns.krapulax.home` and externally through the infra Cloudflare tunnel at `dns.krapulax.dev`.
-   DNS `53/TCP` and `53/UDP` are exposed on `10.0.40.53`.
-   No cluster tokens, TSIG keys, or local zone records are committed.
-   `krapulax.dev` remains Cloudflare-managed by the Cloudflare ExternalDNS deployment.

## Local DNS Automation

Use Technitium as the LAN resolver and authoritative `krapulax.home` server at `10.0.40.53`.

Two RFC2136 ExternalDNS deployments publish internal Kubernetes routes into Technitium:

-   `technitium-dns` in app-cluster watches app-cluster internal HTTPRoutes.
-   `technitium-dns-infra` in infra-cluster watches infra-cluster internal HTTPRoutes, including `dns.krapulax.home`, `pulse.krapulax.home`, and `kestra.krapulax.home`.
-   A static app-cluster `DNSEndpoint` publishes `kubernetes.krapulax.home -> 10.0.40.102` because existing app-cluster internal HTTPRoutes target that gateway name.

Both writers are filtered to `krapulax.home`. They do not manage `krapulax.dev`.

## Clustering

After deployment, initialize a new Technitium cluster on `technitium-0`, then join `technitium-1` as a secondary. Cluster node addresses must use the stable per-replica Services, never pod IPs:

-   `technitium-peer-0.network.svc.cluster.local` for `technitium-0`
-   `technitium-peer-1.network.svc.cluster.local` for `technitium-1`

Each Service selects one StatefulSet ordinal and exposes DNS plus the HTTPS cluster API only inside the infra cluster. This keeps peer identities unchanged when a pod is recreated. The public `technitium-dns` LoadBalancer at `10.0.40.53` remains the resolver used by LAN and Tailscale clients.

Create the `krapulax.home` primary zone in Technitium, enable RFC2136 dynamic updates with the Doppler-managed TSIG key, and include that zone in the cluster catalog so it replicates across nodes. `krapulax.dev` remains in Cloudflare and is not configured on these RFC2136 writers.

## Recovery and Validation

Run `task dns:technitium:repair` after the peer Services are deployed, and whenever a peer shows `Unreachable`. The task authenticates with the existing Doppler-managed password without printing it, repoints both nodes to their stable Service IPs, and resyncs the secondary.

Validate with:

```bash
task dns:technitium:repair
dig +short minecraft.krapulax.home @10.0.40.53
```

Both replicas must report the primary as `Connected`; the final query must return `10.0.40.112`.

## Rollback

-   Delete or disable `kubernetes/argo/apps/infra-cluster/network/technitium-infra.yaml`.
-   Delete or disable `kubernetes/argo/apps/app-cluster/network/technitium-dns.yaml` and `kubernetes/argo/apps/infra-cluster/network/technitium-dns-infra.yaml`.
-   Point the home router DHCP DNS option back to the previous resolver.
-   Remove `10.0.40.53/32` from the infra Cilium LoadBalancer pool if unused.
-   Delete the `technitium-peer-*` Services only after moving the cluster peers to replacement stable addresses.
-   Local config remains in retained static node-local PVs for inspection or restore.
