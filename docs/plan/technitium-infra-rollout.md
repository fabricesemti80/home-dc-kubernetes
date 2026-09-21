# Technitium Infra Rollout

## Tasks

-   [x] Run Technitium as a single-replica infra-cluster StatefulSet.
-   [x] Retain `technitium-0` state on static node-local PVCs and preserve the unused replica-1 PVs for recovery.
-   [x] Expose DNS on `10.0.40.53` with TCP and UDP port `53`.
-   [x] Expose the admin console internally at `dns.krapulax.home`.
-   [x] Add app-cluster and infra-cluster RFC2136 ExternalDNS writers for `krapulax.home`.
-   [x] Keep the initial admin password in Doppler.

## Validation

```bash
kubectl get app -n argo-system technitium-infra
kubectl rollout status statefulset/technitium -n network
kubectl get pods -n network -l app.kubernetes.io/instance=technitium -o wide
kubectl get svc,pvc -n network -l app.kubernetes.io/instance=technitium
kubectl get pv technitium-config-0 technitium-logs-0
dig @10.0.40.53 krapulax.home SOA
kubectl rollout status deploy/technitium-dns -n network --context app-cluster
kubectl rollout status deploy/technitium-dns-infra -n network --context infra-cluster
```

Initialize the primary zone in the Technitium UI:

1. Port-forward the primary pod: `kubectl -n network port-forward pod/technitium-0 5380:5380`.
2. Open `http://127.0.0.1:5380/` and initialize a new cluster.
3. Use `krapulax.home` as the local DNS zone.
4. Add a primary `krapulax.home` zone and enable RFC2136 dynamic updates for the Doppler-managed TSIG key.
5. Point the router DHCP DNS option to `10.0.40.53`.
6. Verify `dig @10.0.40.53 jellyfin.krapulax.home`, `dig @10.0.40.53 pulse.krapulax.home`, and `dig @10.0.40.53 dns.krapulax.home`.

## Rollback

```bash
kubectl delete app -n argo-system technitium-infra
```

Then restore the previous router DNS server and revert the Technitium Git changes.
