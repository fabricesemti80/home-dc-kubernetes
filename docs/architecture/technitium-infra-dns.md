# Technitium Infra DNS

## Decision

Date: 2026-07-30

Deploy Technitium DNS Server on every infra-cluster node as a DaemonSet. Each node keeps its own local config under `/var/technitium/dns`; Technitium clustering is responsible for consistency.

## Assumptions

-   Infra nodes are currently `infra-cp-01` and `infra-wk-01`.
-   Control-plane scheduling remains allowed for infra support services.
-   `10.0.40.53` is free on the LAN and should be used as the home-router DNS target.
-   The intended local DNS zone is `krapulax.home`.
-   Doppler `infra` config contains `TECHNITIUM_ADMIN_PASSWORD`.
-   Doppler `apps` and `infra` configs contain the same `TECHNITIUM_RFC2136_TSIG_KEYNAME` and `TECHNITIUM_RFC2136_TSIG_SECRET`.

## Security Impact

-   Recursive DNS is limited to private RFC1918 ranges.
-   The web console is internal-only at `dns.krapulax.home`; port `5380` is also reachable on each node IP for cluster bootstrap.
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

After deployment, initialize a new Technitium cluster on `infra-cp-01`, then join `infra-wk-01` as a secondary. Use node IPs as cluster node addresses:

-   `infra-cp-01`: `10.0.40.31`
-   `infra-wk-01`: `10.0.40.32`

Create the `krapulax.home` primary zone in Technitium, enable RFC2136 dynamic updates with the Doppler-managed TSIG key, and include that zone in the cluster catalog so it replicates across nodes. `krapulax.dev` remains in Cloudflare and is not configured on these RFC2136 writers.

## Rollback

-   Delete or disable `kubernetes/argo/apps/infra-cluster/network/technitium-infra.yaml`.
-   Delete or disable `kubernetes/argo/apps/app-cluster/network/technitium-dns.yaml` and `kubernetes/argo/apps/infra-cluster/network/technitium-dns-infra.yaml`.
-   Point the home router DHCP DNS option back to the previous resolver.
-   Remove `10.0.40.53/32` from the infra Cilium LoadBalancer pool if unused.
-   Local config remains on each node under `/var/technitium/dns` for inspection or restore.
