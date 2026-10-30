#!/bin/sh
# Native logical export only; never copy running PGDATA.
set -eu
umask 077
mkdir -p /state/exports
stage=$(mktemp -d /tmp/backrest-postgres.XXXXXX)
output=$(mktemp "/state/exports/.${BACKUP_APP}.XXXXXX")
trap 'rm -rf "$stage"; rm -f "$output"' EXIT HUP INT TERM
pg_dump --format=custom --file="$stage/database.dump"
pg_restore --file=/dev/null "$stage/database.dump"
pg_dumpall --roles-only --no-role-passwords --quote-all-identifiers >"$stage/roles.sql"
psql -X -v ON_ERROR_STOP=1 -Atc "SELECT json_build_object('database',current_database(),'server_version',current_setting('server_version'),'bootstrap_role',(SELECT rolname FROM pg_roles WHERE oid=10),'shared_preload_libraries',current_setting('shared_preload_libraries'),'extensions',(SELECT json_agg(json_build_object('name',extname,'version',extversion)) FROM pg_extension));" >"$stage/database.json"
pg_dump --version >"$stage/client-version"
printf '%s\n' "$BACKUP_APP" >"$stage/app"
date -u +%Y-%m-%dT%H:%M:%SZ >"$stage/captured-at"
mkdir -m 700 "$stage/secrets"
for source in /recovery/*; do
  test -f "$source"
  cp "$source" "$stage/secrets/$(basename "$source")"
done
(cd "$stage" && sha256sum database.dump roles.sql database.json client-version app captured-at secrets/* >SHA256SUMS)
tar -C "$stage" -cf "$output" .
tar -tf "$output" >/dev/null
# Rename on the same filesystem: failed producers leave the old archive untouched.
mv -f "$output" "/state/exports/${BACKUP_APP}.tar"
echo "Validated native export published; credentials and database data suppressed."
