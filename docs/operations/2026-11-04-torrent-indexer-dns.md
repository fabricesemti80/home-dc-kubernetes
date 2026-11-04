# Torrent indexer DNS, 2026-11-04

## Problem

Prowlarr only has The Pirate Bay, so several shows have a single thin swarm. Adding more public indexers failed with "Connection refused": from inside the cluster the indexer domains resolve to `0.0.0.0`. The nodes use the public resolvers 1.1.1.1, 1.0.0.1 and 8.8.8.8, and all three return `0.0.0.0` for these names from this network (the cause on that path was not investigated). Technitium (10.0.40.53) returns real addresses for the same names.

## Change

The default CoreDNS server block (`kubernetes/apps/app-cluster/kube-system/coredns/values.yaml`) gets four extra `forward` stanzas, one per zone (`forward` accepts a single FROM zone), that send these zones and their subdomains to Technitium. Everything else keeps using the node resolvers.

It has to be inside the default block rather than a separate zone block (first tried in #514, which did not work): pods ask for `knaben.org` through the search-path suffixes first, and the `autopath` plugin of the default block resolves those through its own chain. It accepted the public resolvers' `0.0.0.0` answer before a separate zone block was consulted. `krapulax.home` works as a separate block only because the public resolvers answer NXDOMAIN for it, so `autopath` moves on.

| Zone                   | Prowlarr indexer     | HTTPS check through Technitium's answer |
| ---------------------- | -------------------- | --------------------------------------- |
| `knaben.org`           | Knaben (meta-search) | 200                                     |
| `uindex.org`           | Uindex               | 200                                     |
| `limetorrents.fun`     | LimeTorrents         | 200                                     |
| `torrentdownloads.pro` | Torrent Downloads    | 200                                     |

Checked and left out: EZTV answers HTTP 451 from this network, and 1337x and kickasstorrents sit behind a Cloudflare challenge (Prowlarr needs a solver proxy for those; none is configured).

Prowlarr itself is configured through its UI/API, not Git: add the four indexers, keep the default app sync profile so Sonarr and Radarr receive them, and use priority 25 (same as the existing ones).

## Assumptions and security impact

-   Only DNS answers change, and only for four domains. TLS validation is untouched. Technitium becomes the resolver for those four zones; if it is unreachable, cached answers are served stale and an uncached name fails (as for `krapulax.home`).
-   The sites are reachable once resolved: verified with an HTTPS request to the address Technitium returned.
-   A domain must only be added here after the same reachability check.

## Validation

1. Render: `helm template coredns oci://ghcr.io/coredns/charts/coredns --version 1.50.0 -f kubernetes/apps/app-cluster/kube-system/coredns/values.yaml` shows four `forward <zone> 10.0.40.53` lines before `forward . /etc/resolv.conf`.
2. Behaviour (before merge, CoreDNS v1.15.0 in a container with the rendered block, minus the `kubernetes` and `autopath` plugins that need a cluster): the four zones resolve to real addresses, `thepiratebay.org` (not covered) and other names are unchanged, `AAAA` is empty. A single `forward` with several FROM zones silently did not work, which is why there is one stanza per zone.
3. After merge: Argo `coredns` Healthy; from a pod `getent hosts knaben.org` returns a non-zero address; Prowlarr "Test All" passes for the new indexers.

## Rollback

Revert the commit; Argo rolls CoreDNS back. In Prowlarr delete the added indexers (Sonarr and Radarr drop their synced copies).
