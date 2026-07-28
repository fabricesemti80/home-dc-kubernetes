#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname "${0}")/lib/common.sh"

export LOG_LEVEL="debug"
export ROOT_DIR="$(git rev-parse --show-toplevel)"

# Talos requires the nodes to be 'Ready=False' before applying resources
function wait_for_nodes() {
  log debug "Waiting for nodes to be available"

  # Skip waiting if all nodes are 'Ready=True'
  if kubectl wait nodes --for=condition=Ready=True --all --timeout=10s &>/dev/null; then
    log info "Nodes are available and ready, skipping wait for nodes"
    return
  fi

  # Wait for all nodes to be 'Ready=False'
  until kubectl wait nodes --for=condition=Ready=False --all --timeout=10s &>/dev/null; do
    log info "Nodes are not available, waiting for nodes to be available. Retrying in 10 seconds..."
    sleep 10
  done
}

# Namespaces to be applied before the SOPS secrets are installed
function apply_namespaces() {
  log debug "Applying namespaces"

  local -r apps_dir="${ROOT_DIR}/kubernetes/apps"

  if [[ ! -d ${apps_dir} ]]; then
    log error "Directory does not exist" "directory=${apps_dir}"
  fi

  while IFS= read -r namespace; do
    [[ -n ${namespace} ]] || continue

    # Check if the namespace resources are up-to-date
    if kubectl get namespace "${namespace}" &>/dev/null; then
      log info "Namespace resource is up-to-date" "resource=${namespace}"
      continue
    fi

    # Apply the namespace resources
    if kubectl create namespace "${namespace}" --dry-run=client --output=yaml |
      kubectl apply --server-side --filename - &>/dev/null; then
      log info "Namespace resource applied" "resource=${namespace}"
    else
      log error "Failed to apply namespace resource" "resource=${namespace}"
    fi
  done < <(
    {
      for app in "${apps_dir}"/*/; do
        namespace=$(basename "${app}")
        [[ ${namespace} == "app-cluster" || ${namespace} == "infra-cluster" ]] && continue
        printf '%s\n' "${namespace}"
      done

      for app in "${apps_dir}/app-cluster"/*/; do
        [[ -d ${app} ]] || continue
        printf '%s\n' "$(basename "${app}")"
      done
    } | sort -u
  )
}

# SOPS secrets to be applied before the helmfile charts are installed
function apply_sops_secrets() {
  log debug "Applying secrets"

  local -r secrets=(
    "${ROOT_DIR}/kubernetes/components/common/helm-secrets-private-keys.sops.yaml"
  )

  for secret in "${secrets[@]}"; do
    if [ ! -f "${secret}" ]; then
      log warn "File does not exist" "file=${secret}"
      continue
    fi

    # Check if the secret resources are up-to-date
    if sops exec-file "${secret}" "kubectl --namespace argo-system diff --filename {}" &>/dev/null; then
      log info "Secret resource is up-to-date" "resource=$(basename "${secret}" ".sops.yaml")"
      continue
    fi

    # Apply secret resources
    if sops exec-file "${secret}" "kubectl --namespace argo-system apply --server-side --filename {}" &>/dev/null; then
      log info "Secret resource applied successfully" "resource=$(basename "${secret}" ".sops.yaml")"
    else
      log error "Failed to apply secret resource" "resource=$(basename "${secret}" ".sops.yaml")"
    fi
  done
}

# CRDs to be applied before the helmfile charts are installed
function apply_crds() {
  log debug "Applying CRDs"

  local -r helmfile_file="${ROOT_DIR}/bootstrap/helmfile.d/00-crds.yaml"

  if [[ ! -f ${helmfile_file} ]]; then
    log fatal "File does not exist" "file" "${helmfile_file}"
  fi

  if ! all_resources=$(helmfile --file "${helmfile_file}" template --quiet); then
    log fatal "Failed to render resources from Helmfile" "file" "${helmfile_file}"
  fi

  if ! crds=$(echo "${all_resources}" | yq eval-all 'select(.kind == "CustomResourceDefinition")' - 2>/dev/null) || [[ -z ${crds} ]]; then
    log warn "No CRDs found in the rendered templates" "file" "${helmfile_file}"
    return

  fi

  if echo "${crds}" | kubectl diff --filename - &>/dev/null; then
    log info "CRDs are up-to-date"
    return
  fi

  if ! echo "${crds}" | kubectl apply --server-side --filename - &>/dev/null; then
    log fatal "Failed to apply crds from Helmfile" "file" "${helmfile_file}"
  fi

  log info "CRDs applied successfully"
}

# Clean up stuck helm releases
function cleanup_stuck_releases() {
  log debug "Cleaning up stuck helm releases"

  local stuck_releases
  stuck_releases=$(helm ls -A --pending 2>/dev/null | tail -n +1 || true)

  if [[ -z ${stuck_releases} ]]; then
    log info "No stuck helm releases found"
    return
  fi

  log warn "Found stuck helm releases, cleaning up..."

  while IFS= read -r line; do
    if [[ -z ${line} ]] || [[ ${line} == "NAME" ]]; then
      continue
    fi
    release=$(echo "${line}" | awk '{print $1}')
    namespace=$(echo "${line}" | awk '{print $2}')
    log info "Removing stuck release" "release=${release}" "namespace=${namespace}"
    helm uninstall "${release}" -n "${namespace}" &>/dev/null || true
  done <<<"${stuck_releases}"

  log info "Stuck helm releases cleaned up"
}

# Sync Helm releases
function sync_helm_releases() {
  log debug "Syncing Helm releases"

  local -r helmfile_file="${ROOT_DIR}/bootstrap/helmfile.d/01-apps.yaml"

  if [[ ! -f ${helmfile_file} ]]; then
    log error "File does not exist" "file=${helmfile_file}"
  fi

  if ! helmfile --file "${helmfile_file}" sync --hide-notes; then
    log error "Failed to sync Helm releases"
  fi

  log info "Helm releases synced successfully"
}

# Sync Argo Applications
function sync_argo_apps() {
  log debug "Sync Argo Applications"

  local -r bootstrappingmaps=(
    "${ROOT_DIR}/kubernetes/components/common/apps.yaml"
    "${ROOT_DIR}/kubernetes/components/common/repositories.yaml"
    "${ROOT_DIR}/kubernetes/components/common/settings.yaml"
  )

  for bootstrappingmap in "${bootstrappingmaps[@]}"; do
    if [ ! -f "${bootstrappingmap}" ]; then
      log warn "File does not exist" file "${bootstrappingmap}"
      continue
    fi

    # Check if the bootstrappingmap resources are up-to-date
    if kubectl --namespace argo-system diff --filename "${bootstrappingmap}" &>/dev/null; then
      log info "bootstrappingmap resource is up-to-date" "resource=$(basename "${bootstrappingmap}" ".yaml")"
      continue
    fi

    # Apply bootstrappingmap resources
    if kubectl --namespace argo-system apply --server-side --filename "${bootstrappingmap}" &>/dev/null; then
      log info "bootstrappingmap resource applied successfully" "resource=$(basename "${bootstrappingmap}" ".yaml")"
    else
      log error "Failed to apply bootstrappingmap resource" "resource=$(basename "${bootstrappingmap}" ".yaml")"
    fi
  done
}

function main() {
  check_env KUBECONFIG TALOSCONFIG
  check_cli helmfile kubectl kustomize sops talhelper yq

  # Apply resources and Helm releases
  wait_for_nodes
  apply_namespaces
  apply_sops_secrets
  apply_crds
  cleanup_stuck_releases
  sync_helm_releases
  sync_argo_apps

  log info "Congrats! The cluster is bootstrapped and Argo is syncing the Git repository"
}

main "$@"
