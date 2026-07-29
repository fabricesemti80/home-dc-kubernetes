#!/usr/bin/env bash
set -euo pipefail

SOURCE_PROJECT="${SOURCE_PROJECT:-project-homelab}"
SOURCE_CONFIG="${SOURCE_CONFIG:-dev_homelab}"
TARGET_PROJECT="${TARGET_PROJECT:-home-dc-kubernetes}"
APPS_CONFIG="${APPS_CONFIG:-apps}"
INFRA_CONFIG="${INFRA_CONFIG:-infra}"

apps_secrets=(
  GITHUB_APP_ID
  GITHUB_APP_INSTALLATION_ID
  GITHUB_APP_PRIVATE_KEY
  IMMICH_DB_PASSWORD
  SONARR_API_KEY
  RADARR_API_KEY
  SLACK_WEBHOOK_MONITORING
  TUNNEL_TOKEN_APPS
  CODE_SERVER_PASSWORD
  DATABASE_URL
  NEXTAUTH_URL
  NEXTAUTH_SECRET
  LINKWARDEN_DB_PASSWORD
  N8N_ENCRYPTION_KEY
)

infra_secrets=(
  KESTRA_BASIC_AUTH_USERNAME
  KESTRA_BASIC_AUTH_PASSWORD
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_DB
  USERDB_USER
  USERDB_PASSWORD
  ROOT_ACCESS_KEY
  ROOT_SECRET_KEY
  HOMELAB_SSH_PRIVATE_KEY
  HOMELAB_SSH_KNOWN_HOSTS
  PULSE_INFRA_TOKEN
  PULSE_AUTH_USER
  PULSE_AUTH_PASS
  UPTIME_KUMA_USERNAME
  UPTIME_KUMA_PASSWORD
  TUNNEL_TOKEN_INFRA
  TAILSCALE_OAUTH_CLIENT_ID
  TAILSCALE_OAUTH_CLIENT_SECRET
)

function copy_secret() {
  local name="$1"
  local target_config="$2"

  printf 'copying %s -> %s/%s\n' "${name}" "${TARGET_PROJECT}" "${target_config}"
  doppler secrets get "${name}" \
    --project "${SOURCE_PROJECT}" \
    --config "${SOURCE_CONFIG}" \
    --plain |
    doppler secrets set "${name}" \
      --project "${TARGET_PROJECT}" \
      --config "${target_config}" \
      --no-interactive \
      >/dev/null
}

function verify_secret() {
  local name="$1"
  local target_config="$2"

  doppler secrets get "${name}" \
    --project "${TARGET_PROJECT}" \
    --config "${target_config}" \
    >/dev/null
  printf 'verified %s/%s:%s\n' "${TARGET_PROJECT}" "${target_config}" "${name}"
}

command -v doppler >/dev/null

for name in "${apps_secrets[@]}"; do
  copy_secret "${name}" "${APPS_CONFIG}"
done

for name in "${infra_secrets[@]}"; do
  copy_secret "${name}" "${INFRA_CONFIG}"
done

for name in "${apps_secrets[@]}"; do
  verify_secret "${name}" "${APPS_CONFIG}"
done

for name in "${infra_secrets[@]}"; do
  verify_secret "${name}" "${INFRA_CONFIG}"
done

printf 'done: copied Doppler secrets from %s/%s to %s/{%s,%s}\n' \
  "${SOURCE_PROJECT}" "${SOURCE_CONFIG}" "${TARGET_PROJECT}" "${APPS_CONFIG}" "${INFRA_CONFIG}"
