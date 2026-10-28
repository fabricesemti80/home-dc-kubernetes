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

Media apps in the `media` namespace (Jellyfin, Sonarr, Radarr, Prowlarr, qBittorrent, SABnzbd, Immich, Recyclarr, Jellyseerr) mount `media-library-pvc` for library and download paths while using `local-path` PVCs for their config/state.

## 🤔 Assumptions

-   The NFS server `10.0.40.2` is reachable from all app-cluster worker nodes.
-   The export path `/media` already exists and contains the current shared library.
-   Permissions on the export allow the apps to read/write media files as configured.
-   During the first GitOps sync, the app tunnel only serves the Argo webhook and `cloudflare-dns` is manually synced; no app route is public until backup and restore checks pass.

## ✅ Validation

After Argo syncs:

```bash
kubectl get pv media-library-pv
kubectl get pvc -n media media-library-pvc
kubectl get pods -n media
kubectl describe pod -n media -l app.kubernetes.io/name=jellyfin
kubectl get httproute -n media jellyfin -o yaml
```

Only after the reviewed public cutover, verify routing:

```bash
kubectl get httproute -n media jellyfin -o jsonpath='{.metadata.annotations}'
dig +short jelly.krapulax.dev
curl -I https://jelly.krapulax.dev/
```

If the pod starts but libraries are empty, verify NFS connectivity and path contents from the storage server side.

Before public cutover, a 404 for the hostname is expected. After cutover, if it still returns 404, confirm the DNS record resolves to `external-apps.krapulax.dev` rather than a stale direct tunnel target.

## ↩️ Rollback

-   Remove the external-dns annotations from the app's `HTTPRoute` to withdraw the public hostname.
-   Re-sync the Argo CD application so external-dns can withdraw the record.
-   Remove or tighten the `cloudflare_zero_trust_access_application` rule in `infra/terraform_cloudflare/main.tf` when Cloudflare Access enforcement is desired.
