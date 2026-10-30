#!/bin/sh
# Init-container only: no data is written into the original photo filesystem.
set -eu
umask 077
PGHOST=$(cat /stage/source-ip)
export PGHOST

fail() {
  echo "Photo-set metadata capture failed at $1; private diagnostics suppressed." >&2
  exit 1
}

# psql keeps this transaction alive while its child pg_dump imports the snapshot.
# A child-shell failure is separately checked: psql's \! is not ON_ERROR_STOP.
psql -X -v ON_ERROR_STOP=1 -At >/stage/session.log 2>/stage/error.log <<'SQL' || fail transaction
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT pg_export_snapshot() AS exported_snapshot \gset
\setenv K8UP_PG_SNAPSHOT :exported_snapshot
\o /stage/original-refs.jsonl
SELECT json_build_object('path',"originalPath",'sha1',encode(checksum,'hex')) FROM asset ORDER BY id;
\o
\! sh -ec 'printf "%s" "$K8UP_PG_SNAPSHOT" > /stage/pg-snapshot-id; sh /scripts/postgres_export.sh > /stage/database.tar; touch /stage/database.complete'
COMMIT;
SQL

test -f /stage/database.complete || fail database-export
test -s /stage/database.tar || fail database-export
test -f /stage/original-refs.jsonl || fail original-references
reference_hash=$(sha256sum /stage/original-refs.jsonl)
reference_hash=${reference_hash%% *}
printf '{"format":1,"kind":"immich-photo-set","app":"immich-photos","phase":"seed-only","references_sha256":"%s","capture_method":"exported-repeatable-read-snapshot"}\n' "$reference_hash" >/stage/photo-set.json
rm -f /stage/source-ip /stage/session.log /stage/error.log /stage/database.complete
