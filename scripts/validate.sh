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

echo "Validation passed: required files present."
