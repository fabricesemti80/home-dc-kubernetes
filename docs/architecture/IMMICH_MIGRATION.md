# 📸 Immich Migration

## 🎯 Objective

Bring Immich from the legacy Docker Swarm environment into Kubernetes while preserving:

-   the existing NFS-backed photo and video files
-   the original Swarm source as a fallback until Kubernetes has been validated

## 📌 Source Inventory

Legacy Dockerlab layout:

-   Immich uploads and generated files:
    -   `/mnt/media/immich`
-   Immich external library:
    -   `/mnt/media/immich/library`
-   Immich database:
    -   `/mnt/cephfs/docker-shared-data/immich/postgres`
-   Redis:
    -   `/mnt/cephfs/docker-shared-data/immich/redis`
-   ML model cache:
    -   `/mnt/cephfs/docker-shared-data/immich/model-cache`

## 🚚 Migration Strategy

```mermaid
flowchart LR
    subgraph Legacy["Docker Swarm"]
        OldMedia[/NFS Media /mnt/media/immich]
    end
    subgraph K8s["Kubernetes"]
        NewDB[(Fresh Postgres)]
        NewML[Machine Learning]
        NewImmich[Immich Server]
        NewMedia[/NFS subPath immich]
    end
    OldMedia -->|Read-only external library| NewImmich
    NewDB --> NewImmich
    NewML --> NewImmich
    NewMedia --> NewImmich
```

Use a non-destructive fresh-rebuild migration:

1. Build the Kubernetes Immich stack with fresh CephFS-backed service state.
2. Let the new Kubernetes Immich instance create a fresh database and re-import the media from the existing NFS-backed paths.

The old Swarm storage paths remain untouched. No source directories are deleted or repurposed as part of this migration.

## 🗄️ Database Decision

This plan intentionally does **not** preserve the old Immich database.

Implication:

-   albums, people, favorites, and other Immich-managed metadata will be rebuilt from scratch

This is acceptable for the current migration because the priority is to keep the media files in place and to keep the old Swarm source available as fallback.

## 📌 Kubernetes Target Shape

-   Namespace:
    -   `media`
-   Public hostname:
    -   `photos.krapulax.dev`
-   Internal hostname:
    -   `photos.krapulax.home` over HTTP on the internal gateway
-   Components:
    -   `immich-server`
    -   `immich-machine-learning`
    -   `database` as a single-replica `StatefulSet`
    -   `redis`
-   Storage:
    -   NFS `media-library-pvc` reused with subpaths for Immich media
    -   CephFS PVCs for PostgreSQL, Redis, and ML cache

## 💾 Storage Model

-   `/data`
    -   NFS `media-library-pvc`
    -   `subPath: immich`
-   `/external-library`
    -   NFS `media-library-pvc`
    -   `subPath: immich/library`
    -   mounted read-only for migration safety
-   PostgreSQL data
    -   CephFS PVC
-   Redis data
    -   CephFS PVC
-   Machine learning cache
    -   CephFS PVC

## 📌 Cutover Model

Kubernetes Immich now serves the public `photos.krapulax.dev` hostname directly.
It also exposes an internal gateway hostname at `photos.krapulax.home`.

After validation:

1. stop or disconnect the Swarm Immich app
2. switch the public hostname to the Kubernetes route

## 🤔 Assumptions

-   The NFS export still contains the legacy Immich directory at `/media/immich`
-   The cluster can mount the same NFS library currently used by Jellyfin
-   the old Swarm service can be left available as a fallback, but not on the same active hostname

## ✅ Validation

-   Kubernetes Immich app starts on `photos.krapulax.dev`
-   internal access works on `photos.krapulax.home`
-   onboarding completes successfully on a fresh database
-   assets appear after import and/or external library scan
-   the external library path is visible to Immich at `/external-library`
-   source Swarm stack remains untouched and can still be used as fallback

## ↩️ Rollback

-   do not delete or modify the source Swarm stack storage
-   remove the Kubernetes Immich app from Argo if deployed
-   keep the Kubernetes PostgreSQL PVC for inspection unless a clean rebuild is chosen
-   restore `photos.krapulax.dev` to the original Swarm stack if Kubernetes rollback is needed
