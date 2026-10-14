#!/usr/bin/env bash
set -euo pipefail

required=(
  "docs/architecture/ARCHITECTURE_PLAN.md"
  "docs/architecture/PHASE_0_1_BLUEPRINT.md"
  "flake.nix"
  "scripts/generate-autokuma-monitors.py"
  ".github/workflows/generate-autokuma-monitors.yaml"
)

for f in "${required[@]}"; do
  [[ -f $f ]] || {
    echo "Missing required file: $f"
    exit 1
  }
done

yq eval '.' "kubernetes/apps/app-cluster/web/homepage/config/settings.yaml" >/dev/null

# Existing PVs require a separate Retain rebind; this gate protects new volumes.
yq eval-all -e 'select(.kind == "StorageClass" and .metadata.name == "cephfs") | (.parameters.mounter == "fuse" and .reclaimPolicy == "Retain")' \
  kubernetes/apps/app-cluster/storage/cephfs-sc.yaml >/dev/null

# csiConfig is published in a ConfigMap; credentials belong in the CSI Secret.
yq eval -e '[.csiConfig[] | (has("adminKey") or has("userKey"))] | any == false' \
  kubernetes/apps/app-cluster/storage/ceph-csi/values.yaml >/dev/null

echo "Validation passed: required files and CephFS safeguards present."
