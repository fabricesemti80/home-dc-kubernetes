# Minecraft administration rollout

Decision date: 2026-09-12. Environment: lab (app-cluster).

## Context and goals

Add browser-based RCON commands, user permissions and scheduled commands while Argo owns the Minecraft Deployment. This does not provide world-file editing, mod uploads or Kubernetes lifecycle controls.

## Proposed architecture

The app-template 5.0.1 chart deploys one RCON Web Admin instance in `gaming`, using image `itzg/rcon:0.14.1-1`. Its 1Gi CephFS configuration PVC stores accounts, server credentials and dashboard state. Recreate updates prevent concurrent database writers.

Cloudflare's existing wildcard tunnel forwards to Envoy's `envoy-external` HTTPS listener. `minecraft-admin.krapulax.dev` routes to Service port 80, while its `/ws` path routes to port 4327 for browser WebSockets. Keeping the WebSocket same-origin means Cloudflare Access uses the UI's authenticated session. Homepage displays only the UI.

The existing world PVC and server remain in `gaming`. The UI connects to `minecraft-rcon.gaming.svc.cluster.local:25575`; the LAN LoadBalancer continues exposing only game port 25565. No shared world mount is added.

## Assumptions and access control

-   Argo's app-cluster discovery includes the new Application directory; app-template is allowed by the `kubernetes` project.
-   CephFS, Doppler, Reloader, external-dns and Envoy are operational. The gateway accepts routes from `gaming`.
-   Create `RCON_PASSWORD` and `RCON_WEB_ADMIN_PASSWORD` in Doppler project `home-dc-kubernetes`, config `apps`, before syncing. No default password is supplied.
-   Doppler projects the same RCON password into the two application Secrets in `gaming`. The UI password is projected only into the UI Secret. Secret values remain outside Git.
-   Login is `admin` with the Doppler UI password. Treat this account as privileged: RCON can stop the server, change players and mutate the world.
-   HTTPS and the tunnel do not themselves restrict who can reach the login. Configure Cloudflare Access for the admin hostname if identity gating is required, and verify the same-origin WebSocket through it. This PR does not create an Access policy.
-   ClusterIP prevents LAN/WAN exposure of RCON but does not isolate it from other pods. No new NetworkPolicy is introduced; the password remains required.

## Rotation and availability

Both controllers carry workload-level Reloader annotations. When Doppler updates each Secret, Reloader restarts the consumer. Minecraft uses Recreate and a 120-second termination grace period to avoid two world writers and allow graceful saving. UI updates also use Recreate. The two Secret updates are asynchronous: rotation briefly interrupts game/admin access, then the UI reconnects after both consumers restart. Rotate during a maintenance window.

The image re-applies the environment-configured account and server when starting; UI edits to those bootstrap entries can be overwritten on restart. Additional UI state remains on the configuration PVC.

## Backup and rollback

The UI database contains credentials and needs protected backups. CephFS persistence alone is not a backup; no scheduled snapshots or off-cluster backups are added here. Take a world backup before the initial restart and a UI PVC snapshot/backup before upgrades. Verify that retained backups can be restored. Do not delete or migrate the existing world PVC.

For rollback, first remove the two HTTPRoutes to withdraw administration access, then disable automated sync and remove the new Application with resource preservation (non-cascading) so the UI PVC survives. Remove the UI workload/services separately and retain its PVC until recovery is no longer needed. Revert the server RCON additions and sync during a maintenance window; retain its Recreate strategy for safe restarts. Delete obsolete Doppler projections only after their consumers are removed. Restore UI state from a retained PVC/backup if necessary; reconcile restored credentials with Doppler before starting.

## Validation criteria

1. Render both Kustomizations and the app-template chart. Check Service backend names/ports, secret references and PVC mounts; run repository lint and inventory checks.
2. Confirm both managed Secrets contain the expected keys without printing values; confirm Argo sync and PVC Bound status.
3. Verify both HTTPRoutes report Accepted and ResolvedRefs, DNS points through the tunnel, HTTPS login works, and the browser WebSocket upgrades successfully at `/ws`.
4. Run `list` through the console and verify its response. Check Homepage and AutoKuma. Confirm the LAN game endpoint still works and RCON is absent from the LoadBalancer ports.
5. Rotate the RCON password during maintenance. Verify both workloads restart, only one Minecraft pod writes the world, and `list` succeeds again without manual password edits. Rotate the UI password and verify login with the new value.
6. Record a successful backup restore test before relying on this for recovery.

## Next actions

-   [ ] Populate Doppler keys and take a world backup.
-   [ ] Merge and sync during a maintenance window.
-   [ ] Verify HTTPS/WebSocket login, console commands, rotation and LAN play.
-   [ ] Configure and test protected backups and any required Cloudflare Access policy.
