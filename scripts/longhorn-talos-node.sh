#!/usr/bin/env bash
set -euo pipefail
# Read-only checks for the Longhorn rollout on ONE app-cluster worker (see
# docs/operations/longhorn.md). It never changes a node.
#
#   preflight <ip>      worker, exactly one blank ~500 GB disk attached, schematic status, node Ready
#   needs-upgrade <ip>  exit 0 when the node runs a different schematic than talos/app/talconfig.yaml, 1 when it already matches
#   verify <ip>         extensions, Longhorn and local-path volumes, kubelet and the shared mount
#
# TALOSCONFIG and KUBECONFIG come from the environment (the Taskfile exports both).

mode=${1:?usage: longhorn-talos-node.sh preflight|needs-upgrade|verify <node-ip>}
ip=${2:?usage: longhorn-talos-node.sh preflight|needs-upgrade|verify <node-ip>}
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
talconfig="$root/talos/app/talconfig.yaml"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}
ok() { printf 'ok:   %s\n' "$*"; }
node_field() { yq -r ".nodes[] | select(.ipAddress == \"$ip\") | $1" "$talconfig"; }
configured_schematic() { node_field .talosImageURL | awk -F/ '{print $NF}'; }
running_schematic() { talosctl -n "$ip" get extensions 2>/dev/null | awk '$6 == "schematic" {print $7}'; }
require_worker() {
  local control
  control=$(node_field .controlPlane)
  [[ -n $control ]] || fail "$ip is not a node in talos/app/talconfig.yaml"
  [[ $control == false ]] || fail "$ip is a control-plane node; this rollout is for workers only"
}

preflight() {
  require_worker
  ok "$(node_field .hostname) ($ip) is a worker"

  # One disk of ~400 GB or more: the passthrough SSD (the others are 59 GB and 107 GB).
  local big count
  big=$(talosctl -n "$ip" get disks 2>/dev/null | awk 'NR > 1 && (($7 == "GB" && $6 + 0 >= 400) || $7 == "TB") {print $4}')
  count=$(printf '%s\n' "$big" | grep -c . || true)
  [[ $count -eq 1 ]] || fail "expected exactly one disk >= 400 GB on $ip, found $count; is the SSD attached (task nodes-apply) and visible?"
  ok "SSD present as $big"

  # Blank, or already provisioned by this very rollout. Anything else is unexpected.
  local volumes parts holder
  volumes=$(talosctl -n "$ip" get discoveredvolumes 2>/dev/null)
  parts=$(awk -v d="$big" 'NR > 1 && $4 ~ "^" d "p?[0-9]+$" {print $4}' <<<"$volumes")
  holder=$(awk -v d="$big" 'NR > 1 && $4 == d && NF > 8 {print $9}' <<<"$volumes")
  if [[ -n $parts || -n $holder ]]; then
    if talosctl -n "$ip" get volumestatus u-longhorn >/dev/null 2>&1; then
      ok "$big already holds the Longhorn volume (re-run is fine)"
    else
      fail "$big is not blank (partitions: ${parts:-none}, filesystem: ${holder:-none}); wipe it first (task ssd-passthrough-apply -- -e proxmox_ssd_passthrough_wipe_signatures=true in home-dc-proxmox)"
    fi
  else
    ok "$big is blank"
  fi

  local running configured
  running=$(running_schematic)
  configured=$(configured_schematic)
  if [[ $running == "$configured" ]]; then
    ok "already on the target schematic ${configured:0:12}; the upgrade step will be skipped"
  else
    ok "schematic ${running:0:12} -> ${configured:0:12}; the node will be upgraded (reboot)"
  fi

  local ready
  ready=$(kubectl get nodes -o json | jq -r --arg ip "$ip" '.items[] | select(any(.status.addresses[]; .type == "InternalIP" and .address == $ip)) | .metadata.name + " " + ((.status.conditions[] | select(.type == "Ready")).status)')
  [[ $ready == *" True" ]] || fail "Kubernetes node for $ip is not Ready (${ready:-not found})"
  ok "Kubernetes node ${ready% *} is Ready"
}

verify() {
  require_worker
  local extensions name phase mounts kubelet
  extensions=$(talosctl -n "$ip" get extensions 2>/dev/null)
  for name in iscsi-tools util-linux-tools; do
    awk -v n="$name" '$6 == n {found = 1} END {exit !found}' <<<"$extensions" || fail "extension $name is missing on $ip (upgrade to the new schematic first)"
    ok "extension $name"
  done
  [[ $(running_schematic) == "$(configured_schematic)" ]] || fail "running schematic differs from talos/app/talconfig.yaml"
  ok "schematic matches talos/app/talconfig.yaml"
  # Talos provisions user volumes asynchronously after a config apply; allow up to 2 minutes.
  for name in u-longhorn u-local-path-provisioner; do
    for _ in $(seq 1 24); do
      phase=$(talosctl -n "$ip" get volumestatus "$name" -o yaml 2>/dev/null | yq -r '.spec.phase' || true)
      [[ $phase == ready ]] && break
      sleep 5
    done
    [[ $phase == ready ]] || fail "volume $name is '${phase:-missing}' after 2 minutes, expected 'ready'"
    ok "volume $name ready"
  done
  # Capture first: `talosctl ... | grep -q` under pipefail reports a broken pipe as a failure.
  for _ in $(seq 1 24); do
    mounts=$(talosctl -n "$ip" read /proc/mounts 2>/dev/null || true)
    grep -q ' /var/mnt/longhorn ' <<<"$mounts" && break
    sleep 5
  done
  grep -q ' /var/mnt/longhorn ' <<<"$mounts" || fail "/var/mnt/longhorn is not mounted on $ip"
  ok "/var/mnt/longhorn is mounted"
  # Applying the kubelet extraMounts restarts the kubelet; wait for it (up to 3 minutes).
  for _ in $(seq 1 36); do
    kubelet=$(talosctl -n "$ip" service kubelet 2>/dev/null || true)
    grep -Eq '^STATE +Running' <<<"$kubelet" && grep -Eq '^HEALTH +OK' <<<"$kubelet" && break
    sleep 5
  done
  grep -Eq '^STATE +Running' <<<"$kubelet" || fail "kubelet is not Running on $ip after 3 minutes"
  grep -Eq '^HEALTH +OK' <<<"$kubelet" || fail "kubelet is Running but not healthy on $ip"
  ok "kubelet Running and healthy"
}

case $mode in
preflight) preflight ;;
needs-upgrade) [[ $(running_schematic) != "$(configured_schematic)" ]] ;;
verify) verify ;;
*) fail "unknown mode '$mode' (preflight, needs-upgrade, verify)" ;;
esac
