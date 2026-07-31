# Technitium Infra Rollout

## Tasks

-   [x] Add Technitium as a two-replica infra-cluster StatefulSet.
-   [x] Store each replica's state on retained static node-local PVCs.
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
kubectl get pv technitium-config-0 technitium-logs-0 technitium-config-1 technitium-logs-1
dig @10.0.40.53 krapulax.home SOA
kubectl rollout status deploy/technitium-dns -n network --context app-cluster
kubectl rollout status deploy/technitium-dns-infra -n network --context infra-cluster
```

Then initialize clustering in the Technitium UI:

1. Port-forward the primary pod: `kubectl -n network port-forward pod/technitium-0 5380:5380`.
2. Open `http://127.0.0.1:5380/` and initialize a new cluster.
3. Use `krapulax.home` as the local DNS zone.
4. Stop the first port-forward, then port-forward the secondary pod: `kubectl -n network port-forward pod/technitium-1 5380:5380`.
5. Open `http://127.0.0.1:5380/` and join it to the primary using `technitium-0.technitium-headless.network.svc.cluster.local`.
6. Add a primary `krapulax.home` zone and enable RFC2136 dynamic updates for the Doppler-managed TSIG key.
7. Point the router DHCP DNS option to `10.0.40.53`.
8. Verify `dig @10.0.40.53 jellyfin.krapulax.home`, `dig @10.0.40.53 pulse.krapulax.home`, and `dig @10.0.40.53 dns.krapulax.home`.

## Rollback

```bash
kubectl delete app -n argo-system technitium-infra
```

Then restore the previous router DNS server and revert the Technitium Git changes.
