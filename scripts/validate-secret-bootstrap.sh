#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

failures=0

function info() {
  printf 'info: %s\n' "$*"
}

function ok() {
  printf 'ok: %s\n' "$*"
}

function fail() {
  printf 'error: %s\n' "$*" >&2
  failures=$((failures + 1))
}

function require_file() {
  local file="$1"
  if [[ -f ${file} ]]; then
    ok "found ${file}"
  else
    fail "missing ${file}"
  fi
}

required_files=(
  ".sops.yaml"
  "age.key"
  "talos/app/talsecret.sops.yaml"
  "talos/app/patches/global/machine-registries.sops.yaml"
  "kubernetes/components/common/helm-secrets-private-keys.sops.yaml"
  "kubernetes/argo/repositories/github.sops.yaml"
  "kubernetes/apps/app-cluster/argo-system/argo-cd/values.sops.yaml"
  "kubernetes/apps/app-cluster/doppler-operator-system/doppler-operator/config/secret.sops.yaml"
  "kubernetes/apps/infra-cluster/doppler-operator-system/doppler-operator-infra/config/secret.sops.yaml"
)

for file in "${required_files[@]}"; do
  require_file "${file}"
done

if [[ -f age.key && -f .sops.yaml ]]; then
  public_key="$(age-keygen -y age.key 2>/dev/null || true)"
  if [[ -n ${public_key} ]] && grep -q "${public_key}" .sops.yaml; then
    ok "age.key public recipient is present in .sops.yaml"
  else
    fail "age.key public recipient is not present in .sops.yaml"
  fi
fi

if command -v jq >/dev/null 2>&1; then
  while IFS= read -r file; do
    if [[ -z ${file} ]]; then
      continue
    fi
    if ! sops filestatus "${file}" 2>/dev/null | jq -e '.encrypted == true' >/dev/null; then
      fail "${file} is not encrypted according to sops filestatus"
      continue
    fi
    if sops -d "${file}" >/dev/null 2>&1; then
      ok "decryptable ${file}"
    else
      fail "cannot decrypt ${file}"
    fi
  done < <(find kubernetes talos -type f -name '*.sops.yaml' -print | sort)
else
  info "jq is unavailable; skipping sops filestatus encryption checks"
fi

doppler_refs="$(grep -RhoE 'project: [^[:space:]]+|config: [^[:space:]]+' kubernetes/apps/*-cluster 2>/dev/null | sort | uniq -c || true)"
if [[ -n ${doppler_refs} ]]; then
  info "Doppler manifest references:"
  printf '%s\n' "${doppler_refs}"
else
  info "no Doppler project/config references found"
fi

if [[ ${failures} -gt 0 ]]; then
  printf 'error: secret bootstrap validation failed with %d problem(s)\n' "${failures}" >&2
  exit 1
fi

ok "secret bootstrap validation passed"
