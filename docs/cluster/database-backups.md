# Application backup inventory and recovery requirements

The active replacement design is [Backrest](../architecture/backrest.md), with
[operating and restore instructions](../operations/backrest.md). The superseded
K8up implementation and its evidence are preserved in branch
`backup/k8up-before-backrest-20261030`, commit `94abc54`.

Backrest plans cover native Immich/LiteLLM database exports, the read-only Immich
original tree, and Backrest configuration. Deployment definitions are not proof
of a successful scheduled backup or application restore. Servarr, Jellyfin, Jellyseerr, SABnzbd, qBittorrent, Recyclarr, Technitium, Pulse and
AutoKuma configuration is exported daily and snapshotted (see the architecture doc,
"Application configuration coverage"); restore drills for them are still pending.
Uptime Kuma (embedded MariaDB) and the retired archives remain outstanding.
No physical infra node settings or original application storage are changed.

## Verified app-cluster inventory

All sources below are in namespace `media`. Worker abbreviations are **GPU** = `k8s-wrkr-01-gpu`, **W2** = `k8s-wrkr-02`, **W3** = `k8s-wrkr-03`. Local claims must remain on their bound worker unless restored to a new volume. Sizes are observed filesystem usage from `du -sk` converted approximately to MiB, **not** PVC requests or expected compressed backup sizes. Database sizes are PostgreSQL's reported logical database footprint.

| Workload                           | Source and container path                                                                                          | Placement / observed size                    | Protection decision                                                                                                                                                                   |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Immich PostgreSQL                  | `immich-postgres-data`, `/var/lib/postgresql/data`                                                                 | W2; DB about 194 MiB; PG 14.19               | Critical. Logical DB dump, not a live PGDATA file copy. Preserve extension/image compatibility.                                                                                       |
| Immich uploads and external photos | `media-library-pvc`; `/data` = NAS `/media/immich`; `/external-library` = `/media/immich/library`, read-only alias | NFS; size not recursively measured           | Critical. Protect originals and DB as a matched recovery set. Do not copy the alias twice.                                                                                            |
| Jellyfin                           | `jellyfin-config`, `/config`; observed DB `/config/data/data/jellyfin.db`                                          | GPU; about 1,705 MiB; image 10.11.11         | Important. Full stopped config copy is the baseline; native 10.11 backup is an online option after coverage/free-space validation.                                                    |
| Jellyseerr                         | `jellyseerr`, `/app/config`; `db/db.sqlite3` with WAL/SHM                                                          | W3; about 5.4 MiB                            | Important. Consistent SQLite plus settings; stopped whole-directory copy is the baseline.                                                                                             |
| Sonarr                             | `sonarr`, `/config`; `sonarr.db`, `logs.db`                                                                        | W3; about 72 MiB                             | Important. Native backup ZIP, plus verified settings coverage. Retain library definitions, profiles, client/indexer settings and API identity.                                        |
| Radarr                             | `radarr`, `/config`; `radarr.db`, `logs.db`                                                                        | W3; about 122 MiB                            | Same native-export method as Sonarr.                                                                                                                                                  |
| Prowlarr                           | `prowlarr`, `/config`; `prowlarr.db`, `logs.db`                                                                    | W3; about 6 MiB                              | Same native-export method; include application mappings and indexer credentials/tags.                                                                                                 |
| SABnzbd                            | `sabnzbd`, `/config`; `admin/history1.db`                                                                          | W3; about 0.15 MiB                           | Important. Stopped config/admin copy for queue/history consistency. No download payloads in this repository.                                                                          |
| qBittorrent                        | `qbittorrent`, `/config`                                                                                           | W3; about 8 MiB                              | Important. Graceful stopped copy including torrent metadata, fast-resume state, settings and credentials. Match download paths on restore.                                            |
| Recyclarr                          | `recyclarr`, `/config`, with Git-backed `configs/recyclarr.yml` mounted read-only                                  | W3; about 73 MiB                             | Daily config/state copy without an overlapping sync; omit disposable provider caches only after identifying them. Git and Doppler reconstruct declarative inputs.                     |
| Immich model cache                 | `immich-model-cache`, `/cache`                                                                                     | W3; request 10 GiB                           | Exclude from routine backups; models can download again.                                                                                                                              |
| Immich Valkey                      | `immich-redis-data`, `/data`                                                                                       | W2; request 2 GiB                            | Rebuild queues/cache with the matched Immich version after DB recovery; do not replay stale queue state into a restored database. Validate job requeue behavior in the restore drill. |
| Jellyfin cache / transcodes        | `jellyfin-cache`, `/cache`; transient `/transcode`                                                                 | GPU; cache request 20 GiB                    | Exclude; regenerate. Do not confuse with `/config` metadata or watched state.                                                                                                         |
| Shared movies/series/downloads     | `media-library-pvc`, NAS `/media`; download mounts use `downloads/complete` and `downloads/incomplete`             | NFS; claim request 8 TiB is not measured use | Separate NAS media policy. Exclude bulk downloads and replaceable films from config backup scope. Never exclude Immich originals just because they share this claim.                  |

Immich's PostgreSQL image is `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`. Installed extensions observed: `cube`, `earthdistance`, `pg_trgm`, `plpgsql`, `unaccent`, `uuid-ossp`, `vchord`, `vector`. Restore initially to this compatible image and Immich `v3.0.3`; do not restore to plain PostgreSQL or run a newer application's migrations first.

## Verified infra-cluster inventory

The physical nodes and their Talos configuration are unchanged. A PVC-only solution would **miss all three monitoring state directories** below.

| Workload                           | Source and container path                                                              | Placement / observed state                                                                                                          | Protection decision                                                                                                                                                                                 |
| ---------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LiteLLM PostgreSQL                 | `ai/litellm-postgres`, `/var/lib/postgresql/data`                                      | `infra-cp-01`; PG 17.5; `litellm` DB about 12.7 MiB                                                                                 | Critical. Logical database export plus required role/ownership recovery; capture Git settings and secret dependencies.                                                                              |
| Technitium primary                 | `network/config-technitium-0`, `/etc/dns`                                              | `infra-cp-01`; about 88 KiB; image 15.6.2                                                                                           | Critical. Native settings/zone/auth export from this exact instance.                                                                                                                                |
| Technitium additional pod          | `network/config-technitium-1`, `/etc/dns`                                              | `infra-wk-01`; about 84 KiB; image 15.4.0                                                                                           | Critical until ownership is resolved. Back up independently; do not assume its data matches primary.                                                                                                |
| Technitium logs                    | `network/logs-technitium-0` and `network/logs-technitium-1`, `/var/log/technitium/dns` | Respective DNS nodes                                                                                                                | Exclude from config recovery unless a separate audit-retention requirement is agreed.                                                                                                               |
| Pulse                              | hostPath `/var/pulse/data`, mounted `/data`                                            | `infra-wk-01`; about 676 MiB; multiple SQLite DBs, including audit, metrics, notification, resources, deployment and recovery state | Important. Stopped whole-directory copy including encryption/identity material. Independent online copies of several DBs are not automatically a consistent application backup.                     |
| Uptime Kuma                        | hostPath `/var/uptime-kuma/data`, `/app/data`                                          | `infra-wk-01`; about 248 MiB                                                                                                        | Important. `db-config.json` reports **embedded-mariadb**; `/app/data/mariadb` and `mariadb-dump` exist. Do not apply an SQLite backup recipe.                                                       |
| AutoKuma                           | hostPath `/var/autokuma/data`, `/data`                                                 | `infra-wk-01`; about 2 MiB                                                                                                          | Back up with Kuma's stopped recovery set; generated monitor definitions are in Git, but runtime ID mapping is not.                                                                                  |
| Retired Kestra DB and object store | `kestra/kestra-postgres`, `kestra/data-versitygw-0`                                    | Bound, retained, no live consumer                                                                                                   | One archival stopped copy per claim, including original image/config references. No nightly backup of retired services. Preserve until archive restore is checked and deletion separately approved. |
| Released old LiteLLM volume        | PV `pvc-7f6beb16-162f-4b3a-be3a-dd5f20e66542`, former `ai/litellm-postgres`            | Released/Retain on `infra-cp-01`; not the active DB                                                                                 | Inventory/archive separately before any storage cleanup. Do not rebind or delete as part of routine backup rollout.                                                                                 |

**DNS drift found, not changed:** live StatefulSet `technitium` desires one replica. `technitium-1` is an ownerless pod, not a managed second replica; it also runs an older image. Preserve/export both configs and determine serving/zone ownership before reconciling that drift. Backup jobs must address each pod directly, not a load-balanced service that could export either instance. This is not authorization to delete either DNS pod or change DNS ownership.

## Recovery objectives and retention

These are proposed operating targets, **not present guarantees**. Start the recovery clock once the destination cluster/storage and keys are available; a full host rebuild or a large photo restore takes additional time. UTC schedules avoid daylight-saving ambiguity. Stage jobs so cold-copy work does not overlap Recyclarr's existing 04:00 Europe/London sync or heavy NAS operations.

| Class                       | Sources                                                                                   | Proposed frequency / RPO                                                              | Retention                                                                  | Initial restore objective                                                                     |
| --------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Critical DB/config          | Immich DB, LiteLLM DB, both DNS exports                                                   | Every 6 hours, staggered within each six-hour window; RPO ≤6h                         | 14 daily, 8 weekly, 12 monthly; retain pre-upgrade checkpoints separately  | DB/DNS functional recovery within 2h on prepared storage                                      |
| Matched photo recovery sets | Immich DB + original assets + external-library paths                                      | Daily coordinated set; complete-set RPO ≤24h, independent of six-hour DB-only exports | 14 daily, 8 weekly, 12 monthly, subject to measured asset growth           | Start with a measured sample restore; full-library RTO set after throughput/size measurement  |
| Active application state    | Jellyfin, Jellyseerr, Servarr apps, SABnzbd, qBittorrent, Recyclarr, Pulse, Kuma/AutoKuma | Daily, staggered; RPO ≤24h once each consistency method is proven                     | 14 daily, 8 weekly, 6 monthly                                              | One app restored and authenticated within 2h; whole media stack within 4h on prepared workers |
| Retired archives            | Kestra claims and released LiteLLM data                                                   | One reviewed archival capture                                                         | Keep until operator explicitly approves deletion after recovery validation | No running service restored automatically                                                     |
| Platform recovery           | Talos/etcd, bootstrap secrets, Git/Argo recovery bundle                                   | Daily proposed; always before destructive maintenance or schema/cluster upgrades      | 7 daily, 4 weekly, 6 monthly, plus upgrade checkpoints                     | Separate cluster rebuild drill; not part of app-only RTO                                      |

## Enrollment and recovery boundaries

Backrest uses explicit Git-owned plans, not Kubernetes label discovery. Native
database exporters publish validated, atomic archives into private local staging;
Backrest refuses missing or older-than-eight-hour exports. Never back up live
PGDATA, SQLite/WAL or embedded MariaDB directories as ordinary files.

Prefer native Servarr/Jellyfin/Technitium backup APIs after validating their
contents and an actual restore. DNS exports must address each exact instance,
not the load-balanced Service. Do not reconcile the ownerless secondary as a
backup workaround.

Cold-copy apps require graceful shutdown, complete directory capture and safe
restart. Argo self-heal makes unattended scale-to-zero unsafe without separate
coordination. Production shutdowns remain limited to the approved 03:00 UTC
maintenance window; this replacement introduces no automatic app shutdown.

Immich uploads and external originals must be compatible with the recovered DB.
Restore the DB before app migrations; restore original path mappings and verify
referenced file contents. Online daily originals and six-hour DB exports are not
a paused matched recovery set. Coordinate external NAS writers before claiming
that stronger guarantee.

All drills use fresh directories/claims and isolated workloads. Do not let a
restored scheduler send downloads, notifications or DNS updates to production.
Preserve exact database majors/extensions, roles and application credentials.
Restic integrity checks and successful file restores do not replace SQL imports
and authenticated application checks.

The NAS remains a local target: AUTH_SYS trusts numeric identities from allowed
clients, writable clients can delete data, and NAS loss can lose both originals
and backups. Offsite copies, external dead-man alerts, NAS snapshot assurance,
workstation-loss key escrow and platform/etcd rebuild drills remain outstanding.

See the [Backrest runbook](../operations/backrest.md) for merge, restore and
restore-gated legacy repository removal. Never delete retained retired source
volumes as part of removing old backup repositories.
