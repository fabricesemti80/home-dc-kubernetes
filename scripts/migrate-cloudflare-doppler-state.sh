#!/usr/bin/env bash
set -euo pipefail

[[ ${CONFIRM_STATE_MIGRATION:-} == 1 ]] || {
  echo "Set CONFIRM_STATE_MIGRATION=1 to migrate the six Doppler state entries."
  exit 1
}

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
state_dir=$(cd -- "$script_dir/../infra/terraform_cloudflare" && pwd)
state_file="$state_dir/terraform.tfstate"

addresses=(
  'doppler_secret.kubernetes_tunnel_credentials[0]'
  'doppler_secret.kubernetes_tunnel_id[0]'
  'doppler_secret.kubernetes_tunnel_token[0]'
  'doppler_secret.kubernetes_infra_tunnel_credentials[0]'
  'doppler_secret.kubernetes_infra_tunnel_id[0]'
  'doppler_secret.kubernetes_infra_tunnel_token[0]'
)
ids=(
  'home-dc-kubernetes.apps.TUNNEL_CREDENTIALS_APPS'
  'home-dc-kubernetes.apps.TUNNEL_ID_APPS'
  'home-dc-kubernetes.apps.TUNNEL_TOKEN_APPS'
  'home-dc-kubernetes.infra.TUNNEL_CREDENTIALS_INFRA'
  'home-dc-kubernetes.infra.TUNNEL_ID_INFRA'
  'home-dc-kubernetes.infra.TUNNEL_TOKEN_INFRA'
)
import_indexes=(2 5)

[[ -f $state_file ]] || {
  echo "State file not found: $state_file"
  exit 1
}

state_json=$(tofu -chdir="$state_dir" state pull)
for address in "${addresses[@]}"; do
  id=$(jq -r --arg address "$address" '
    .resources[] | select((.type + "." + .name) == ($address | split("[")[0])) |
    .instances[] | select(.index_key == 0) | .attributes.id
  ' <<<"$state_json")
  [[ $id == project-homelab.dev_homelab.* ]] || {
    echo "Refusing migration: $address is not bound to project-homelab/dev_homelab."
    exit 1
  }
done

for target in 'apps:TUNNEL_TOKEN_APPS' 'infra:TUNNEL_TOKEN_INFRA'; do
  config=${target%%:*}
  secret=${target#*:}
  doppler secrets get "$secret" --project home-dc-kubernetes --config "$config" --plain --silent >/dev/null
done

backup="$state_file.pre-doppler-migration-$(date +%Y%m%d%H%M%S).backup"
cp "$state_file" "$backup"
rollback() {
  cp "$backup" "$state_file"
  echo "Migration failed; restored $state_file from $backup."
}
trap rollback ERR

for address in "${addresses[@]}"; do
  tofu -chdir="$state_dir" state rm "$address" >/dev/null
done

for i in "${import_indexes[@]}"; do
  tofu -chdir="$state_dir" import "${addresses[$i]}" "${ids[$i]}" >/dev/null
done

trap - ERR
echo "Migrated Doppler tunnel-secret state. The next plan will create the four missing credential and ID secrets."
