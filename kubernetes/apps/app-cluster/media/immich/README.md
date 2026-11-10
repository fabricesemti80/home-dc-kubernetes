# 📸 Immich Notes

This app is scaffolded for a non-destructive fresh rebuild from the legacy Docker Swarm Immich deployment.

Current intent:

-   keep the old Swarm source storage untouched as fallback
-   serve Kubernetes Immich on `https://photos.krapulax.dev`
-   also expose an internal-only companion hostname at `http://photos.krapulax.home`
-   keep the photo and video files in place on NFS
-   use a fresh Immich database in Kubernetes

Storage layout:

-   `/data`
    -   NFS `media-library-pvc`
    -   `subPath: immich`
-   `/external-library`
    -   NFS `media-library-pvc`
    -   `subPath: immich/library`
    -   mounted read-only
-   PostgreSQL, Redis, and ML cache
    -   Longhorn ReadWriteOnce PVCs `immich-postgres-data-longhorn`, `immich-redis-data-longhorn`, `immich-model-cache-longhorn`; the old local-path claims were deleted on 2026-11-10, see [the migration record](../../../../../docs/operations/local-path-to-longhorn.md#immich-cutover-completed-2026-11-10)

Controller note:

-   the Immich PostgreSQL database runs as a `StatefulSet`
-   this gives the DB a more stable pod and storage identity than a plain `Deployment`

Important migration rule:

-   do not point Kubernetes PostgreSQL at the old Swarm PostgreSQL data directory
-   the old Swarm database is intentionally left untouched as fallback

Route:

-   `https://photos.krapulax.dev`
-   `http://photos.krapulax.home`

Cutover note:

-   the old Swarm service should not keep serving `photos.krapulax.dev` once this route is active
-   expect albums and other Immich metadata to be rebuilt in the new instance
