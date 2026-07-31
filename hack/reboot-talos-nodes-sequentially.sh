#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KUBECONFIG_PATH="${KUBECONFIG:-$ROOT_DIR/kubeconfig}"
TALOSCONFIG_PATH="${TALOSCONFIG:-$ROOT_DIR/talos/app/clusterconfig/talosconfig}"
TALOSCONFIG_FALLBACK_PATH="$ROOT_DIR/talos/clusterconfig/talosconfig"
INTERVAL_SECONDS=30
NOT_READY_TIMEOUT_SECONDS=180
READY_TIMEOUT_SECONDS=900
ASSUME_YES=false

DEFAULT_NODE_NAMES=(k8s-ctrl-03 k8s-ctrl-02 k8s-ctrl-01)
KNOWN_NODE_NAMES=(k8s-ctrl-03 k8s-ctrl-02 k8s-ctrl-01)
KNOWN_NODE_IPS=(10.0.40.92 10.0.40.91 10.0.40.90)
NODE_NAMES=("${DEFAULT_NODE_NAMES[@]}")
NODE_IPS=(10.0.40.92 10.0.40.91 10.0.40.90)

usage() {
  cat <<EOF
Usage: $0 [options] [node-name ...]

Sequentially reboot Talos nodes and wait for each Kubernetes node to become Ready.

Options:
  --yes                 Do not prompt before starting.
  --interval SECONDS    Poll interval. Default: ${INTERVAL_SECONDS}.
  --timeout SECONDS     Ready timeout per node. Default: ${READY_TIMEOUT_SECONDS}.
  --kubeconfig PATH     Kubernetes kubeconfig. Default: \$KUBECONFIG or $ROOT_DIR/kubeconfig.
  --talosconfig PATH    Talos config. Default: \$TALOSCONFIG or $ROOT_DIR/talos/app/clusterconfig/talosconfig.
  -h, --help            Show this help.

Default node order:
  ${DEFAULT_NODE_NAMES[*]}
EOF
}

node_ip() {
  local name="$1"

  for i in "${!KNOWN_NODE_NAMES[@]}"; do
    if [[ ${KNOWN_NODE_NAMES[$i]} == "$name" ]]; then
      printf '%s\n' "${KNOWN_NODE_IPS[$i]}"
      return 0
    fi
  done

  return 1
}

node_ready() {
  local name="$1"
  local status

  status="$(
    kubectl --kubeconfig "$KUBECONFIG_PATH" get node "$name" \
      -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true
  )"

  [[ $status == "True" ]]
}

wait_for_node_ready() {
  local name="$1"
  local start now elapsed

  start="$(date +%s)"

  while true; do
    if node_ready "$name"; then
      printf 'node %s is Ready\n' "$name"
      return 0
    fi

    now="$(date +%s)"
    elapsed=$((now - start))
    if ((elapsed >= READY_TIMEOUT_SECONDS)); then
      printf 'timed out waiting for %s to become Ready after %ss\n' "$name" "$READY_TIMEOUT_SECONDS" >&2
      return 1
    fi

    printf '[%s] waiting for %s to become Ready (%ss elapsed)\n' "$(date -Is)" "$name" "$elapsed"
    sleep "$INTERVAL_SECONDS"
  done
}

wait_for_node_not_ready() {
  local name="$1"
  local start now elapsed

  start="$(date +%s)"

  while node_ready "$name"; do
    now="$(date +%s)"
    elapsed=$((now - start))
    if ((elapsed >= NOT_READY_TIMEOUT_SECONDS)); then
      printf 'timed out waiting for %s to leave Ready after reboot request\n' "$name" >&2
      return 1
    fi

    printf '[%s] waiting for %s to leave Ready (%ss elapsed)\n' "$(date -Is)" "$name" "$elapsed"
    sleep "$INTERVAL_SECONDS"
  done

  printf 'node %s left Ready\n' "$name"
}

print_var_mount() {
  local ip="$1"

  talosctl --talosconfig "$TALOSCONFIG_PATH" -e "$ip" -n "$ip" mounts |
    awk '$NF == "/var" {print}'
}

require_tools() {
  command -v kubectl >/dev/null
  command -v talosctl >/dev/null

  if [[ ! -s $TALOSCONFIG_PATH && -s $TALOSCONFIG_FALLBACK_PATH ]]; then
    TALOSCONFIG_PATH="$TALOSCONFIG_FALLBACK_PATH"
  fi

  if [[ ! -s $KUBECONFIG_PATH ]]; then
    printf 'kubeconfig not found or empty: %s\n' "$KUBECONFIG_PATH" >&2
    exit 1
  fi

  if [[ ! -s $TALOSCONFIG_PATH ]]; then
    printf 'talosconfig not found or empty: %s\n' "$TALOSCONFIG_PATH" >&2
    exit 1
  fi
}

confirm() {
  local answer

  if [[ $ASSUME_YES == true ]]; then
    return 0
  fi

  printf 'This will reboot these nodes sequentially: %s\n' "${NODE_NAMES[*]}"
  printf 'Continue? [y/N] '
  read -r answer
  [[ $answer == "y" || $answer == "Y" ]]
}

while (($# > 0)); do
  case "$1" in
  --yes)
    ASSUME_YES=true
    shift
    ;;
  --interval)
    INTERVAL_SECONDS="$2"
    shift 2
    ;;
  --timeout)
    READY_TIMEOUT_SECONDS="$2"
    shift 2
    ;;
  --kubeconfig)
    KUBECONFIG_PATH="$2"
    shift 2
    ;;
  --talosconfig)
    TALOSCONFIG_PATH="$2"
    shift 2
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  -*)
    printf 'unknown option: %s\n' "$1" >&2
    usage >&2
    exit 1
    ;;
  *)
    NODE_NAMES=("$@")
    NODE_IPS=()
    for name in "${NODE_NAMES[@]}"; do
      if ! ip="$(node_ip "$name")"; then
        printf 'unknown node: %s\n' "$name" >&2
        exit 1
      fi
      NODE_IPS+=("$ip")
    done
    break
    ;;
  esac
done

require_tools

if ! confirm; then
  printf 'aborted\n'
  exit 1
fi

for i in "${!NODE_NAMES[@]}"; do
  name="${NODE_NAMES[$i]}"
  ip="${NODE_IPS[$i]}"

  printf '\n==> %s (%s)\n' "$name" "$ip"
  kubectl --kubeconfig "$KUBECONFIG_PATH" cordon "$name"

  printf 'rebooting %s via Talos\n' "$name"
  talosctl --talosconfig "$TALOSCONFIG_PATH" -e "$ip" -n "$ip" reboot --wait=false

  wait_for_node_not_ready "$name"
  wait_for_node_ready "$name"

  printf 'current /var mount for %s:\n' "$name"
  print_var_mount "$ip" || true

  kubectl --kubeconfig "$KUBECONFIG_PATH" uncordon "$name"
done

printf '\nall requested nodes rebooted and Ready\n'
