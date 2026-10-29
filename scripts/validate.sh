#!/usr/bin/env bash
set -euo pipefail

required=(
  "docs/architecture/ARCHITECTURE_PLAN.md"
  "docs/plan/app-cluster-standalone-refactor.md"
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

# CI and the dev shell both use mikefarah/yq to emit JSON for jq checks.
yaml_json() {
  yq -o=json '.' "$1"
}

yaml_json kubernetes/apps/app-cluster/web/homepage/config/settings.yaml | jq -e '. != null' >/dev/null

# Fresh workers have dedicated local volumes; never schedule on the controller.
yaml_json kubernetes/apps/app-cluster/storage/local-path/values.yaml | jq -e '
  .nodePathMap[0].node == "DEFAULT_PATH_FOR_NON_LISTED_NODES"
  and .nodePathMap[0].paths == []
  and ([.nodePathMap[1:][] | select(.paths == ["/var/mnt/local-path-provisioner"]) | .node] | sort)
    == ["k8s-wrkr-01-gpu", "k8s-wrkr-02", "k8s-wrkr-03"]
  and .storageClass.reclaimPolicy == "Retain"
  and .storageClass.volumeBindingMode == "WaitForFirstConsumer"
' >/dev/null

yaml_json kubernetes/apps/app-cluster/media/jellyfin/config/media-library-pv.yaml |
  jq -e '.kind == "PersistentVolume" and .metadata.name == "media-library-pv" and .spec.persistentVolumeReclaimPolicy == "Retain" and .spec.nfs.server == "10.0.40.2" and .spec.nfs.path == "/media" and .spec.claimRef.name == "media-library-pvc"' >/dev/null
yaml_json kubernetes/apps/app-cluster/media/jellyfin/config/media-library-pvc.yaml |
  jq -e '.kind == "PersistentVolumeClaim" and .metadata.name == "media-library-pvc" and .spec.volumeName == "media-library-pv"' >/dev/null

# Public DNS already targets the tunnel. Keep the webhook bypass first, block
# unclaimed setup pages, and route other hosts through TLS-verified Envoy.
yaml_json kubernetes/apps/app-cluster/network/cloudflare-tunnel/config/config.yaml |
  jq -r '.data["config.yaml"]' | yaml_json - | jq -e '
    .ingress as $rules
    | ($rules | length) == 6
      and $rules[0] == {"hostname": "argo.krapulax.dev", "path": "^/api/webhook$", "service": "http://argocd-server.argo-system.svc.cluster.local:80"}
      and $rules[1] == {"hostname": "krapulax.dev", "service": "https://envoy-external.network.svc.cluster.local", "originRequest": {"originServerName": "external.krapulax.dev"}}
      and $rules[2] == {"hostname": "photos.krapulax.dev", "service": "http_status:404"}
      and $rules[3] == {"hostname": "requests.krapulax.dev", "service": "http_status:404"}
      and $rules[4] == {"hostname": "*.krapulax.dev", "service": "https://envoy-external.network.svc.cluster.local", "originRequest": {"originServerName": "external.krapulax.dev"}}
      and $rules[5] == {"service": "http_status:404"}
  ' >/dev/null
yaml_json kubernetes/argo/apps/app-cluster/network/cloudflare-dns.yaml |
  jq -e '.kind == "Application" and (.spec.syncPolicy | has("automated") | not)' >/dev/null

echo "Validation passed: required files, tunnel ingress, manual DNS, local-path and NFS safeguards present."
