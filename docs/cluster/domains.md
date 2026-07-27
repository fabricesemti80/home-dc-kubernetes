# Domain Configuration

Centralized documentation for external and internal DNS hostnames in the cluster.

## Base Domains

| Domain                           | Target                         | Description                                      |
| -------------------------------- | ------------------------------ | ------------------------------------------------ |
| `krapulax.dev`                   | -                              | Primary domain                                   |
| `external-apps.krapulax.dev`     | `kubernetes-apps` tunnel       | Canonical public endpoint for app-cluster routes |
| `external-infra.krapulax.dev`    | `kubernetes-infra` tunnel      | Canonical public endpoint for infra services     |
| `external.krapulax.dev`          | `external-apps.krapulax.dev`   | Compatibility alias; do not use for new routes   |
| `internal.krapulax.dev`          | -                              | Internal routing                                 |
| `krapulax.home`                  | -                              | Internal zone; DNS automation currently inactive |
| `kubernetes.krapulax.home`       | `10.0.40.102`                  | Internal gateway target                          |
| `kestra.krapulax.home`           | `10.0.40.106`                  | Infra-cluster internal Kestra                    |

## External routing policy

Public DNS records must target the endpoint belonging to the cluster that runs the service:

- app-cluster services use `external-apps.krapulax.dev`
- infra-cluster services use `external-infra.krapulax.dev`
- direct `*.cfargotunnel.com` targets are reserved for the two canonical endpoint records only
- `external.krapulax.dev` is retained temporarily as a compatibility alias while manifests are migrated

Current infra services include Pulse, Kestra, and Uptime Kuma.

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
| Sonarr      | `sonarr.krapulax.dev`       | `kubernetes/apps/media/sonarr/config/http-route.yaml`      |
| Radarr      | `radarr.krapulax.dev`       | `kubernetes/apps/media/radarr/config/http-route.yaml`      |
| Prowlarr    | `prowlarr.krapulax.dev`    | `kubernetes/apps/media/prowlarr/config/http-route.yaml`    |
| Jellyseerr  | `requests.krapulax.dev`    | `kubernetes/apps/media/jellyseerr/config/http-route.yaml`  |
| Tdarr       | `tdarr.krapulax.dev`       | `kubernetes/apps/media/tdarr/config/http-route.yaml`       |
| Immich      | `photos.krapulax.dev`      | `kubernetes/apps/media/immich/config/http-route.yaml`      |

### Monitoring

| App          | Hostname                    | Cluster | Config                                                                    |
| ------------ | --------------------------- | ------- | ------------------------------------------------------------------------- |
| Grafana      | `grafana.krapulax.dev`      | apps    | `kubernetes/apps/monitoring/kube-prometheus-stack/config/http-route.yaml` |
| Alertmanager | `alertmanager.krapulax.dev` | apps    | `kubernetes/apps/monitoring/kube-prometheus-stack/values.yaml`            |
| Pulse        | `pulse.krapulax.dev`        | infra   | `kubernetes/apps/monitoring/pulse-infra/config/http-route.yaml`           |
| Uptime Kuma  | `uptime.krapulax.dev`       | infra   | `kubernetes/apps/monitoring/uptime-kuma-infra/config/http-route.yaml`     |

### Automation

| App    | Hostname                                      | Cluster | Config                                                                                                                                 |
| ------ | --------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Kestra | `kestra.krapulax.dev`, `kestra.krapulax.home` | infra   | `kubernetes/apps/automation/kestra-infra/config/http-route.yaml`, `kubernetes/apps/network/cloudflare-tunnel-infra/config/config.yaml` |

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

-   External `krapulax.dev` records are managed by the app-cluster ExternalDNS deployment.
-   Internal `krapulax.home` DNS automation is currently inactive while the Technitium deployment is redesigned.
-   Internal HTTPRoutes set `external-dns.alpha.kubernetes.io/target: kubernetes.krapulax.home`.
-   Some values reference `${DOMAIN}` variable in Glance bookmarks.
-   Hostnames may be defined in both HTTPRoute annotations and central `DNSEndpoint` resources.
