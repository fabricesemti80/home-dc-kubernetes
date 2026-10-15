# 🗄️ Media NFS Storage

This cluster can consume the existing media library over NFS for workloads such as Jellyfin.

## 📌 Design

-   **Source of truth for media files**: existing NFS export at `10.0.40.2:/media`
-   **Kubernetes access model**: static `PersistentVolume` plus namespace-local `PersistentVolumeClaim`
-   **Retention goal**: keep the underlying media library intact even if an app or PVC is deleted
-   **Reclaim policy**: `Retain`
-   **App state split**:
    -   NFS is for the large retained media library mounted at `/data`
    -   CephFS remains the default for cluster-owned app state such as Jellyfin config and cache

## 📌 Consumers

-   Media applications share the NFS library through a `ReadWriteMany` claim in
    the `media` namespace; their configuration PVCs remain on CephFS.
-   `media/jellyfin` mounts the library at `/data`, and is exposed at
    `https://jelly.krapulax.dev` via the shared `external-apps.krapulax.dev`
    Cloudflare tunnel target and `envoy-external` Gateway.
-   Jellyfin has a dedicated Cloudflare Access application configured for full
    bypass so Jellyfin handles authentication itself.

## Temporary claim recovery (2026-10-15)

The original `media-library-pv` and `media-library-pvc` objects entered deletion
while workloads still referenced the claim. Kubernetes protects the bound
objects with finalizers, so new pods cannot schedule against that claim. Both
objects use `Retain`; the backing NAS export remains intact.

Use `media-library-pv-recovery` and `media-library-pvc-recovery` as a new static
pair pointing at the same `10.0.40.2:/media` export. Move every media consumer to
the recovery claim through Git so existing pods can keep their old mounts while
replacements use the new identity. Sync-wave ordering creates the PV and PVC
before the application workloads. Do not remove finalizers or delete the NFS
export. Retire the old Kubernetes objects only after no pods reference the old
claim; keep the recovered claim until a separately reviewed cleanup.

## 🤔 Assumptions

-   The NFS server `10.0.40.2` is reachable from the cluster nodes
-   The export path `/media` already exists and contains the current shared library
-   Permissions on the export allow Jellyfin to read the media files as configured
-   `external-apps.krapulax.dev` already terminates through the Cloudflare tunnel to the cluster `envoy-external` Gateway
-   external-dns is reconciling `HTTPRoute` hostname annotations into Cloudflare DNS records
-   `jelly.krapulax.dev` is intentionally bypassed at Cloudflare Access while other apps may still enforce Access policies

## ✅ Validation

After Argo syncs:

```bash
kubectl get pv media-library-pv-recovery
kubectl get pvc -n media media-library-pvc-recovery
kubectl get pods -n media
kubectl describe pod -n media -l app.kubernetes.io/name=jellyfin
kubectl get httproute -n media jellyfin -o yaml
```

Then verify public routing:

```bash
kubectl get httproute -n media jellyfin -o jsonpath='{.metadata.annotations}'
dig +short jelly.krapulax.dev
curl -I https://jelly.krapulax.dev/
```

Then verify Access behaviour:

```bash
task tf:cloudflare:plan
curl -I https://jelly.krapulax.dev/
```

Expected result:

-   browsers, mobile apps, and TV clients reach Jellyfin without a Cloudflare Access prompt
-   Jellyfin handles sign-in and authorization itself

If the pod starts but libraries are empty, verify NFS connectivity and path contents from the storage server side.

If the hostname still returns `404`, confirm the DNS record resolves to `external-apps.krapulax.dev` rather than a stale direct tunnel target.

## ↩️ Rollback

-   Keep using the recovery claim until the old PV/PVC deletion has completed; reverting early would return workloads to a terminating claim.
-   After the old objects are gone, restore their original names and claim references in Git, then let Argo sync before removing the recovery pair.
-   Remove the external-dns annotations from `kubernetes/apps/app-cluster/media/jellyfin/config/http-route.yaml`
-   Re-sync the Jellyfin Argo CD application so external-dns can withdraw the record
-   Restore the prior DNS mapping only if a direct Cloudflare tunnel route is intentionally reintroduced
-   Remove or tighten the `cloudflare_zero_trust_access_application.jellyfin` rule in `infra/terraform_cloudflare/main.tf` when you want Cloudflare Access enforcement back
