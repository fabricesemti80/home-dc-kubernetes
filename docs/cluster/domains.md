# Domain Configuration

Centralized documentation for external and internal DNS hostnames in the cluster.

## Base Domains

| Domain                        | Target                    | Description                                          |
| ----------------------------- | ------------------------- | ---------------------------------------------------- |
| `krapulax.dev`                | -                         | Primary domain                                       |
| `external-apps.krapulax.dev`  | `kubernetes-apps` tunnel  | New canonical public endpoint for app-cluster routes |
| `external-infra.krapulax.dev` | `kubernetes-infra` tunnel | Canonical public endpoint for infra-cluster services |
| `internal.krapulax.dev`       | -                         | Internal routing                                     |
| `krapulax.home`               | -                         | Internal zone; DNS automation currently inactive     |
| `kubernetes.krapulax.home`    | `10.0.40.102`             | Internal gateway target                              |
| `kestra.krapulax.home`        | `10.0.40.106`             | Infra-cluster internal Kestra                        |

## External endpoint migration

The target architecture contains only two public cluster endpoints:

-   app-cluster services use `external-apps.krapulax.dev`;
-   infra-cluster services use `external-infra.krapulax.dev`.

The migration from `external.krapulax.dev` is complete:

1. app-cluster routes target `external-apps.krapulax.dev`;
2. infra-cluster public records target `external-infra.krapulax.dev`;
3. `external.krapulax.dev` is not published as a Cloudflare DNS record.
4. service records do not point directly at `*.cfargotunnel.com` tunnel IDs.

## Application Hostnames

### Argo CD

-   **URL:** `https://argo.krapulax.dev`
-   **Config:** `kubernetes/apps/app-cluster/argo-system/argo-cd/config/http-route.yaml`

### Productivity

| App        | Hostname                  | Config                                                                       |
| ---------- | ------------------------- | ---------------------------------------------------------------------------- |
| Linkwarden | `linkwarden.krapulax.dev` | `kubernetes/apps/app-cluster/productivity/linkwarden/config/http-route.yaml` |
| ConvertX   | `convertx.krapulax.dev`   | `kubernetes/apps/app-cluster/productivity/convertx/config/http-route.yaml`   |

### Media

| App         | Hostname                   | Config                                                                 |
| ----------- | -------------------------- | ---------------------------------------------------------------------- |
| Jellyfin    | `jelly.krapulax.dev`       | `kubernetes/apps/app-cluster/media/jellyfin/config/http-route.yaml`    |
| SABnzbd     | `sabnzbd.krapulax.dev`     | `kubernetes/apps/app-cluster/media/sabnzbd/config/http-route.yaml`     |
| qBittorrent | `qbittorrent.krapulax.dev` | `kubernetes/apps/app-cluster/media/qbittorrent/config/http-route.yaml` |
| Sonarr      | `sonarr.krapulax.dev`      | `kubernetes/apps/app-cluster/media/sonarr/config/http-route.yaml`      |
| Radarr      | `radarr.krapulax.dev`      | `kubernetes/apps/app-cluster/media/radarr/config/http-route.yaml`      |
| Prowlarr    | `prowlarr.krapulax.dev`    | `kubernetes/apps/app-cluster/media/prowlarr/config/http-route.yaml`    |
| Jellyseerr  | `requests.krapulax.dev`    | `kubernetes/apps/app-cluster/media/jellyseerr/config/http-route.yaml`  |
| Tdarr       | `tdarr.krapulax.dev`       | `kubernetes/apps/app-cluster/media/tdarr/config/http-route.yaml`       |
| Immich      | `photos.krapulax.dev`      | `kubernetes/apps/app-cluster/media/immich/config/http-route.yaml`      |

### Monitoring

| App          | Hostname                    | Cluster | Config                                                                                |
| ------------ | --------------------------- | ------- | ------------------------------------------------------------------------------------- |
| Grafana      | `grafana.krapulax.dev`      | apps    | `kubernetes/apps/app-cluster/monitoring/kube-prometheus-stack/config/http-route.yaml` |
| Alertmanager | `alertmanager.krapulax.dev` | apps    | `kubernetes/apps/app-cluster/monitoring/kube-prometheus-stack/values.yaml`            |
| Pulse        | `pulse.krapulax.dev`        | infra   | `kubernetes/apps/infra-cluster/monitoring/pulse-infra/config/http-route.yaml`         |
| Uptime Kuma  | `uptime.krapulax.dev`       | infra   | `kubernetes/apps/infra-cluster/monitoring/uptime-kuma-infra/config/http-route.yaml`   |

### Automation

| App    | Hostname                                      | Cluster | Config                                                                                                                                                                                                                                                     |
| ------ | --------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Kestra | `kestra.krapulax.dev`, `kestra.krapulax.home` | infra   | `kubernetes/apps/app-cluster/network/cloudflare-tunnel/config/kestra-dnsendpoint.yaml`, `kubernetes/apps/infra-cluster/automation/kestra-infra/config/http-route.yaml`, `kubernetes/apps/infra-cluster/network/cloudflare-tunnel-infra/config/config.yaml` |

### Web

| App    | Hostname              | Config                                                          |
| ------ | --------------------- | --------------------------------------------------------------- |
| Glance | `glance.krapulax.dev` | `kubernetes/apps/app-cluster/web/glance/config/http-route.yaml` |
| Echo   | `echo.krapulax.dev`   | `kubernetes/apps/app-cluster/default/echo/values.sops.yaml`     |

## Deprecated / Inactive

-   `plex.krapulax.net` - External Plex server (not in this repo)
-   `nginx-test.krapulax.dev` - Test endpoint
-   `traefik.krapulax.dev` - Unused

## Notes

-   External `krapulax.dev` records are managed by the app-cluster ExternalDNS deployment.
-   Public infra service records target `external-infra.krapulax.dev`; only `external-infra.krapulax.dev` points at the infra tunnel ID.
-   Internal `krapulax.home` DNS automation is currently inactive while the Technitium deployment is redesigned.
-   Internal HTTPRoutes set `external-dns.alpha.kubernetes.io/target: kubernetes.krapulax.home`.
-   Hostnames may be defined in both HTTPRoute annotations and central `DNSEndpoint` resources.
