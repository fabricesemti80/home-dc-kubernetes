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

# Longhorn is the only default StorageClass; local-path must stay explicitly non-default.
yaml_json kubernetes/apps/app-cluster/storage/local-path/values.yaml | jq -e '.storageClass.defaultClass == false' >/dev/null || {
  echo "local-path must stay a non-default StorageClass (Longhorn is the default)." >&2
  exit 1
}
yaml_json kubernetes/apps/app-cluster/storage/longhorn/values.yaml | jq -e '
  .persistence.defaultClass == true
  and .persistence.defaultClassReplicaCount == 3
  and .persistence.reclaimPolicy == "Retain"
  and .defaultSettings.defaultDataPath == "/var/mnt/longhorn"
' >/dev/null || {
  echo "Longhorn values must keep the default class, 3 replicas, Retain and the /var/mnt/longhorn data path." >&2
  exit 1
}
yaml_json kubernetes/apps/app-cluster/storage/longhorn/config/namespace.yaml |
  jq -e '.metadata.labels["pod-security.kubernetes.io/enforce"] == "privileged"' >/dev/null

# Worker disks are selected by size so the 100 GiB local-path disk and the ~465 GiB Longhorn
# SSD can never match each other's selector; Longhorn needs its kubelet bind mount on workers only.
yaml_json talos/app/talconfig.yaml | jq -e '
  (.worker.userVolumes | map(select(.name == "local-path-provisioner"))[0].provisioning.diskSelector.match) == "!system_disk && disk.size < 200u * GiB"
  and (.worker.userVolumes | map(select(.name == "longhorn"))[0].provisioning.diskSelector.match) == "!system_disk && disk.size > 400u * GiB"
  and (.worker.patches | index("@./patches/worker/machine-longhorn.yaml")) != null
  and ([.nodes[] | select(.controlPlane == false) | .talosImageURL | test("/(613e1592b2da41ae5e265e8789429f22e121aab91cb4deb6bc3c0b6262961245|fb73a1920c434ba8ec579d24f15097f18ffb171342b1c61f68c063d1b2b601c2)$")] | all)
' >/dev/null || {
  echo "Talos worker volumes/schematics must keep the size-based selectors, Longhorn bind mount patch and iscsi-tools schematics." >&2
  exit 1
}

yaml_json kubernetes/apps/app-cluster/media/jellyfin/config/media-library-pv.yaml |
  jq -e '.kind == "PersistentVolume" and .metadata.name == "media-library-pv" and .spec.persistentVolumeReclaimPolicy == "Retain" and .spec.nfs.server == "10.0.40.2" and .spec.nfs.path == "/media" and .spec.claimRef.name == "media-library-pvc"' >/dev/null
yaml_json kubernetes/apps/app-cluster/media/jellyfin/config/media-library-pvc.yaml |
  jq -e '.kind == "PersistentVolumeClaim" and .metadata.name == "media-library-pvc" and .spec.volumeName == "media-library-pv"' >/dev/null

# Public DNS already targets the tunnel. Keep the webhook bypass first,
# route authenticated apps through TLS-verified Envoy, and deny unmatched hosts.
yaml_json kubernetes/apps/app-cluster/network/cloudflare-tunnel/config/config.yaml |
  jq -r '.data["config.yaml"]' | yaml_json - | jq -e '
    .ingress as $rules
    | ($rules | length) == 4
      and $rules[0] == {"hostname": "argo.krapulax.dev", "path": "^/api/webhook$", "service": "http://argocd-server.argo-system.svc.cluster.local:80"}
      and $rules[1] == {"hostname": "krapulax.dev", "service": "https://envoy-external.network.svc.cluster.local", "originRequest": {"originServerName": "external.krapulax.dev"}}
      and $rules[2] == {"hostname": "*.krapulax.dev", "service": "https://envoy-external.network.svc.cluster.local", "originRequest": {"originServerName": "external.krapulax.dev"}}
      and $rules[3] == {"service": "http_status:404"}
  ' >/dev/null || {
  echo "Public tunnel ingress must preserve the webhook bypass, TLS Envoy routes, and fallback 404." >&2
  exit 1
}
yaml_json kubernetes/argo/apps/app-cluster/network/cloudflare-dns.yaml |
  jq -e '.kind == "Application" and (.spec.syncPolicy | has("automated") | not)' >/dev/null

python3 -m unittest discover -s tests -p 'test_*.py'

echo "Validation passed: required files, tunnel ingress, manual DNS and local-path/NFS/Longhorn safeguards."
