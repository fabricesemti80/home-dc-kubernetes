#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

env_remote_host="${HOMELAB_DOCKER_HOST:-}"
env_remote_dir="${HOMELAB_DOCKER_REMOTE_DIR:-}"
env_remote_compose="${HOMELAB_DOCKER_REMOTE_COMPOSE:-}"

docker_root="${repo_root}/infra/docker"
remote_host="${env_remote_host:-fs@10.0.40.19}"
remote_dir="${env_remote_dir:-/opt/project-homelab/infra/docker}"
remote_compose="${env_remote_compose:-sudo docker compose}"

export HOMELAB_DOCKER_ROOT="$remote_dir"

"${docker_root}/scripts/render-secrets.sh"

remote_parent="$(dirname "$remote_dir")"

# shellcheck disable=SC2029
ssh "$remote_host" "mkdir -p '$remote_dir' 2>/dev/null || { sudo mkdir -p '$remote_dir' && sudo chown -R \"\$(id -u):\$(id -g)\" '$remote_parent'; }"

rsync -avz --exclude '.DS_Store' --exclude '._*' --exclude 'runtime' --exclude 'secrets' \
  "$docker_root/" "$remote_host:$remote_dir/"

rsync -avz --delete --exclude '.DS_Store' --exclude '._*' \
  "$docker_root/runtime/" "$remote_host:$remote_dir/runtime/"

# shellcheck disable=SC2029
ssh "$remote_host" "cd '$remote_dir' && $remote_compose -f docker-compose.yml up -d --remove-orphans"
