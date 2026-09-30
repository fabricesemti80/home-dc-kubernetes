# CoreDNS IPv4-only policy

## Decision

The app cluster is IPv4-only: Cilium has IPv6 disabled and nodes have no IPv6 default route. CoreDNS therefore returns an empty `NOERROR` response for `AAAA` queries, while continuing to resolve `A` and all other records normally. This prevents workloads from selecting unreachable IPv6 endpoints without pinning external service IP addresses.

## Assumptions and security impact

-   No workload requires IPv6 egress or IPv6-only DNS records.
-   The policy changes DNS answers only; it does not expose services, alter credentials, or bypass TLS validation.
-   A future dual-stack rollout must remove this policy after IPv6 addressing, routing, and Cilium support are verified end-to-end.

## Validation and rollback

Validate that `AAAA` returns no addresses and `A` still resolves from a pod, then confirm `jellyfin` and `coredns` are `Healthy` in Argo CD.

Revert this change to restore upstream `AAAA` responses. Do that only after IPv6 egress is available, or if a workload needs IPv6 and the cluster is upgraded to dual-stack.
