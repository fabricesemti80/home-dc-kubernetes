# Technitium Infra Rollout

## Tasks

-   [x] Add Technitium as an infra-cluster DaemonSet.
-   [x] Store each node's state on local hostPath storage.
-   [x] Expose DNS on `10.0.40.53` with TCP and UDP port `53`.
-   [x] Expose the admin console internally at `dns.krapulax.home`.
-   [x] Add app-cluster and infra-cluster RFC2136 ExternalDNS writers for `krapulax.home`.
-   [x] Keep the initial admin password in Doppler.

## Validation

```bash
kubectl get app -n argo-system technitium-infra
kubectl rollout status daemonset/technitium -n network
kubectl get svc -n network technitium technitium-dns
dig @10.0.40.53 krapulax.home SOA
curl -I http://10.0.40.31:5380/
curl -I http://10.0.40.32:5380/
kubectl rollout status deploy/technitium-dns -n network --context app-cluster
kubectl rollout status deploy/technitium-dns-infra -n network --context infra-cluster
```

Then initialize clustering in the Technitium UI:

1. Open `http://10.0.40.31:5380/` and initialize a new cluster.
2. Use `krapulax.home` as the local DNS zone.
3. Open `http://10.0.40.32:5380/` and join it to the primary using `10.0.40.31`.
4. Add a primary `krapulax.home` zone and enable RFC2136 dynamic updates for the Doppler-managed TSIG key.
5. Point the router DHCP DNS option to `10.0.40.53`.
6. Verify `dig @10.0.40.53 jellyfin.krapulax.home`, `dig @10.0.40.53 pulse.krapulax.home`, and `dig @10.0.40.53 dns.krapulax.home`.

## Rollback

```bash
kubectl delete app -n argo-system technitium-infra
```

Then restore the previous router DNS server and revert the Technitium Git changes.
