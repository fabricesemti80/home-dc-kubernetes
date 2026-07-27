#!/usr/bin/env bash
set -euo pipefail

required=(
  "docs/architecture/ARCHITECTURE_PLAN.md"
  "docs/architecture/PHASE_0_1_BLUEPRINT.md"
  "flake.nix"
)

for f in "${required[@]}"; do
  [[ -f $f ]] || {
    echo "Missing required file: $f"
    exit 1
  }
done

python3 scripts/generate-autokuma-monitors.py --check

echo "Validation passed: required files and generated outputs are current."
