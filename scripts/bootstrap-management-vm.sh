#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname "${0}")/lib/common.sh"

MGMT_HOST="${MGMT_HOST:-fs@10.0.40.100}"
SSH_IDENTITY_FILE="${SSH_IDENTITY_FILE:-}"
REPO_URL="${REPO_URL:-https://github.com/fabricesemti80/home-dc-kubernetes.git}"
REPO_DIR="${REPO_DIR:-/home/fs/repos/home-dc-kubernetes}"
DOPPLER_PROJECT="${DOPPLER_PROJECT:-project-homelab}"
DOPPLER_CONFIG="${DOPPLER_CONFIG:-dev_homelab}"
ROOT_DIR="$(cd "$(dirname "${0}")/.." && pwd)"

function ssh_run() {
  if [[ -n ${SSH_IDENTITY_FILE} ]]; then
    ssh -i "${SSH_IDENTITY_FILE}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${MGMT_HOST}" "$@"
  else
    ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${MGMT_HOST}" "$@"
  fi
}

function main() {
  check_cli ssh tar

  log info "Preparing management VM bootstrap" "host=${MGMT_HOST}" "repo_dir=${REPO_DIR}"

  ssh_run "sudo apt-get update && sudo apt-get install -y bash ca-certificates curl git sudo"
  ssh_run "mkdir -p /home/fs/repos"

  ssh_run "if [ ! -d '${REPO_DIR}/.git' ]; then git clone '${REPO_URL}' '${REPO_DIR}'; else git -C '${REPO_DIR}' pull --ff-only; fi"
  COPYFILE_DISABLE=1 tar \
    --exclude .git \
    --exclude .claude/worktrees \
    -C "${ROOT_DIR}" \
    -czf - . |
    ssh_run "mkdir -p '${REPO_DIR}' && tar -xzf - -C '${REPO_DIR}'"
  ssh_run "cd '${REPO_DIR}' && TARGET_USER=fs REPO_DIR='${REPO_DIR}' DOPPLER_PROJECT='${DOPPLER_PROJECT}' DOPPLER_CONFIG='${DOPPLER_CONFIG}' bash scripts/management-init.sh"

  log info "Management VM bootstrap finished" "host=${MGMT_HOST}" "repo_dir=${REPO_DIR}"
}

main "$@"
