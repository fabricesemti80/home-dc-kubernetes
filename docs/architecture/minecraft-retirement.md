# Minecraft Retirement

## Decision (2026-09-30)

Retire the unused Minecraft server and its RCON administration UI from the app cluster. Remove their Argo definitions, workloads, routes, DNS endpoint, Doppler projections, monitoring entry, and operating documentation.

## Post-merge cleanup

The root `apps` Argo Application has pruning disabled, and the two child Applications do not have resource finalizers. After this change merges, remove the live Applications with cascading deletion so Argo removes their managed resources:

```bash
kubectl -n argo-system patch application minecraft-server --type=merge -p '{"metadata":{"finalizers":["resources-finalizer.argocd.argoproj.io"]}}'
kubectl -n argo-system patch application rcon-web-admin --type=merge -p '{"metadata":{"finalizers":["resources-finalizer.argocd.argoproj.io"]}}'
kubectl -n argo-system delete application minecraft-server rcon-web-admin --wait=true
```

Cloudflare and Technitium ExternalDNS use `policy=sync`, so deleting the managed public route and LAN DNS endpoint removes their owned records.

## Data and security

Both PVCs use CephFS, whose reclaim policy is `Retain`. Cascading deletion removes the claims and workloads but preserves their backing volumes and data for recovery. The RCON password projections disappear with their Applications; after cleanup, remove `RCON_PASSWORD` and `RCON_WEB_ADMIN_PASSWORD` from Doppler project `home-dc-kubernetes`, config `apps`, because the repository has no remaining consumers.

## Validation and rollback

-   Confirm both Argo Applications and all Minecraft/RCON Deployments, Services, HTTPRoutes, DNS endpoints, DopplerSecrets, and PVC claims are absent.
-   Confirm Cloudflare no longer returns `minecraft-admin.krapulax.dev` and Technitium no longer returns `minecraft.krapulax.home`.
-   The retained CephFS volumes can be rebound if the workload is restored. Revert this retirement and restore the Applications before deleting retained PVs or their CephFS data.
