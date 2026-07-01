#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname "${0}")/lib/common.sh"

TARGET_USER="${TARGET_USER:-${SUDO_USER:-${USER}}}"
TARGET_HOME="$(eval echo "~${TARGET_USER}")"
REPO_DIR="${REPO_DIR:-${TARGET_HOME}/repos/home-dc-kubernetes}"
DOPPLER_PROJECT="${DOPPLER_PROJECT:-project-homelab}"
DOPPLER_CONFIG="${DOPPLER_CONFIG:-dev_homelab}"

function as_target_user() {
  sudo -u "${TARGET_USER}" env "$@"
}

function apt_install() {
  local packages=("${@}")
  sudo apt-get update
  sudo apt-get install -y "${packages[@]}"
}

function ensure_base_packages() {
  apt_install bash build-essential ca-certificates curl git gpg sudo unzip zsh
}

function ensure_mise() {
  if [[ -x "${TARGET_HOME}/.local/bin/mise" ]]; then
    log info "mise already installed" "path=${TARGET_HOME}/.local/bin/mise"
    return
  fi

  log info "Installing mise" "user=${TARGET_USER}"
  as_target_user HOME="${TARGET_HOME}" sh -lc 'curl https://mise.run | sh'
}

function ensure_starship() {
  if [[ -x "${TARGET_HOME}/.local/bin/starship" ]] || command -v starship &>/dev/null; then
    log info "starship already installed"
    return
  fi

  log info "Installing starship" "user=${TARGET_USER}"
  as_target_user HOME="${TARGET_HOME}" sh -lc "mkdir -p '${TARGET_HOME}/.local/bin' && curl -fsSL https://starship.rs/install.sh | sh -s -- -y -b '${TARGET_HOME}/.local/bin'"
}

function ensure_shell_config() {
  local rc_file="${TARGET_HOME}/.zshrc"

  sudo touch "${rc_file}"
  sudo chown "${TARGET_USER}":"${TARGET_USER}" "${rc_file}"

  if ! sudo grep -Fq 'eval "$('"${TARGET_HOME}"'/.local/bin/mise activate zsh)"' "${rc_file}"; then
    echo "eval \"\$(${TARGET_HOME}/.local/bin/mise activate zsh)\"" | sudo tee -a "${rc_file}" >/dev/null
  fi

  if ! sudo grep -Fq 'eval "$(starship init zsh)"' "${rc_file}"; then
    # shellcheck disable=SC2016
    echo 'eval "$(starship init zsh)"' | sudo tee -a "${rc_file}" >/dev/null
  fi
}

function ensure_repo_parent() {
  sudo mkdir -p "${TARGET_HOME}/repos"
  sudo chown -R "${TARGET_USER}":"${TARGET_USER}" "${TARGET_HOME}/repos"
}

function ensure_repo_tools() {
  if [[ ! -f "${REPO_DIR}/.mise.toml" ]]; then
    log warn "Repo not found or missing .mise.toml" "repo_dir=${REPO_DIR}"
    return
  fi

  log info "Trusting repo config for mise" "repo_dir=${REPO_DIR}"
  as_target_user HOME="${TARGET_HOME}" PATH="${TARGET_HOME}/.local/bin:${PATH}" sh -lc "cd '${REPO_DIR}' && ~/.local/bin/mise trust"

  log info "Installing repo-managed tools with mise" "repo_dir=${REPO_DIR}"
  as_target_user HOME="${TARGET_HOME}" PATH="${TARGET_HOME}/.local/bin:${PATH}" sh -lc "cd '${REPO_DIR}' && ~/.local/bin/mise install"
}

function ensure_docker() {
  if command -v docker &>/dev/null; then
    log info "docker already installed"
  else
    log info "Installing Docker Engine"
    curl -fsSL https://get.docker.com | sh
  fi

  sudo usermod -aG docker "${TARGET_USER}"
  sudo systemctl enable --now docker
}

function ensure_doppler() {
  if command -v doppler &>/dev/null; then
    log info "doppler already installed"
    return
  fi

  log info "Installing Doppler CLI"
  sudo apt-get update
  sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
  curl -sLf --retry 3 --tlsv1.2 --proto "=https" \
    'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' |
    sudo gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" |
    sudo tee /etc/apt/sources.list.d/doppler-cli.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y doppler
}

function report_doppler_state() {
  if [[ -n ${DOPPLER_TOKEN:-} ]]; then
    log info "Doppler token is present in environment" "project=${DOPPLER_PROJECT}" "config=${DOPPLER_CONFIG}"
    return
  fi

  if [[ -f "${TARGET_HOME}/.doppler/.doppler.yaml" ]]; then
    log info "Doppler appears configured for user" "user=${TARGET_USER}"
    return
  fi

  log warn "Doppler is installed but not configured yet" "next=run doppler login or provide DOPPLER_TOKEN"
}

function main() {
  check_cli curl sudo

  ensure_base_packages
  ensure_repo_parent
  ensure_mise
  ensure_starship
  ensure_shell_config
  ensure_docker
  ensure_doppler
  ensure_repo_tools
  report_doppler_state

  log info "Management host bootstrap completed" "repo_dir=${REPO_DIR}" "user=${TARGET_USER}"
  log info "docker group membership is active on next login" "user=${TARGET_USER}"
}

main "$@"
