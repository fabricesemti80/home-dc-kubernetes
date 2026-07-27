# Domain Configuration

Centralized documentation for external and internal DNS hostnames in the cluster.

## Base Domains

| Domain                        | Target                    | Description                                             |
| ----------------------------- | ------------------------- | ------------------------------------------------------- |
| `krapulax.dev`                | -                         | Primary domain                                          |
| `external.krapulax.dev`       | `kubernetes-apps` tunnel  | Legacy apps endpoint retained during canary validation  |
| `external-apps.krapulax.dev`  | `kubernetes-apps` tunnel  | New canonical public endpoint for app-cluster routes    |
| `external-infra.krapulax.dev` | `kubernetes-infra` tunnel | Canonical public endpoint for infra-cluster services    |
| `internal.krapulax.dev`       | -                         | Internal routing                                        |
| `krapulax.home`               | -                         | Internal zone; DNS automation currently inactive        |
| `kubernetes.krapulax.home`    | `10.0.40.102`             | Internal gateway target                                 |
| `kestra.krapulax.home`        | `10.0.40.106`             | Infra-cluster internal Kestra                           |

## External endpoint migration

The target architecture contains only two public cluster endpoints:

- app-cluster services use `external-apps.krapulax.dev`;
- infra-cluster services use `external-infra.krapulax.dev`.

The migration is deliberately split into two stages.

### Stage 1: canary validation

During the canary stage, `external.krapulax.dev` remains unchanged and continues to point directly to the apps tunnel. Existing application records therefore keep their current path.

Two canaries validate the new endpoints:

| Canary     | Cluster | DNS target                         |
| ---------- | ------- | ---------------------------------- |
| ConvertX   | apps    | `external-apps.krapulax.dev`       |
| Uptime Kuma| infra   | `external-infra.krapulax.dev`      |

Both canonical endpoint records point directly to their respective Cloudflare Tunnel hostnames. The legacy endpoint is not chained through the new apps endpoint.

### Stage 2: full migration

After both canaries are confirmed healthy:

1. change every remaining app-cluster route target from `external.krapulax.dev` to `external-apps.krapulax.dev`;
2. verify all infra-cluster public records use `external-infra.krapulax.dev`;
3. confirm no service record points directly to a tunnel UUID;
4. delete `external.krapulax.dev` completely;
5. add validation preventing the legacy endpoint from being reintroduced.

## Application Hostnames

### Argo CD

- **URL:** `https://argo.krapulax.dev`
- **Config:** `kubernetes/argo/apps/argo-system/argo-cd/config/http-route.yaml`

### Productivity

| App        | Hostname                  | Config                                                           |
| ---------- | ------------------------- | ---------------------------------------------------------------- |
| Linkwarden | `linkwarden.krapulax.dev` | `kubernetes/apps/productivity/linkwarden/config/http-route.yaml` |
| ConvertX   | `convertx.krapulax.dev`   | `kubernetes/apps/productivity/convertx/config/http-route.yaml`   |

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

- `plex.krapulax.net` - External Plex server (not in this repo)
- `nginx-test.krapulax.dev` - Test endpoint
- `traefik.krapulax.dev` - Unused

## Notes

- External `krapulax.dev` records are managed by the app-cluster ExternalDNS deployment.
- Internal `krapulax.home` DNS automation is currently inactive while the Technitium deployment is redesigned.
- Internal HTTPRoutes set `external-dns.alpha.kubernetes.io/target: kubernetes.krapulax.home`.
- Hostnames may be defined in both HTTPRoute annotations and central `DNSEndpoint` resources.
