# AFFiNE (app-cluster, lab)

AFFiNE is available at `https://notes.krapulax.dev` through the external Envoy Gateway route. The self-hosted server, PostgreSQL with pgvector, and Redis run in the `productivity` namespace. The migration runs as an init container before each server start. The server has one replica and a Recreate strategy because its file storage is local to the deployment's shared PVC.

## Before merging

Add these values to the Doppler `home-dc-kubernetes` / `apps` config:

-   `AFFINE_DB_PASSWORD`: a unique generated password.
-   `DATABASE_URL`: `postgresql://affine:<URL-ENCODED-PASSWORD>@affine-postgres:5432/affine` (use the same password as above; URL-encode reserved characters).

The Doppler operator syncs both values into `productivity/affine-secrets`. No credentials are stored in Git. Verify the secret and PostgreSQL readiness before expecting the server to start. A failed init migration blocks the server startup; check `kubectl -n productivity logs deployment/affine -c migrate`.

## Storage, backup, and rollback

CephFS claims store uploads (`/root/.affine/storage`), AFFiNE config (`/root/.affine/config`) and PostgreSQL (`/var/lib/postgresql/data`). Back up PostgreSQL with `pg_dump` and the storage/config PVCs together. Do not rely on Git rollback to undo schema migrations: restore a matching database backup before rolling back an AFFiNE image. Argo pruning may remove PVCs if the application is deleted; take backups before deletion.

## Validation

-   Confirm the Argo `affine` Application syncs to `app-cluster` and all three controllers become healthy.
-   Confirm the migration init container completes and `https://notes.krapulax.dev` opens and saves a test document.
-   Confirm `notes.krapulax.dev` resolves to the gateway and generated links use HTTPS.
-   Confirm the CephFS claims and PostgreSQL backup job/policy cover this deployment before storing important notes.

The AFFiNE server and migration use the same immutable multi-platform image digest. It was resolved from the upstream `stable` tag on 2026-09-30; update it deliberately after validating upstream requirements and migration compatibility. The official self-hosted Compose reference uses a predeploy migration, Redis, and `pgvector/pgvector:pg16`: https://github.com/toeverything/AFFiNE/blob/canary/.docker/selfhost/compose.yml.
