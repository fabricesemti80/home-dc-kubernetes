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

---

## 📦 Applications by Namespace

### 🎬 media

| App         | Type             | Image                            | Port | Domain                   | Notes                    |
| ----------- | ---------------- | -------------------------------- | ---- | ------------------------ | ------------------------ |
| jellyfin    | Media Server     | lscr.io/linuxserver/jellyfin     | 8096 | jelly.krapulax.dev       | Media player             |
| jellyseerr  | Request Manager  | fallenbagel/jellyseerr           | 5055 | requests.krapulax.dev    | Media requests           |
| immich      | Photo Management | ghcr.io/immich-app/immich-server | 2283 | photos.krapulax.dev      | Photo/video backup       |
| prowlarr    | Indexer Manager  | lscr.io/linuxserver/prowlarr     | 9696 | prowlarr.krapulax.dev    | Usenet/Torrent indexers  |
| qbittorrent | Torrent Client   | lscr.io/linuxserver/qbittorrent  | 8080 | qbittorrent.krapulax.dev | Torrent downloads        |
| radarr      | Movie Manager    | lscr.io/linuxserver/radarr       | 7878 | radarr.krapulax.dev      | Movie automation         |
| sonarr      | TV Manager       | lscr.io/linuxserver/sonarr       | 8989 | sonarr.krapulax.dev      | TV automation            |
| sabnzbd     | Usenet Client    | lscr.io/linuxserver/sabnzbd      | 8080 | sabnzbd.krapulax.dev     | Usenet downloads         |
| recyclarr   | Sync Tool        | ghcr.io/recyclarr/recyclarr      | -    | -                        | Aria2/Radarr sync (cron) |

### 🔹 network

| App               | Type           | Image                     | Port | Notes               |
| ----------------- | -------------- | ------------------------- | ---- | ------------------- |
| cloudflare-dns    | DNS Controller | bitnami/k8s-sidecar       | -    | External DNS        |
| cloudflare-tunnel | Tunnel         | cloudflare/cloudflared    | -    | Cloudflare Tunnel   |
| k8s-gateway       | Gateway        | projectsorted/k8s-gateway | -    | DNS discovery       |
| envoy-gateway     | Gateway API    | envoyproxy/gateway        | -    | App-cluster ingress |
| technitium-dns    | DNS Controller | external-dns              | -    | Internal DNS sync   |

### 💾 storage

The `local-path` provisioner supplies worker-local `ReadWriteOnce` volumes.

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

| App                          | Type       | Image                                       | Notes                         |
| ---------------------------- | ---------- | ------------------------------------------- | ----------------------------- |
| kestra-infra                 | Automation | kestra/kestra                               | Workflow orchestration        |
| doppler-operator-infra       | Secrets    | mirror.gcr.io/dopplerhq/kubernetes-operator | Doppler operator              |
| reloader-infra               | Reloader   | stakater/reloader                           | Config reload watcher         |
| pulse-agent-infra            | Monitoring | ghcr.io/rcourtman/pulse-agent               | Pulse cluster agent           |
| pulse-infra                  | Monitoring | docker.io/rcourtman/pulse                   | Proxmox/Docker/K8s monitoring |
| uptime-kuma-infra            | Monitoring | louislam/uptime-kuma                        | Uptime monitoring             |
| cloudflare-tunnel-infra      | Tunnel     | cloudflare/cloudflared                      | Cloudflare Tunnel             |
| envoy-gateway-infra          | Gateway    | envoyproxy/gateway                          | Gateway API implementation    |
| tailscale-infra              | Tailscale  | tailscale/tailscale                         | Tailscale operator            |
| technitium-dns-infra         | DNS Sync   | external-dns                                | Internal DNS records          |
| technitium-infra             | DNS        | technitium/dns-server                       | DNS admin/server              |
| local-path-provisioner-infra | Storage    | rancher/local-path-provisioner              | Local PV provisioner          |

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
