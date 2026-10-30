#!/usr/bin/env bash

set -euo pipefail

KUBERNETES_DIR=$1

[[ -z ${KUBERNETES_DIR} ]] && echo "Kubernetes location not specified" && exit 1

kustomize_args=(
  "--load-restrictor=LoadRestrictionsNone"
  "--enable-helm"
  "--enable-alpha-plugins"
  "--enable-exec"
)
kustomize_config="kustomization.yaml"
# Derive K8up schemas from the exact immutable CRDs deployed by GitOps.
# The moving public catalog predates fields such as backup.labelSelectors.
schema_dir=$(mktemp -d)
trap 'rm -rf "$schema_dir"' EXIT
kustomize build "${KUBERNETES_DIR}/components/k8up-crds" |
  yq -o=json -I=0 '.' >"${schema_dir}/crds.jsonl"
while IFS= read -r crd; do
  group=$(jq -r '.spec.group' <<<"${crd}")
  kind=$(jq -r '.spec.names.kind | ascii_downcase' <<<"${crd}")
  mkdir -p "${schema_dir}/${group}"
  while IFS= read -r version; do
    jq --arg version "${version}" '
      .spec.versions[] | select(.name == $version) | .schema.openAPIV3Schema
      | walk(
          if type == "object" and has("properties")
             and (has("additionalProperties") | not)
             and .["x-kubernetes-preserve-unknown-fields"] != true
          then .additionalProperties = false
          else .
          end
        )
    ' <<<"${crd}" >"${schema_dir}/${group}/${kind}_${version}.json"
  done < <(jq -r '.spec.versions[] | select(.served) | .name' <<<"${crd}")
done <"${schema_dir}/crds.jsonl"

kubeconform_args=(
  "-strict"
  "-ignore-missing-schemas"
  "-skip"
  "Gateway,HTTPRoute,Secret"
  "-schema-location"
  "${schema_dir}/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
  "-schema-location"
  "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
  "-schema-location"
  "default"
  "-schema-location"
  "https://kubernetes-schemas.pages.dev/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
  "-verbose"
)

has_ksops_generator() {
  local dir=$1
  grep -RqsE '^[[:space:]]*kind:[[:space:]]+ksops[[:space:]]*$' "${dir}"
}

echo "=== Validating standalone manifests in ${KUBERNETES_DIR}/argo ==="
find "${KUBERNETES_DIR}/argo" -maxdepth 1 -type f -name '*.yaml' -print0 | while IFS= read -r -d $'\0' file; do
  kubeconform "${kubeconform_args[@]}" "${file}"
  if [[ ${PIPESTATUS[0]} != 0 ]]; then
    exit 1
  fi
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/argo ==="
find "${KUBERNETES_DIR}/argo" -type f -name $kustomize_config -print0 | while IFS= read -r -d $'\0' file; do
  echo "=== Validating kustomizations in ${file/%$kustomize_config/} ==="
  if has_ksops_generator "${file/%$kustomize_config/}"; then
    echo "=== Skipping SOPS-backed kustomization without an age key ==="
    continue
  fi
  kustomize build "${file/%$kustomize_config/}" "${kustomize_args[@]}" | kubeconform "${kubeconform_args[@]}"
  if [[ ${PIPESTATUS[0]} != 0 ]]; then
    exit 1
  fi
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/apps ==="
find "${KUBERNETES_DIR}/apps" -type f -name $kustomize_config -print0 | while IFS= read -r -d $'\0' file; do
  echo "=== Validating kustomizations in ${file/%$kustomize_config/} ==="
  if has_ksops_generator "${file/%$kustomize_config/}"; then
    echo "=== Skipping SOPS-backed kustomization without an age key ==="
    continue
  fi
  kustomize build "${file/%$kustomize_config/}" "${kustomize_args[@]}" | kubeconform "${kubeconform_args[@]}"
  if [[ ${PIPESTATUS[0]} != 0 ]]; then
    exit 1
  fi
done
