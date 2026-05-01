#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
docker_root="${repo_root}/infra/docker"

required_vars=(
  TAILSCALE_AUTH_KEY
  CLOUDFLARED_TUNNEL_TOKEN
  ARCANE_ENCRYPTION_KEY
  ARCANE_JWT_SECRET
  PORTAINER_ADMIN_PASSWORD
)

for var in "${required_vars[@]}"; do
  # Optional vars
  if [[ $var == "TAILSCALE_AUTH_KEY" || $var == "CLOUDFLARED_TUNNEL_TOKEN" ]]; then
    continue
  fi
  if [ -z "${!var:-}" ]; then
    printf '%s is not set; inject it via Doppler or the shell environment before rendering Docker runtime secrets\n' "$var" >&2
    exit 1
  fi
done

dotenv_quote() {
  printf "'"
  printf '%s' "$1" | sed "s/'/'\\''/g"
  printf "'"
}

write_dotenv() {
  local env_file="${docker_root}/.env"
  local docker_root_value="${HOMELAB_DOCKER_ROOT:-}"
  local domain="${DOMAIN:-krapulax.dev}"
  local arcane_hostname="${ARCANE_HOSTNAME:-arcane.${domain}}"
  local beszel_hostname="${BESZEL_HOSTNAME:-beszel.${domain}}"
  local uptime_kuma_hostname="${UPTIME_KUMA_HOSTNAME:-uptime.${domain}}"
  local whoami_hostname="${WHOAMI_HOSTNAME:-whoami.${domain}}"
  local portainer_hostname="${PORTAINER_HOSTNAME:-portainer.${domain}}"
  # Included Compose files resolve bind-mount paths relative to their own
  # directories, so the shared Docker root must be explicit.
  if [ -z "$docker_root_value" ]; then
    docker_root_value="$docker_root"
  fi
  {
    printf 'COMPOSE_PROJECT_NAME=%s\n' "$(dotenv_quote "${COMPOSE_PROJECT_NAME:-homelab}")"
    printf 'HOMELAB_DOCKER_ROOT=%s\n' "$(dotenv_quote "$docker_root_value")"
    printf 'HOMELAB_DOCKER_PLATFORM=%s\n' "$(dotenv_quote "${HOMELAB_DOCKER_PLATFORM:-linux/amd64}")"
    printf 'DOMAIN=%s\n' "$(dotenv_quote "$domain")"
    [ -z "${COMPOSE_PROFILES:-}" ] || printf 'COMPOSE_PROFILES=%s\n' "$(dotenv_quote "$COMPOSE_PROFILES")"
    printf 'PUID=%s\n' "$(dotenv_quote "${PUID:-1000}")"
    printf 'PGID=%s\n' "$(dotenv_quote "${PGID:-1000}")"
    printf 'TRAEFIK_CLOUDFLARE_API_TOKEN=%s\n' "$(dotenv_quote "${TRAEFIK_CLOUDFLARE_API_TOKEN:-}")"
    printf 'TRAEFIK_CLOUDFLARE_ZONE_ID=%s\n' "$(dotenv_quote "${TRAEFIK_CLOUDFLARE_ZONE_ID:-}")"
    printf 'TRAEFIK_CLOUDFLARE_EMAIL=%s\n' "$(dotenv_quote "${TRAEFIK_CLOUDFLARE_EMAIL:-}")"
    printf 'TRAEFIK_LOG_LEVEL=%s\n' "$(dotenv_quote "${TRAEFIK_LOG_LEVEL:-DEBUG}")"
    printf 'ARCANE_HOSTNAME=%s\n' "$(dotenv_quote "$arcane_hostname")"
    printf 'ARCANE_APP_URL=%s\n' "$(dotenv_quote "${ARCANE_APP_URL:-https://${arcane_hostname}}")"
    printf 'ARCANE_ENCRYPTION_KEY=%s\n' "$(dotenv_quote "$ARCANE_ENCRYPTION_KEY")"
    printf 'ARCANE_JWT_SECRET=%s\n' "$(dotenv_quote "$ARCANE_JWT_SECRET")"
    printf 'BESZEL_HOSTNAME=%s\n' "$(dotenv_quote "$beszel_hostname")"
    printf 'BESZEL_APP_URL=%s\n' "$(dotenv_quote "${BESZEL_APP_URL:-https://${beszel_hostname}}")"
    printf 'BESZEL_AGENT_KEY=%s\n' "$(dotenv_quote "${BESZEL_AGENT_KEY:-}")"
    printf 'UPTIME_KUMA_HOSTNAME=%s\n' "$(dotenv_quote "$uptime_kuma_hostname")"
    printf 'WHOAMI_HOSTNAME=%s\n' "$(dotenv_quote "$whoami_hostname")"
    printf 'PORTAINER_HOSTNAME=%s\n' "$(dotenv_quote "$portainer_hostname")"

  } >"$env_file"
  chmod 0600 "$env_file"
}
tailscale_dir="${docker_root}/runtime/secrets/tailscale"
cloudflared_dir="${docker_root}/runtime/secrets/cloudflared"
portainer_dir="${docker_root}/runtime/secrets/portainer"
traefik_dynamic_dir="${docker_root}/runtime/traefik/dynamic"

mkdir -p "$tailscale_dir" "$cloudflared_dir" "$portainer_dir" "$traefik_dynamic_dir"
chmod 700 "${docker_root}/runtime" "${docker_root}/runtime/secrets" "$tailscale_dir" "$cloudflared_dir" "$portainer_dir"

# Remove generated files from the retired Omni deployment so local Compose runs
# do not keep publishing stale Traefik routes or secret mounts.
rm -f "${traefik_dynamic_dir}/omni.yml"
rm -rf "${docker_root}/runtime/secrets/omni"

if [ -n "${TAILSCALE_AUTH_KEY:-}" ]; then
  printf '%s\n' "$TAILSCALE_AUTH_KEY" >"${tailscale_dir}/auth_key"
  chmod 0600 "${tailscale_dir}/auth_key"
fi

if [ -n "${CLOUDFLARED_TUNNEL_TOKEN:-}" ]; then
  secret_file="$(mktemp)"
  trap 'rm -f "$secret_file"' EXIT
  printf '%s\n' "$CLOUDFLARED_TUNNEL_TOKEN" >"$secret_file"

  if jq -e 'type == "object" and has("AccountTag") and has("TunnelSecret") and has("TunnelID")' "$secret_file" >/dev/null 2>&1; then
    tunnel_id="$(jq -r '.TunnelID' "$secret_file")"
    printf '%s\n' \
      "tunnel: ${tunnel_id}" \
      "credentials-file: /etc/cloudflared/credentials.json" \
      "ingress:" \
      "  - service: http://127.0.0.1:80" \
      >"${cloudflared_dir}/config.yml"
    install -m 0600 "$secret_file" "${cloudflared_dir}/credentials.json"
  else
    printf '%s\n' \
      "ingress:" \
      "  - service: http://127.0.0.1:80" \
      >"${cloudflared_dir}/config.yml"
    install -m 0600 "$secret_file" "${cloudflared_dir}/token"
  fi
  chmod 0600 "${cloudflared_dir}/config.yml"
fi

portainer_password_file="${portainer_dir}/admin_password"
printf '%s\n' "$PORTAINER_ADMIN_PASSWORD" >"$portainer_password_file"
chmod 0600 "$portainer_password_file"

write_dotenv
printf 'Rendered Docker runtime secrets under %s/runtime and %s/.env\n' "$docker_root" "$docker_root"
