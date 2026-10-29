# 🗄️ Media NFS Storage

This cluster consumes the existing media library over NFS for workloads such as Jellyfin, Immich, Sonarr, Radarr, and download clients.

## 📌 Design

-   **Source of truth for media files**: existing NFS export at `10.0.40.2:/media`
-   **Kubernetes access model**: static `PersistentVolume` plus namespace-local `PersistentVolumeClaim`
-   **Retention goal**: keep the underlying media library intact even if an app or PVC is deleted
-   **Reclaim policy**: `Retain`
-   **Access mode**: `ReadWriteMany` so multiple media pods can read/write the shared library
-   **App state split**:
    -   NFS is for the large retained media library mounted at `/data`, `/media`, `/downloads`, etc.
    -   Node-local `local-path` volumes are the default for cluster-owned app state (`/config`, databases, caches)

## 📌 Current Consumers

Jellyfin, Sonarr, Radarr, qBittorrent, SABnzbd and Immich mount `media-library-pvc` in namespace `media`. Prowlarr, Recyclarr and Jellyseerr use app-local configuration and access the others over Services; they do not mount the NFS claim. See [the media app setup runbook](../plan/media-app-setup.md) for observed directories, container paths and UI configuration.

## 🤔 Assumptions

-   The NFS server `10.0.40.2` is reachable from all app-cluster worker nodes.
-   The export path `/media` already exists and contains the current shared library.
-   Permissions on the export allow the apps to read/write media files as configured.
-   The public app tunnel routes through TLS-verified Envoy. Immich's `photos.krapulax.dev` is released after verified admin login; Cloudflare Access bypasses challenges for its mobile client, leaving Immich authentication essential. `requests.krapulax.dev` remains blocked (404) pending Jellyseerr first-run security. `cloudflare-dns` remains manually synced. Off-host backups and restores of fresh local-path state remain unverified.

## ✅ Validation

After Argo syncs, use the **app-cluster** kubeconfig (there is no ambient kubectl context):

```bash
kubectl --kubeconfig kubeconfig get pv media-library-pv
kubectl --kubeconfig kubeconfig get pvc -n media media-library-pvc
kubectl --kubeconfig kubeconfig get pods -n media
kubectl --kubeconfig kubeconfig describe pod -n media -l app.kubernetes.io/name=jellyfin
kubectl --kubeconfig kubeconfig get httproute -n media jellyfin -o yaml
```

Verify current public routing only after application authentication is configured; Jellyseerr remains private for first-run setup, while Immich now uses its own login on the public route:

```bash
kubectl --kubeconfig kubeconfig get httproute -n media jellyfin -o jsonpath='{.metadata.annotations}'
dig +short jelly.krapulax.dev
curl -I https://jelly.krapulax.dev/
```

Cloudflare Access may return a login redirect rather than origin content. If an allowed host returns the tunnel's 404, inspect the live tunnel ConfigMap and the app's HTTPRoute; avoid automatically syncing `cloudflare-dns` because of the previous private-IP publication regression.

## ↩️ Rollback

-   Revert the relevant GitOps tunnel/route changes in a reviewed commit or disable the app's public route while retaining the NFS PV and data. To roll back Immich access specifically, restore its exact-host `http_status:404` tunnel rule before the wildcard; leave Jellyseerr's public denial in place until its setup and authentication are verified.
-   Coordinate any DNS change explicitly: `cloudflare-dns` is manually gated because an automatic sync can publish private gateway IPs. Do not delete the retained NFS PV or NAS content during an application rollback.
