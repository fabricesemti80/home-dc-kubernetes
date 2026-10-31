# Backrest backup replacement

## Decision and assumptions

Replace K8up and the custom capture/recovery framework with upstream Backrest. Argo owns deployment, source plans and credential references; Backrest owns scheduling, Restic checks, retention, notifications and the restore UI. Use the existing `10.0.40.2:/k8s-backup` export directly; no S3 gateway is needed.

-   One independent instance per cluster in `backups`: `backrest.krapulax.home` (app) and `backrest-infra.krapulax.home` (infra). Internal HTTPRoutes only; no Cloudflare/public route. Native authentication remains enabled.
-   Run as the tested NAS writer UID 1004 / GID 65534. Backrest itself has no host mounts, privileged containers, Kubernetes API credentials or cluster-wide data reader.
-   Separate new encrypted repositories: `<cluster>/backrest/repository`. Never import old K8up repositories into automatic retention.
-   Mount the export without Kubernetes `subPath`: root-squashed kubelet preparation cannot traverse private UID-1004 directories. The application resolves its cluster prefix as UID 1004. This is not a strong cross-cluster filesystem boundary; both NAS clients already trust that numeric identity.
-   Backrest state and export staging use a retained local-path PVC, on a fixed worker. Existing app storage, original media/photos and physical infra Talos configuration remain unchanged.
-   Repository keys and UI credentials live in Doppler; repository keys also have independent macOS Keychain copies. Git contains neither passwords nor password hashes.
-   Configuration/plans are generated from Git plus Secrets at startup. Git is authoritative; UI configuration edits are not a substitute for changing Git. Backrest can maintain its runtime operation history and repository identity on its state PVC.

## Protection contract

The replacement must preserve the currently deployed Immich and LiteLLM logical database coverage. Small ordinary Kubernetes CronJobs run the matching native PostgreSQL client every six hours. They validate the dump, include roles and explicit application recovery credentials, and atomically publish one archive to the Backrest instance's local staging volume. No live PGDATA copy is made. Backrest refuses a database plan whose validated export is missing or older than eight hours.

The app instance also backs up the scoped `/media/immich` original tree read-only each day, and both instances back up their own configuration. Originals are a separate plan: an online file snapshot and a database export are **not** advertised as one paused, matched Immich recovery point. Recovery must select compatible database/photo points and verify referenced originals before production promotion.

## Application configuration coverage

Backrest cannot mount another namespace's PVC or another worker's local volume, and a host mount of the local-path root is rejected: apps run as root, so a UID-1004 reader cannot traverse their files, and giving the UI pod root/host access widens its blast radius. Instead, the Helm chart `kubernetes/charts/app-protect` renders one daily CronJob per app **in the app's namespace, pinned to the volume's node**. Two containers: a root `snapshot` init (source mounted read-write solely so SQLite can take WAL read locks; non-database files are only read; only CHOWN/DAC_OVERRIDE/FOWNER) copies the volume to an emptyDir, minus disposable paths, and requires `PRAGMA integrity_check` to pass on every copied SQLite file (retry x3, fail closed); a UID-1004 `publish` container atomically swaps it into `/k8s-backup/<cluster>/exports/<app>/current` with a `.captured-at` marker. Backrest plans `app-<name>` snapshot that directory; their start hook refuses exports older than 26h. Inventories: `kubernetes/apps/<cluster>/storage/app-protect/values.yaml` (Argo apps `app-protect`, `app-protect-infra`).

-   app-cluster: sonarr, radarr, prowlarr, jellyseerr, sabnzbd, qbittorrent, recyclarr, jellyfin (`/config`, excluding caches/logs/MediaCover/Jellyfin `metadata`).
-   infra-cluster: technitium-0, technitium-1 (each pod's own PVC, never the Service), pulse, autokuma.
-   Not covered: Uptime Kuma (embedded MariaDB; needs `mariadb-dump`, a file copy is invalid), Immich config (no config volume; DB and originals have their own plans), caches/redis/media.

Opt-out: set `protect: false` on the app entry in the values file (default is protected) and remove its `app-<name>` plan from `config.json`. Kubernetes labels are not used: label-driven enrollment needs an admission mutator (Kyverno) or an operator with cluster-wide read/create-Job RBAC, both rejected above.

Consistency and risk: SQLite databases are captured through SQLite's online backup API (one read transaction, transactionally consistent while the app runs, then `integrity_check`); other files are plain copies, and the app is not quiesced (no shutdown), so multi-file state across separate files is crash-consistent only. Servarr's own scheduled `Backups/` zips are included and are the stronger restore point. Exports sit as plaintext, UID-1004/0700 files on the NAS (they include API keys/credentials) before Restic encrypts them; this is the same NAS trust boundary as the repository ownership. File ownership is normalised to 1004:65534; re-chown on restore (apps run as root).

## Security and consistency

-   DB export credentials are read-only dedicated PostgreSQL logins; original app credentials are not rotated. Recovery credentials are stored only in private staging and encrypted snapshots, never Git/logs.
-   Failed exporters must not update the published archive's timestamp. Temporary artifacts are private and cleaned on failure. Backrest start hooks fail closed on stale/missing exports.
-   Restore into a fresh destination. The UI must not have writable mounts of originals or production application data. Reviewed database import remains necessary after restoring its archive.
-   Keep Restic locks; `autoUnlock` is false. Backrest alone manages its new repositories. Database, originals and Backrest-config plans keep 24 hourly, 14 daily, 8 weekly and 12 monthly representatives; `app-*` config plans keep 14 daily, 8 weekly and 6 monthly; weekly pruning never targets legacy repositories.
-   NAS writable clients can still delete backups. This is local recovery, not offsite protection or immutability. Offsite and external dead-man monitoring remain explicitly deferred.

## Ordered cutover and cleanup

1. Preserve all current implementation in pushed branch `backup/k8up-before-backrest-20261030` (archive commit `94abc54`).
2. Merge the Backrest PR and let Argo deploy both authenticated instances, native export CronJobs and internal DNS routes. New and old repositories are disjoint, so overlap does not create competing retention managers.
3. Run the native exporters, execute Backrest plans and inspect fresh source timestamps. Restore both database archives and import them into fresh isolated databases using matching images/extensions; restore representative original photos and compare hashes. Verify authentication and internal DNS/UI.
4. Only after replacement recovery evidence exists, retire orphaned K8up resources and erase the explicitly enumerated old backup directories. Never delete the NFS export, NAS account/ACLs, original `/media` contents, retained source volumes, or the new `backrest` prefixes. Cleanup must refuse while old backup jobs are active or replacement evidence is absent.
5. Old application database backup roles and Doppler/Keychain recovery keys are removed only after retirement and repository deletion. Keep keys while any old snapshot remains.

Deleting an Argo Application without a cascading finalizer can leave workloads behind. Removal of legacy Git definitions alone is not evidence that operators/schedules have stopped; the retirement task must inspect and remove their runtime resources explicitly.

## Validation and rollback

Before merge: render both app-template deployments; server-dry-run destination configuration; run the pinned Backrest binary with generated configuration, prove authenticated access, a real backup, and byte-identical restore. Check exporter failure leaves the previous published archive untouched. Do not stop production applications for these checks.

After merge: verify Argo health, DNS and actual browser access; native database export/import checks and photo restore checks gate destructive cleanup. Record exact snapshot IDs, source capture times and results rather than a generic success flag.

Rollback before cleanup: revert the Backrest deployment PR or suspend its plans, preserve new repositories and keys, and restore the archived K8up definitions if necessary. Never erase data as rollback. After old repositories are erased, the archive branch restores code only—not deleted backup data.

Upstream references: [Backrest setup](https://garethgeorge.github.io/backrest/introduction/getting-started), [hooks and fatal failures](https://garethgeorge.github.io/backrest/docs/hooks), [restore UI](https://garethgeorge.github.io/backrest/introduction/restore-files).
