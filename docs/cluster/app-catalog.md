# 📚 App Catalog

This document provides an index of all applications deployed in the Kubernetes cluster.

## ☸️ Cluster Overview

| Namespace               | App Count | Description                                         |
| ----------------------- | --------- | --------------------------------------------------- |
| media                   | 9         | Media management and playback                       |
| network                 | 5         | DNS, Cloudflare tunnel and gateway                  |
| argo-system             | 1         | Argo CD                                             |
| kube-system             | 6         | Cilium, CoreDNS, GPU operator and system components |
| default                 | 2         | Homepage and Echo                                   |
| storage                 | 1         | Local-path provisioner                              |
| ci-cd                   | 2         | Actions runner controller and runner set            |
| cert-manager            | 1         | Certificate manager                                 |
| doppler-operator-system | 1         | Doppler operator                                    |
| trading                 | 1         | Freqtrade crypto bot (dry-run)                      |

---

## 📦 Applications by Namespace

### 🎬 media

| App         | Type             | Image                            | Port | Domain                   | Notes                                    |
| ----------- | ---------------- | -------------------------------- | ---- | ------------------------ | ---------------------------------------- |
| jellyfin    | Media Server     | lscr.io/linuxserver/jellyfin     | 8096 | jelly.krapulax.dev       | Media player; Longhorn config + cache    |
| jellyseerr  | Request Manager  | seerr-team/seerr                 | 5055 | requests.krapulax.dev    | Media requests; Longhorn config          |
| immich      | Photo Management | ghcr.io/immich-app/immich-server | 2283 | photos.krapulax.dev      | Photo/video backup; Longhorn DB/Redis/ML |
| prowlarr    | Indexer Manager  | lscr.io/linuxserver/prowlarr     | 9696 | prowlarr.krapulax.dev    | Usenet/Torrent indexers; Longhorn config |
| qbittorrent | Torrent Client   | lscr.io/linuxserver/qbittorrent  | 8080 | qbittorrent.krapulax.dev | Torrent downloads; Longhorn config       |
| radarr      | Movie Manager    | lscr.io/linuxserver/radarr       | 7878 | radarr.krapulax.dev      | Movie automation; Longhorn config        |
| sonarr      | TV Manager       | lscr.io/linuxserver/sonarr       | 8989 | sonarr.krapulax.dev      | TV automation; Longhorn config           |
| sabnzbd     | Usenet Client    | lscr.io/linuxserver/sabnzbd      | 8080 | sabnzbd.krapulax.dev     | Usenet downloads; Longhorn config        |
| recyclarr   | Sync Tool        | ghcr.io/recyclarr/recyclarr      | -    | -                        | Sonarr/Radarr sync; Longhorn config      |

### 📈 trading

| App       | Type        | Image                  | Port | Domain                  | Notes                                                                          |
| --------- | ----------- | ---------------------- | ---- | ----------------------- | ------------------------------------------------------------------------------ |
| freqtrade | Trading Bot | freqtradeorg/freqtrade | 8080 | freqtrade.krapulax.home | Dry-run only; internal UI; LLM entry veto; data on Longhorn (`freqtrade-data`) |

### 🔹 network

| App               | Type           | Image                     | Port | Notes               |
| ----------------- | -------------- | ------------------------- | ---- | ------------------- |
| cloudflare-dns    | DNS Controller | bitnami/k8s-sidecar       | -    | External DNS        |
| cloudflare-tunnel | Tunnel         | cloudflare/cloudflared    | -    | Cloudflare Tunnel   |
| k8s-gateway       | Gateway        | projectsorted/k8s-gateway | -    | DNS discovery       |
| envoy-gateway     | Gateway API    | envoyproxy/gateway        | -    | App-cluster ingress |
| technitium-dns    | DNS Controller | external-dns              | -    | Internal DNS sync   |

### 💾 storage

The app-cluster apps use Longhorn (`ReadWriteOnce`, 3 replicas) for config, state, caches and queues. The `local-path` provisioner stays deployed but no app-cluster claim uses it any more (old claims deleted 2026-11-10).

| App      | Type          | Chart             | Port | Domain                 | Notes                                                                                                                                                          |
| -------- | ------------- | ----------------- | ---- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| longhorn | Block storage | longhorn/longhorn | 80   | longhorn.krapulax.home | Default StorageClass, 3 replicas on passthrough SSDs, internal UI only, manual sync, used by every app-cluster app claim; [runbook](../operations/longhorn.md) |

### 🔹 argo-system

| App     | Type   | Image            | Port | Domain            | Notes             |
| ------- | ------ | ---------------- | ---- | ----------------- | ----------------- |
| argo-cd | GitOps | argoproj/argo-cd | 8080 | argo.krapulax.dev | GitOps controller |

### 🔹 kube-system

| App            | Type            | Image                                    | Notes                    |
| -------------- | --------------- | ---------------------------------------- | ------------------------ |
| cilium         | CNI             | cilium/cilium                            | App-cluster networking   |
| coredns        | DNS             | registry.k8s.io/coredns                  | Cluster DNS              |
| reloader       | Config Reloader | stakater/reloader                        | Config restart watcher   |
| metrics-server | Metrics         | registry.k8s.io/metrics-server           | Resource metrics         |
| spegel         | Mirror          | ghcr.io/spegel/spegel                    | Image mirror             |
| gpu-operator   | GPU             | nvcr.io/nvidia/cloud-native/gpu-operator | NVIDIA device management |

### 🔹 default

| App      | Type      | Image                        | Port | Domain                | Notes          |
| -------- | --------- | ---------------------------- | ---- | --------------------- | -------------- |
| echo     | Test      | hashicorp/http-echo          | 5678 | echo.krapulax.dev     | Test endpoint  |
| homepage | Dashboard | ghcr.io/gethomepage/homepage | 3000 | homepage.krapulax.dev | Home dashboard |

### 🔹 doppler-operator-system

| App              | Type    | Image                                       | Notes            |
| ---------------- | ------- | ------------------------------------------- | ---------------- |
| doppler-operator | Secrets | mirror.gcr.io/dopplerhq/kubernetes-operator | Doppler operator |

### ☸️ infra-cluster

Argo CD on `app-cluster` also deploys these `infra-cluster` workloads:

| App                          | Type       | Image                                       | Notes                      |
| ---------------------------- | ---------- | ------------------------------------------- | -------------------------- |
| doppler-operator-infra       | Secrets    | mirror.gcr.io/dopplerhq/kubernetes-operator | Doppler operator           |
| reloader-infra               | Reloader   | stakater/reloader                           | Config reload watcher      |
| uptime-kuma-infra            | Monitoring | louislam/uptime-kuma                        | Uptime monitoring          |
| cloudflare-tunnel-infra      | Tunnel     | cloudflare/cloudflared                      | Cloudflare Tunnel          |
| envoy-gateway-infra          | Gateway    | envoyproxy/gateway                          | Gateway API implementation |
| tailscale-infra              | Tailscale  | tailscale/tailscale                         | Tailscale operator         |
| technitium-dns-infra         | DNS Sync   | external-dns                                | Internal DNS records       |
| technitium-infra             | DNS        | technitium/dns-server                       | DNS admin/server           |
| local-path-provisioner-infra | Storage    | rancher/local-path-provisioner              | Local PV provisioner       |

Both clusters also have a `nas-backup` GitOps Application provisioning the retained
`backups/k8s-backup` NFS claim; no storage-server image runs for this target.
The Backrest replacement adds independent `backrest-app` / `backrest-infra`
instances in `backups`, using pinned upstream Backrest v1.14.1. Internal UIs:
`backrest.krapulax.home` and `backrest-infra.krapulax.home`.
See the [Backrest runbook](../operations/backrest.md) for coverage and cutover gates.
Kestra and the KubeVirt/CDI/Manager trial are removed from desired configuration.
Their runtime was removed by the [ordered retirement procedure](../architecture/nas-backup-target.md#kestra--kubevirt-retirement);
its namespaces and leftovers were removed on 2026-11-09, and the three `Released`
PVs they left on the infra cluster (Kestra object store, Kestra PostgreSQL and the
old LiteLLM PostgreSQL) were deleted with their directories on 2026-11-11 (#562,
[record](../architecture/nas-backup-target.md#retained-volumes-deleted-2026-11-11-issue-562)).

---

## 📝 Image Summary

### 🔹 LinuxServer.io (lscr.io)

-   jellyfin, jellyseerr, sonarr, radarr, prowlarr, qbittorrent, sabnzbd

### 🔹 GHCR.IO

-   immich-app/immich-server, immich-app/immich-machine-learning
-   recyclarr/recyclarr
-   spegel/spegel

### 🔹 Official

-   argoproj/argo-cd, bitnami/k8s-sidecar, cloudflare/cloudflared, hashicorp/http-echo
-   stakater/reloader, cilium/cilium
-   projectsorted/k8s-gateway, registry.k8s.io/coredns

---

## ➕ Adding New Apps

See [Adding Applications](adding-applications.md) for the workflow.
