# Copyparty Media File Manager Rollout

## Tasks

-   [x] Add app-cluster Copyparty app using app-template.
-   [x] Store Copyparty config on CephFS.
-   [x] Reuse the existing app-cluster `media-library-pvc`.
-   [x] Expose `https://files.krapulax.dev` through the app-cluster Gateway and Cloudflare tunnel.
-   [x] Keep credentials in Doppler.

## Validation

```bash
kubectl get app -n argo-system copyparty
kubectl get pv media-library-pv
kubectl get pvc -n media media-library-pvc
kubectl rollout status deploy/copyparty -n media
kubectl get httproute -n media copyparty -o yaml
dig +short files.krapulax.dev
curl -I https://files.krapulax.dev/
```

Then sign in as `media`, delete a disposable test file from `/media`, and confirm it disappears on the NFS server.

## Rollback

```bash
kubectl delete app -n argo-system copyparty
```

Then revert the Git changes for Copyparty and re-sync the app-of-apps.
