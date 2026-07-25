# Tailscale Infra Routers

Deploy one ephemeral Tailscale router pod on every infra-cluster node.

## Architecture

-   A DaemonSet runs `tailscale/tailscale:stable` on each infra node.
-   Pods use host networking and `/dev/net/tun` so each node can advertise routes directly.
-   Advertised subnet routes: `10.0.0.0/16` and `192.168.0.0/16`.
-   Each node advertises itself as an exit node.
-   State uses `emptyDir`, so identity is intentionally ephemeral and recreated on pod replacement.

## Security

-   `TAILSCALE_AUTHKEY` is synced from Doppler (`project-homelab/dev_homelab`).
-   The auth key must be reusable, ephemeral, and preauthorized.
-   The key or tailnet ACLs must allow route and exit-node advertisement, or the routes must be approved in the Tailscale admin UI after deployment.
-   The `network` namespace is labeled privileged because subnet routing requires kernel networking access.

## Validation

1. `kubectl kustomize kubernetes/apps/network/tailscale-infra`
2. Confirm one pod per infra node: `kubectl -n network get pods -l app.kubernetes.io/name=tailscale-infra-router -o wide`
3. Confirm routes and exit nodes in the Tailscale admin UI.
4. Test LAN reachability through Tailscale to both advertised ranges.

## Rollback

1. Revert the PR or delete the `tailscale-infra` Argo Application.
2. Argo prunes the DaemonSet and DopplerSecret.
3. Remove stale ephemeral nodes, routes, or exit-node approvals from the Tailscale admin UI if they remain visible.
