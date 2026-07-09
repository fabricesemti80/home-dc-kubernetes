# Domain Configuration

Centralized documentation for external and internal DNS hostnames in the cluster.

## Base Domains

| Domain                     | Target        | Description                   |
| -------------------------- | ------------- | ----------------------------- |
| `krapulax.dev`             | -             | Primary domain                |
| `external.krapulax.dev`    | -             | External load balancer target |
| `internal.krapulax.dev`    | -             | Internal routing              |
| `krapulax.home`            | -             | Internal Technitium zone      |
| `kubernetes.krapulax.home` | `10.0.40.102` | Internal gateway target       |

## Application Hostnames

### Argo CD

-   **URL:** `https://argo.krapulax.dev`
-   **Config:** `kubernetes/argo/apps/argo-system/argo-cd/config/http-route.yaml`

### Productivity

| App        | Hostname                  | Config                                                           |
| ---------- | ------------------------- | ---------------------------------------------------------------- |
| Linkwarden | `linkwarden.krapulax.dev` | `kubernetes/apps/productivity/linkwarden/config/http-route.yaml` |

### Media

| App         | Hostname                   | Config                                                     |
| ----------- | -------------------------- | ---------------------------------------------------------- |
| Jellyfin    | `jelly.krapulax.dev`       | `kubernetes/apps/media/jellyfin/config/http-route.yaml`    |
| SABnzbd     | `sabnzbd.krapulax.dev`     | `kubernetes/apps/media/sabnzbd/config/http-route.yaml`     |
| qBittorrent | `qbittorrent.krapulax.dev` | `kubernetes/apps/media/qbittorrent/config/http-route.yaml` |
| Sonarr      | `sonarr.krapulax.dev`      | `kubernetes/apps/media/sonarr/config/http-route.yaml`      |
| Radarr      | `radarr.krapulax.dev`      | `kubernetes/apps/media/radarr/config/http-route.yaml`      |
| Prowlarr    | `prowlarr.krapulax.dev`    | `kubernetes/apps/media/prowlarr/config/http-route.yaml`    |
| Jellyseerr  | `requests.krapulax.dev`    | `kubernetes/apps/media/jellyseerr/config/http-route.yaml`  |
| Tdarr       | `tdarr.krapulax.dev`       | `kubernetes/apps/media/tdarr/config/http-route.yaml`       |
| Immich      | `photos.krapulax.dev`      | `kubernetes/apps/media/immich/config/http-route.yaml`      |

### Monitoring

| App          | Hostname                    | Config                                                                    |
| ------------ | --------------------------- | ------------------------------------------------------------------------- |
| Grafana      | `grafana.krapulax.dev`      | `kubernetes/apps/monitoring/kube-prometheus-stack/config/http-route.yaml` |
| Alertmanager | `alertmanager.krapulax.dev` | `kubernetes/apps/monitoring/kube-prometheus-stack/values.yaml`            |

### Web

| App    | Hostname              | Config                                              |
| ------ | --------------------- | --------------------------------------------------- |
| Glance | `glance.krapulax.dev` | `kubernetes/apps/web/glance/config/http-route.yaml` |
| Echo   | `echo.krapulax.dev`   | `kubernetes/apps/default/echo/values.sops.yaml`     |

## Deprecated / Inactive

-   `plex.krapulax.net` - External Plex server (not in this repo)
-   `nginx-test.krapulax.dev` - Test endpoint
-   `traefik.krapulax.dev` - Unused

## Notes

-   External `krapulax.dev` records are managed by `cloudflare-dns`.
-   Internal `krapulax.home` records are managed by `technitium-dns` from internal HTTPRoutes and DNSEndpoint resources.
-   Internal HTTPRoutes set `external-dns.alpha.kubernetes.io/target: kubernetes.krapulax.home`.
-   Some values reference `${DOMAIN}` variable in Glance bookmarks
-   Hostnames are defined in both HTTPRoute annotations and `external-dns.alpha.kubernetes.io/hostname`
-   The `external-dns.alpha.kubernetes.io/target` annotation points to `external.krapulax.dev` for all apps
