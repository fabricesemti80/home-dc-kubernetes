# App Catalog

This document provides an index of all applications deployed in the Kubernetes cluster.

## Cluster Overview

| Namespace               | App Count | Description                                             |
| ----------------------- | --------- | ------------------------------------------------------- |
| media                   | 10        | Media management stack (Jellyfin, Sonarr, Radarr, etc.) |
| productivity            | 1         | Linkwarden                                              |
| monitoring              | 1         | Prometheus/Grafana stack                                |
| network                 | 2         | Cloudflare DNS and Tunnel                               |
| web                     | 1         | Glance dashboard                                        |
| argo-system             | 1         | Argo CD                                                 |
| kube-system             | 5         | System components (Cilium, CoreDNS, etc.)               |
| default                 | 1         | Echo (test app)                                         |
| doppler-operator-system | 1         | Doppler operator                                        |

---

## Applications by Namespace

### media

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
| tdarr       | Transcoder       | ghcr.io/haveagitgat/tdarr        | 8265 | tdarr.krapulax.dev       | Media transcode checks   |

### productivity

| App        | Type             | Image                         | Port | Domain                  | Notes                        |
| ---------- | ---------------- | ----------------------------- | ---- | ----------------------- | ---------------------------- |
| linkwarden | Bookmark Manager | ghcr.io/linkwarden/linkwarden | 3000 | linkwarden.krapulax.dev | Self-hosted bookmark manager |

### monitoring

| App                   | Type       | Image                    | Port      | Domain               | Notes                |
| --------------------- | ---------- | ------------------------ | --------- | -------------------- | -------------------- |
| kube-prometheus-stack | Monitoring | prom/prometheus-operator | 9090/3000 | grafana.krapulax.dev | Prometheus + Grafana |

### network

| App               | Type           | Image                     | Port | Notes             |
| ----------------- | -------------- | ------------------------- | ---- | ----------------- |
| cloudflare-dns    | DNS Controller | bitnami/k8s-sidecar       | -    | External DNS      |
| cloudflare-tunnel | Tunnel         | cloudflare/cloudflared    | -    | Cloudflare Tunnel |
| k8s-gateway       | Gateway        | projectsorted/k8s-gateway | -    | DNS discovery     |

### web

| App    | Type      | Image                    | Port | Domain              | Notes          |
| ------ | --------- | ------------------------ | ---- | ------------------- | -------------- |
| glance | Dashboard | ghcr.io/glanceapp/glance | 8080 | glance.krapulax.dev | Home dashboard |

### argo-system

| App     | Type   | Image            | Port | Domain            | Notes             |
| ------- | ------ | ---------------- | ---- | ----------------- | ----------------- |
| argo-cd | GitOps | argoproj/argo-cd | 8080 | argo.krapulax.dev | GitOps controller |

### kube-system

| App            | Type            | Image                          | Notes |
| -------------- | --------------- | ------------------------------ | ----- |
| cilium         | CNI             | cilium/cilium                  |
| coredns        | DNS             | registry.k8s.io/coredns        |
| reloader       | Config Reloader | stakater/reloader              |
| metrics-server | Metrics         | registry.k8s.io/metrics-server |
| spegel         | Mirror          | ghcr.io/spegel/spegel          |

### default

| App  | Type | Image               | Port | Domain            | Notes         |
| ---- | ---- | ------------------- | ---- | ----------------- | ------------- |
| echo | Test | hashicorp/http-echo | 5678 | echo.krapulax.dev | Test endpoint |

### doppler-operator-system

| App              | Type    | Image                                       | Notes            |
| ---------------- | ------- | ------------------------------------------- | ---------------- |
| doppler-operator | Secrets | mirror.gcr.io/dopplerhq/kubernetes-operator | Doppler operator |

---

## Image Summary

### LinuxServer.io (lscr.io)

-   jellyfin, jellyseerr, sonarr, radarr, prowlarr, qbittorrent, sabnzbd

### GHCR.IO

-   immich-app/immich-server, immich-app/immich-machine-learning
-   linkwarden/linkwarden
-   glanceapp/glance
-   recyclarr/recyclarr
-   spegel/spegel

### Official

-   argoproj/argo-cd, bitnami/k8s-sidecar, cloudflare/cloudflared, hashicorp/http-echo
-   prom/prometheus-operator, stakater/reloader, cilium/cilium
-   projectsorted/k8s-gateway, registry.k8s.io/coredns

---

## Adding New Apps

See [Adding Applications](adding-applications.md) for the workflow.
