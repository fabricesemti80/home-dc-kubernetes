# Media stack update, 2026-11-04

## Checked

Every image in the media namespace was compared with what is published (Renovate's local lookup with the repository rules, plus a direct registry check of the digest-pinned `latest` images).

| App                                                                       | Before                                | After                             | Note                                                                   |
| ------------------------------------------------------------------------- | ------------------------------------- | --------------------------------- | ---------------------------------------------------------------------- |
| Seerr (was Jellyseerr)                                                    | `fallenbagel/jellyseerr:latest` 2.7.3 | `ghcr.io/seerr-team/seerr:v3.5.1` | The old image is frozen and deprecated; see below                      |
| Immich server and ML                                                      | v3.3.5                                | v3.3.6                            | v3.3.6 stops the ML container sending anonymous telemetry to Microsoft |
| Prowlarr                                                                  | `latest` 2.4.0 (digest)               | `latest` 2.7.0 (digest)           |                                                                        |
| qBittorrent (and its init container)                                      | `latest` 5.2.2 (digest)               | `latest` 5.3.0 (digest)           |                                                                        |
| Sonarr 4.0.20, Radarr 6.4.4, SABnzbd 5.1.3, Recyclarr 8.8.1, Valkey 9.1.3 |                                       |                                   | Already the newest releases                                            |
| Jellyfin 10.11.11                                                         |                                       |                                   | Not changed: major upgrade, see `docs/TODO.md`                         |
| Immich PostgreSQL 14                                                      |                                       |                                   | Not changed: major upgrade, see `docs/TODO.md`                         |

## Why Renovate did not propose Seerr

Jellyseerr was merged with Overseerr into Seerr (`seerr-team/seerr`). The `fallenbagel/jellyseerr` Docker Hub image stopped at 2.7.3 (the newest tag is `2.7.3-deprecated`), so Renovate, which watches the digest of the `latest` tag, had nothing newer to find. Releases 3.x are published as `ghcr.io/seerr-team/seerr`.

## Seerr migration

-   The first start of 3.x migrates the SQLite database in place (one-way). It was tested on a copy of the live config in a local container with no network: migrations 44 to 55, `PRAGMA integrity_check` ok, all 8 requests, 84 media rows and the default Sonarr and Radarr servers preserved, status API ready in 8 seconds.
-   The image runs as UID 1000. The existing volume is root-owned and `local-path` volumes are not chowned by `fsGroup`, so an init container does `chown -R 1000:1000 /app/config`.
-   The strategy is `Recreate` so the old and the new pod never share the database.
-   Names (Argo app, Service, PVC, hostnames, backup entries) are unchanged.

## Before merging

Take fresh snapshots of the stateful apps being changed:

```bash
for a in jellyseerr prowlarr qbittorrent; do
  kubectl -n media create job --from=cronjob/protect-$a protect-$a-premerge
done
task backups:run CLUSTER=app-cluster PLAN=app-jellyseerr
task backups:run CLUSTER=app-cluster PLAN=app-prowlarr
task backups:run CLUSTER=app-cluster PLAN=app-qbittorrent
task backups:run CLUSTER=app-cluster PLAN=immich-db
```

## Rollback

-   Prowlarr, qBittorrent and Immich: revert the commit; their data formats are unchanged by these patch and minor bumps.
-   Seerr: reverting the image is not enough once the database has migrated. Scale the app to zero, restore the pre-merge snapshot with `task backups:restore CLUSTER=app-cluster PLAN=app-jellyseerr SNAPSHOT=<id>` (it restores into a disposable directory, nothing is overwritten), copy `db/` and `settings.json` back into the volume, then revert the commit.
