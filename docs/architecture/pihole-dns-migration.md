# Pi-hole DNS Migration

## Decision

Replace the two-replica Technitium DNS deployment with one Pi-hole replica on `10.0.40.53`.

## Constraints

-   Pi-hole does not provide the RFC2136 workflow used by the Technitium ExternalDNS writers.
-   Local `krapulax.home` records therefore become version-controlled static dnsmasq entries.
-   The service keeps `10.0.40.53`; router and client DNS settings do not change.

## Security

-   Only DNS ports are exposed through the LAN LoadBalancer. The web service remains ClusterIP-only and is routed through the existing internal Envoy gateway at `dns.krapulax.home` and Cloudflare path at `dns.krapulax.dev`.
-   The Pi-hole dashboard password is `PIHOLE_WEB_PASSWORD` in Doppler's `home-dc-kubernetes/infra` config; no password or upstream credential is committed.

## Rollout and rollback

1. Merge this PR. Pi-hole remains intentionally unsynced so it cannot contend for `10.0.40.53`.
2. Delete `technitium-infra`, `technitium-dns`, and `technitium-dns-infra` from Argo CD with cascading deletion.
3. Sync the `pihole` Argo application, then verify public plus local names.
4. If validation fails, restore the three Technitium Argo applications; retained Technitium PVCs preserve its state.

## Validation

-   `dig +short jellyfin.krapulax.home @10.0.40.53`
-   `dig +short argo.krapulax.dev @10.0.40.53`
-   `curl -I http://jellyfin.krapulax.home`

Use `argocd app delete <name> --cascade` for each retired application, then `argocd app sync pihole`. Do not delete the retained Technitium PVCs during cutover.

## Next actions

-   [ ] Add each new internal hostname to Pi-hole's static DNS configuration.
-   [ ] Verify router clients and Uptime Kuma after cutover.
