#!/bin/sh
# Runs in the matching PostgreSQL image; stdout is the validated archive only.
set -eu
umask 077

PGHOST=$(cat /stage/source-ip)
export PGHOST
stage=$(mktemp -d /stage/postgres.XXXXXX)
trap 'rm -rf "$stage"; rm -f /stage/postgres-checksums /stage/postgres-bundle.tar' EXIT HUP INT TERM
cp /stage/source.json "$stage/source.json"

fail() {
  echo "PostgreSQL capture failed at $1; no artifact accepted (private diagnostics suppressed)." >&2
  exit 1
}

set -- --format=custom --file="$stage/database.dump"
if [ -n "${K8UP_PG_SNAPSHOT:-}" ]; then
  set -- "$@" --snapshot="$K8UP_PG_SNAPSHOT"
fi
pg_dump "$@" 2>"$stage/error.log" || fail dump
pg_restore --exit-on-error --file=/dev/null "$stage/database.dump" 2>"$stage/error.log" || fail archive-validation
pg_dumpall --roles-only --no-role-passwords --quote-all-identifiers >"$stage/roles.sql" 2>"$stage/error.log" || fail role-metadata
psql -X -v ON_ERROR_STOP=1 -At >"$stage/database.json" 2>"$stage/error.log" <<'SQL' || fail database-metadata
SELECT json_build_object(
 'format',2,
 'database',current_database(),
 'database_owner',(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()),
 'bootstrap_role',(SELECT rolname FROM pg_roles WHERE oid=10),
 'server_version',current_setting('server_version'),
 'server_version_num',current_setting('server_version_num')::integer,
 'shared_preload_libraries',current_setting('shared_preload_libraries'),
 'captured_at',clock_timestamp(),
 'extensions',(SELECT json_agg(json_build_object('name',extname,'version',extversion)) FROM pg_extension),
 'tablespaces',(SELECT json_agg(spcname) FROM pg_tablespace WHERE spcname NOT IN ('pg_default','pg_global')),
 'schemas',(SELECT json_agg(nspname) FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema')
);
SQL

# Secret mount contents are explicit per app. Dereference only visible key files,
# not Kubernetes AtomicWriter's hidden implementation directories/symlinks.
mkdir "$stage/secrets"
if [ -d /recovery-secrets ]; then
  for group in /recovery-secrets/*; do
    [ -d "$group" ] || continue
    name=${group##*/}
    mkdir "$stage/secrets/$name"
    for key in "$group"/*; do
      [ -f "$key" ] || fail secret-coverage
      cp -L "$key" "$stage/secrets/$name/${key##*/}"
      chmod 0600 "$stage/secrets/$name/${key##*/}"
    done
  done
fi
rm -f "$stage/error.log"
(
  cd "$stage" || fail stage
  find . -type f -exec sha256sum {} + >/stage/postgres-checksums || fail checksums
  mv /stage/postgres-checksums SHA256SUMS || fail checksums
  tar -cf /stage/postgres-bundle.tar source.json database.json database.dump roles.sql secrets SHA256SUMS || fail bundle-creation
  tar -tf /stage/postgres-bundle.tar >/dev/null || fail bundle-validation
)
cat /stage/postgres-bundle.tar
rm -f /stage/postgres-bundle.tar
