# 📸 Immich Migration Rollout

## 📌 Design

-   [x] Preserve the original Docker Swarm Immich source as fallback
-   [x] Preserve NFS-backed media files
-   [x] Accept a fresh Immich database rebuild
-   [x] Use the final `photos.krapulax.dev` route in Kubernetes
-   [x] Add an internal-only companion hostname

## 📌 Repo Scaffolding

-   [x] Add Immich migration architecture notes
-   [x] Scaffold Kubernetes Immich manifests
-   [x] Add operator notes for migration and validation
-   [x] Add the Argo CD application

## 📌 Source-Side Operator Steps

-   [ ] Confirm the old Swarm Immich stack still has access to:
    -   `/mnt/media/immich`
-   [ ] Keep the Swarm stack definition and source storage untouched

## 📌 Kubernetes Operator Steps

-   [x] Add `IMMICH_DB_PASSWORD` to Doppler for the Kubernetes Immich app
-   [ ] Open `https://photos.krapulax.dev`
-   [ ] Open `http://photos.krapulax.home`
-   [ ] Complete fresh Immich onboarding
-   [ ] Add the NFS-backed paths as external libraries if needed
-   [ ] Trigger library scan/import
-   [ ] Verify external library access under `/external-library`
-   [ ] Verify assets appear as expected

## 📌 Cutover

-   [ ] Stop or disable the old Swarm Immich service
-   [ ] Switch the public hostname from the Swarm route to Kubernetes
-   [ ] Validate uploads and browsing on the final hostname

## ↩️ Rollback

-   [ ] Remove or disable the Kubernetes Immich app
-   [ ] Leave the old Swarm source and storage untouched
-   [ ] Re-enable the Swarm Immich service on the original hostname
