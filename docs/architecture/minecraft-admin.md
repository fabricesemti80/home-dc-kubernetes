# Minecraft administration rollout

Decision date: 2026-09-12. Environment: lab (app-cluster).

## Context and goals

Add browser-based RCON commands, user permissions and scheduled commands while Argo owns the Minecraft Deployment. This does not provide world-file editing, mod uploads or Kubernetes lifecycle controls.

## Proposed architecture

The app-template 5.0.1 chart deploys one Minecraft Admin instance in `gaming`, using the pinned `ghcr.io/tekikaito/mc-admin:v1.3.3` image digest. It provides a focused Minecraft dashboard, player controls, whitelist actions and RCON console. It has no world-data mount or persistent state: Argo remains the sole owner of the Minecraft workload and its files.

Cloudflare's existing wildcard tunnel forwards to Envoy's `envoy-external` HTTPS listener. `minecraft-admin.krapulax.dev` routes to Service port 80. Cloudflare Access provides browser authentication; the dashboard itself has no separate public listener or WebSocket hostname.

The existing world PVC and server remain in `gaming`. The UI connects to `minecraft-rcon.gaming.svc.cluster.local:25575`; the LAN LoadBalancer continues exposing only game port 25565. No shared world mount is added.

## Assumptions and access control

-   Argo's app-cluster discovery includes the new Application directory; app-template is allowed by the `kubernetes` project.
-   CephFS, Doppler, Reloader, external-dns and Envoy are operational. The gateway accepts routes from `gaming`.
-   Create `RCON_PASSWORD` in Doppler project `home-dc-kubernetes`, config `apps`, before syncing. No default password is supplied.
-   Doppler projects the same RCON password into the two application Secrets in `gaming`. Secret values remain outside Git.
-   Treat access as privileged: RCON can stop the server, change players and mutate the world.
-   Cloudflare Access restricts the dashboard hostname. This change retains the existing Access policy and does not create a second application or hostname.
-   ClusterIP prevents LAN/WAN exposure of RCON but does not isolate it from other pods. No new NetworkPolicy is introduced; the password remains required.

## Rotation and availability

Both controllers carry workload-level Reloader annotations. When Doppler updates each Secret, Reloader restarts the consumer. Minecraft uses Recreate and a 120-second termination grace period to avoid two world writers and allow graceful saving. Rotate the shared RCON password during a maintenance window.

## Backup and rollback

The dashboard has no persistent data. Take a world backup before maintenance. Do not delete or migrate the existing world PVC.

For rollback, revert the Argo Application source to the RCON Web Admin manifest and sync. The new deployment/service then prunes, while the previous UI resources are recreated. Revert the server RCON additions only during a maintenance window; retain its Recreate strategy for safe restarts.

## Validation criteria

1. Render both Kustomizations and the app-template chart. Check Service backend names/ports and secret references; run repository lint and inventory checks.
2. Confirm both managed Secrets contain `RCON_PASSWORD` without printing values; confirm Argo sync and Deployment Ready status.
3. Verify the HTTPRoute reports Accepted and ResolvedRefs, DNS points through the tunnel, and the existing Cloudflare Access policy admits the dashboard.
4. Use the dashboard to list players, update a whitelist entry and run `list`. Confirm the LAN game endpoint still works and RCON is absent from the LoadBalancer ports.
5. Rotate the RCON password during maintenance. Verify both workloads restart, only one Minecraft pod writes the world, and `list` succeeds again without manual password edits.
6. Confirm Argo prunes the obsolete WebSocket HTTPRoute and the unused UI PVC.

## Next actions

-   [ ] Take a world backup.
-   [ ] Merge and sync during a maintenance window.
-   [ ] Verify dashboard controls, password rotation and LAN play.
