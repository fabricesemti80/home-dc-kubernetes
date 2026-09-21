# Technitium Infra DNS

## Decision

Date: 2026-07-30

Deploy Technitium DNS Server on the infra cluster as a single-replica StatefulSet using the existing `technitium-0` retained static node-local PVC. This removes the failed cluster replication path while preserving RFC2136 updates for `krapulax.home`.

## Assumptions

-   `technitium-0` uses the static `technitium-local` PVs on `infra-cp-01`.
-   The retained `technitium-1` PVs remain unused for recovery and are not deleted by this change.
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

## Single-instance operation

`technitium-0` is the sole authoritative `krapulax.home` server. The public `technitium-dns` LoadBalancer at `10.0.40.53` remains the resolver used by LAN and Tailscale clients.

Create the `krapulax.home` primary zone in Technitium and enable RFC2136 dynamic updates with the Doppler-managed TSIG key. `krapulax.dev` remains in Cloudflare and is not configured on these RFC2136 writers.

## Recovery and Validation

Validate with:

```bash
kubectl rollout status statefulset/technitium -n network
dig +short minecraft.krapulax.home @10.0.40.53
```

The StatefulSet must report `1/1` ready and the final query must return `10.0.40.112`.

## Rollback

-   Delete or disable `kubernetes/argo/apps/infra-cluster/network/technitium-infra.yaml`.
-   Delete or disable `kubernetes/argo/apps/app-cluster/network/technitium-dns.yaml` and `kubernetes/argo/apps/infra-cluster/network/technitium-dns-infra.yaml`.
-   Point the home router DHCP DNS option back to the previous resolver.
-   Remove `10.0.40.53/32` from the infra Cilium LoadBalancer pool if unused.
-   Local config remains in retained static node-local PVs for inspection or restore.
