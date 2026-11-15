# Immich PostgreSQL 16 to 17 migration

## Decision and assumptions

A PostgreSQL major-version image must not start on the previous major's data directory. Restore a logical export to a fresh retained Longhorn claim, leaving the PostgreSQL 16 claim untouched for rollback. Use `17-vectorchord0.4.3-pgvector0.8.1`; the running PostgreSQL 16 instance has the same VectorChord and pgvector extension versions. Immich's published support range is PostgreSQL 14 through 19. Upgrade the Backrest export client to PostgreSQL 17 in the same cutover: `pg_dump` 16 cannot dump a PostgreSQL 17 server.

## Rehearsal

On 2026-11-15, a fresh `immich-db` native export was backed up as snapshot `ec10cb54f4b0ff8dc13071e4ace109175037187f88e80f460c6fcd1a8155b2da` (Backrest operation 1231) and restored to an isolated NAS directory (operation 1235). A temporary pod initialized PostgreSQL 17.6 using image digest `sha256:79b95b795f0911e95ffa4d092a2162c4d81a984d5629bc8f786afe0bc0657671`, verified the export checksums and imported its custom-format dump and roles. It returned 6,439 assets, one user, zero albums, `vchord 0.4.3`, `vector 0.8.1` and two VectorChord indexes. Counts match the live PG16 query made before that export; new user activity may change counts later. This is a database import rehearsal, not a compatible originals-set restore test.

## Cutover and validation

1. Prepare and review a PR changing the database image, a new 20 GiB retained Longhorn claim and the export image; do not sync it before the final backup and quiescence. Keep `immich-postgres16-data-longhorn` declared.
2. Pause auto-sync on parent `apps`, `immich`, and `backrest-app`; suspend the Immich export CronJob. Stop Immich, its machine-learning deployment and Redis; confirm there are no database clients. Record current counts.
3. Take a fresh native export and `immich-db` Backrest snapshot; restore the exact snapshot into an isolated directory and check its archive checksums and dump before proceeding. Record the operation and snapshot IDs.
4. Merge the reviewed PR and selectively sync only the new PVC and database StatefulSet. The new PG17 volume uses `PGDATA=/var/lib/postgresql/data/pgdata` so ext4 `lost+found` does not block initialization. Keep application deployments stopped.
5. Using a temporary restore job with the PG17 image and the restored archive, authenticate as the existing bootstrap superuser; verify checksums, drop the newly created empty `immich` database, restore `roles.sql` omitting only the bootstrap `CREATE ROLE`, then `pg_restore --exit-on-error --create --dbname=postgres`. Re-provision the read-only backup login using `task backups:credentials CLUSTER=app-cluster` without printing passwords.
6. Compare counts and extension versions to the stopped-source baseline, verify VectorChord indexes and checksums; start applications and verify readiness, API, search and ML. Sync the new Backrest export image, run a fresh export and backup, restore it in isolation and verify the archive. Clean up scratch resources and resume the original Argo policies and export schedule.

## Rollback and security

Until validated, stop Immich, point the StatefulSet back to the PG16 image and `immich-postgres16-data-longhorn` claim and sync the revert. This loses writes made on PG17 after cutover unless separately exported and restored; retain the final PG16 export and backup. Never run both instances against one data directory. Keep credentials in Kubernetes secrets and do not log their values. If a restore or check fails, keep clients stopped and restore the previous service before resuming automation. PG16 volume retention is not an offsite backup.

## Outcome (2026-11-15)

-   Stopped all Immich clients and recorded 6,439 assets, one user, zero albums and zero database clients. Final PG16 backup operation 1236 produced snapshot `e600caec82048992f2371c485d637b98ea5b3f8fe162f1b880ccb4d49471cfcd`; restore operation 1240 succeeded and its archive passed checksums and `pg_restore` read verification.
-   PR #605 was merged during the authorized cutover. The restored PG17 database matched all counts, had `vchord 0.4.3`, `vector 0.8.1` and two VectorChord indexes. The backup login was re-provisioned and authenticated with restricted privileges.
-   Immich and machine-learning ping endpoints returned success. Search and thumbnails were not exercised during this cutover. Argo automation and the export schedule were restored; `apps`, `immich` and `backrest-app` reported Synced and Healthy.
-   A PG17 `pg_dump` export and Backrest backup succeeded (operation 1241, snapshot `981b12c4bd9744ab198c3518eb8a020f8ad8a2dd7c842c2ba437ff70d9fb6ac1`); restore operation 1245 succeeded, and the restored archive passed checksum and dump-read checks. This is not a second database import test.
-   `immich-postgres16-data-longhorn` remains retained for rollback. Reverting to it loses subsequent PG17 writes unless separately migrated. Temporary jobs, pods and isolated restore directories were removed.
