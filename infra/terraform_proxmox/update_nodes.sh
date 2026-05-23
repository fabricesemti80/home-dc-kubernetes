#!/bin/bash
set -e

# Default to ../nodes.yaml relative to the script execution (terraform dir)
NODES_YAML="${NODES_YAML:-../nodes.yaml}"

if [ ! -f "$NODES_YAML" ]; then
  echo "nodes.yaml not found at $NODES_YAML"
  exit 0
fi

if [ -z "$NODES_JSON" ]; then
  echo "NODES_JSON environment variable is empty"
  exit 1
fi

# Create a temp file for the loop input
TMP_INPUT=$(mktemp)
echo "$NODES_JSON" | jq -r 'to_entries[] | "\(.key) \(.value.mac_address) \(.value.ip)"' >"$TMP_INPUT"

echo "Updating nodes.yaml with IPs and MACs from Terraform..."

while read -r name mac ip; do
  if [ -n "$mac" ] && [ "$mac" != "null" ]; then
    # Lowercase MAC for consistency
    mac=$(echo "$mac" | tr '[:upper:]' '[:lower:]')

    # Check if node exists in yaml
    if yq ".nodes[] | select(.name == \"$name\")" "$NODES_YAML" >/dev/null 2>&1; then
      # Update MAC
      yq -i "(.nodes[] | select(.name == \"$name\")).mac_addr = \"$mac\"" "$NODES_YAML"
      # Update IP
      yq -i "(.nodes[] | select(.name == \"$name\")).address = \"$ip\"" "$NODES_YAML"
      echo "Updated $name: IP=$ip, MAC=$mac"
    else
      echo "Node $name not found in nodes.yaml, skipping update."
    fi
  fi
done <"$TMP_INPUT"

rm "$TMP_INPUT"
echo "nodes.yaml update complete."
