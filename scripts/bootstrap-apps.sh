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

  local -r argo_apps_dir="${ROOT_DIR}/kubernetes/argo/apps/app-cluster"

  if [[ ! -d ${argo_apps_dir} ]]; then
    log fatal "Directory does not exist" "directory=${argo_apps_dir}"
  fi

  while IFS= read -r namespace; do
    [[ ${namespace} =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || continue

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
    for app in "${argo_apps_dir}"/*/; do
      [[ -d ${app} ]] || continue
      for manifest in "${app}"/*.yaml; do
        [[ -f ${manifest} ]] || continue
        printf '%s\n' "$(basename "${app}")"
        break
      done
    done
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

  if ! all_resources=$(helmfile --file "${helmfile_file}" template --include-crds --quiet); then
    log fatal "Failed to render resources from Helmfile" "file" "${helmfile_file}"
  fi

  if ! crds=$(printf '%s\n' "${all_resources}" | yq eval-all 'select(.kind == "CustomResourceDefinition")' - 2>/dev/null) || [[ -z ${crds} ]]; then
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

# Sync Helm releases
function sync_helm_releases() {
  log debug "Syncing Helm releases"

  local -r helmfile_file="${ROOT_DIR}/bootstrap/helmfile.d/01-apps.yaml"

  if [[ ! -f ${helmfile_file} ]]; then
    log error "File does not exist" "file=${helmfile_file}"
  fi

  # Argo updates its own Secret; Helm 4 server-side apply conflicts on the next sync.
  if ! helmfile --file "${helmfile_file}" sync --hide-notes --args '--server-side=false'; then
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
  local stage="${1:-all}"
  if [[ ${stage} != network && ${stage} != platform && ${stage} != all ]]; then
    log fatal "Unknown bootstrap stage" "stage=${stage}"
  fi

  check_env KUBECONFIG TALOSCONFIG
  check_cli helmfile kubectl kustomize sops talhelper yq

  if [[ ${stage} == network ]]; then
    apply_crds
    helmfile --file "${ROOT_DIR}/bootstrap/helmfile.d/01-apps.yaml" --selector name=cilium sync --args '--server-side=false'
    return
  fi

  # Apply resources and Helm releases
  wait_for_nodes
  apply_namespaces
  apply_sops_secrets
  apply_crds
  sync_helm_releases
  if [[ ${stage} == all ]]; then
    sync_argo_apps
    log info "Argo is syncing the Git repository"
  else
    log info "Platform installed; restore data before syncing Argo Applications"
  fi
}

main "$@"
