#!/usr/bin/env bash
set -euo pipefail

infra_kubeconfig="${INFRA_KUBECONFIG:-.private/infra-cluster/kubeconfig}"
namespace=network
kubectl_cmd=(kubectl --kubeconfig "$infra_kubeconfig" -n "$namespace")

for command in curl jq kubectl base64; do
    command -v "$command" >/dev/null
done

password="$("${kubectl_cmd[@]}" get secret technitium-secrets -o jsonpath='{.data.TECHNITIUM_ADMIN_PASSWORD}' | base64 -d)"
peer_0_ip="$("${kubectl_cmd[@]}" get service technitium-peer-0 -o jsonpath='{.spec.clusterIP}')"
peer_1_ip="$("${kubectl_cmd[@]}" get service technitium-peer-1 -o jsonpath='{.spec.clusterIP}')"

"${kubectl_cmd[@]}" port-forward pod/technitium-0 15380:5380 >/dev/null 2>&1 &
port_forward_0=$!
"${kubectl_cmd[@]}" port-forward pod/technitium-1 15381:5380 >/dev/null 2>&1 &
port_forward_1=$!
trap 'kill "$port_forward_0" "$port_forward_1" 2>/dev/null || true' EXIT

for port in 15380 15381; do
    until curl -ks --max-time 1 "http://127.0.0.1:${port}/" >/dev/null; do sleep 1; done
done

login() {
    curl -ksG --data-urlencode user=admin --data-urlencode "pass=$password" "http://127.0.0.1:$1/api/user/login" |
        jq -er '.token // .response.token'
}

token_0="$(login 15380)"
token_1="$(login 15381)"

curl -ks -X POST -H "Authorization: Bearer $token_0" \
    --data-urlencode 'zone=krapulax.home' \
    --data-urlencode 'zoneTransferTsigKeyNames=cluster-catalog.krapulax.home' \
    http://127.0.0.1:15380/api/zones/options/set >/dev/null
curl -ks -X POST -H "Authorization: Bearer $token_1" \
    --data-urlencode 'zone=krapulax.home' \
    --data-urlencode 'primaryZoneTransferTsigKeyName=cluster-catalog.krapulax.home' \
    http://127.0.0.1:15381/api/zones/options/set >/dev/null
curl -ks -X POST -H "Authorization: Bearer $token_0" --data-urlencode "ipAddresses=$peer_0_ip" \
    http://127.0.0.1:15380/api/admin/cluster/updateIpAddress >/dev/null
curl -ks -X POST -H "Authorization: Bearer $token_1" \
    --data-urlencode 'primaryNodeUrl=https://technitium-0.krapulax.home:53443/' \
    --data-urlencode "primaryNodeIpAddresses=$peer_0_ip" \
    http://127.0.0.1:15381/api/admin/cluster/secondary/updatePrimary >/dev/null
curl -ks -X POST -H "Authorization: Bearer $token_1" --data-urlencode "ipAddresses=$peer_1_ip" \
    http://127.0.0.1:15381/api/admin/cluster/updateIpAddress >/dev/null
curl -ks -X POST -H "Authorization: Bearer $token_1" \
    http://127.0.0.1:15381/api/admin/cluster/secondary/resync >/dev/null
curl -ks -X POST -H "Authorization: Bearer $token_1" --data-urlencode 'zone=krapulax.home' \
    http://127.0.0.1:15381/api/zones/resync >/dev/null

sleep 3
for port in 15380 15381; do
    token="$(login "$port")"
    curl -ks -H "Authorization: Bearer $token" "http://127.0.0.1:${port}/api/admin/cluster/state" |
        jq -e '.response.clusterNodes[] | select(.type == "Primary") | select(.state == "Connected" or .state == "Self")' >/dev/null
done

"${kubectl_cmd[@]}" exec technitium-0 -- dig +short minecraft.krapulax.home @127.0.0.1
"${kubectl_cmd[@]}" exec technitium-1 -- dig +short minecraft.krapulax.home @127.0.0.1
