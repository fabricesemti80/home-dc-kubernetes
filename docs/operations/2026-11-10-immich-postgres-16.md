# Immich database: PostgreSQL 14 to 16, 2026-11-10

## Why

PostgreSQL 14's final release is 2026-11-12. Immich supports PostgreSQL 14 up to (not including) 20 with its VectorChord image. A major version cannot start on the existing data directory, so the upgrade is a logical dump and restore into a fresh volume (the path Immich and its community document: dump, new image on a new empty volume, restore into the `postgres` database, never into `immich` itself).

## Choice

`ghcr.io/immich-app/postgres:16-vectorchord0.4.3-pgvector0.8.1` (digest pinned in the export job). Same VectorChord (0.4.3) and pgvector (0.8.1) as before, so no extension upgrade happens in the same step; only the server major changes. PostgreSQL 16 matches the earlier plan in `docs/TODO.md`; 17 and 18 images exist but 18 also moves the data directory mount. The old image carried pgvecto.rs (`vectors.so` in `shared_preload_libraries`), but the `vectors` extension is not installed in the database, so dropping it loses nothing.

Facts checked before (2026-11-10): database `immich` 222 MB, extensions `vchord 0.4.3`, `vector 0.8.1`, `cube`, `earthdistance`, `pg_trgm`, `plpgsql`, `unaccent`, `uuid-ossp`; roles `postgres` (bootstrap superuser) and `backrest_backup` (read-only login, password set by `task backups:credentials`).

## Procedure (in a window; Immich is down for about 15 minutes)

1. Merge-ready PR (this change): new `immich-postgres16-data-longhorn` claim (20 GiB), database image tag, export job image digest. Old claim `immich-postgres-data-longhorn` stays declared and untouched.
2. Pause Argo (`apps`, `immich`) and suspend `backrest-export-immich-db`. Scale `immich`, `immich-machine-learning`, `immich-redis` to zero; leave the database running.
3. Final native export from PG14 (`task backups:export CLUSTER=app-cluster APP=immich-db`), then `task backups:run … PLAN=immich-db`, then restore that snapshot into a fresh NAS directory (`task backups:restore`) and fully read the dump with `pg_restore --file=/dev/null`.
4. Merge, sync `immich`: the StatefulSet restarts on the PG16 image and the empty claim (initdb with `--data-checksums`, superuser `postgres`, password from `IMMICH_DB_PASSWORD`).
5. Restore from the restored NAS copy with a Job in `backups` (same image, UID 1004): `DROP DATABASE immich` in `postgres`, create roles from `roles.sql` skipping `CREATE ROLE "postgres"`, `pg_restore --exit-on-error --create --dbname=postgres database.dump`. Then `task backups:credentials CLUSTER=app-cluster` to set the `backrest_backup` password.
6. Verify: server version, extension versions, row counts against the baseline, the vchord indexes exist, then scale Immich up and check ping, version, search and a thumbnail job.
7. New native export (now with a PG16 `pg_dump`) and an `immich-db` Backrest run; restore it and fully read it.
8. Resume Argo and the export CronJob.

## Rollback

Until the old volume is deleted: set the database image tag back to `14-vectorchord0.4.3-pgvectors0.2.0` and the claim back to `immich-postgres-data-longhorn` (revert the PR), sync. The old volume was cleanly shut down and holds the data as of the final export; anything written to PG16 afterwards is lost unless exported first. Otherwise restore the `immich-db` snapshot.

Delete `immich-postgres-data-longhorn` (and its kustomization entry) after a few days of normal running.

## Outcome

Done 2026-11-10. Server 16.10, data checksums on, `shared_preload_libraries = vchord.so`.

-   Rehearsal first: the latest snapshot restored into a scratch PG16 pod of the same image (3,518 assets at that time, `vchord 0.4.3`, `vector 0.8.1`, 2 vchord indexes).
-   Final export taken after Immich was stopped: 5,092 assets, 1 user. After the restore into the live PG16 instance: 5,092 assets, 1 user, 0 albums, same extensions (`earthdistance` 1.1 to 1.2 is the bundled contrib bump), 2 vchord indexes. Immich 3.3.6 ping 200, ML `pong`, no errors in the server log.
-   A new native export ran with `pg_dump` 16.10 against server 16.10, and an `immich-db` Backrest backup succeeded. The `backrest_backup` login was re-provisioned with `task backups:credentials`.
-   Snag: the first start failed because initdb refuses a Longhorn (ext4) volume root containing `lost+found`. Fixed with `PGDATA=/var/lib/postgresql/data/pgdata`. It was applied live first (signing was unavailable) and committed afterwards; do not sync the Immich app from a revision without it.
-   Not tested: search relevance and thumbnail generation (left to a UI check).
-   Rollback volume `immich-postgres-data-longhorn` (PG14) kept; delete it after a few days (see `docs/TODO.md`).
