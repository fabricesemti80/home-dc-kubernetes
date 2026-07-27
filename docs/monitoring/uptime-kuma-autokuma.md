# Uptime Kuma and AutoKuma

## Purpose

Uptime Kuma provides external availability checks, response-time history, certificate expiry visibility, and status pages for services exposed under `*.krapulax.dev`.

AutoKuma makes the monitor inventory declarative. Public Kubernetes HTTPRoutes are scanned by a repository generator, the generated monitor ConfigMap is committed to Git, Argo CD deploys it, and AutoKuma reconciles the definitions into Uptime Kuma.

## Architecture

```text
Kubernetes HTTPRoutes
        |
        v
scripts/generate-autokuma-monitors.py
        |
        v
config/autokuma-monitors.yaml
        |
        v
Git -> Argo CD -> ConfigMap -> AutoKuma -> Uptime Kuma
```

Uptime Kuma and AutoKuma run as separate controllers in the same app-template Helm release on the infra cluster. Both are pinned to `infra-wk-01` and use hostPath persistence:

- Uptime Kuma: `/var/uptime-kuma/data`
- AutoKuma: `/var/autokuma/data`

The UI is exposed at `https://uptime.krapulax.dev` through the infra-cluster Cloudflare Tunnel.

## Generated monitor inventory

The generated output is:

```text
kubernetes/apps/monitoring/uptime-kuma-infra/config/autokuma-monitors.yaml
```

Do not edit that file manually. Generate it with:

```bash
task monitoring:generate-autokuma
```

Verify that it is current with:

```bash
task monitoring:check-autokuma
```

The normal repository validation also runs the drift check:

```bash
task validate
```

The generator:

1. scans YAML files under `kubernetes/` whose filenames contain `http-route` or `httproute`;
2. selects resources with `kind: HTTPRoute`;
3. reads public hostnames matching `*.krapulax.dev`;
4. ignores internal `*.krapulax.home` and non-public hostnames;
5. de-duplicates hostnames;
6. sorts the resulting monitors deterministically;
7. writes one AutoKuma JSON document per hostname into the ConfigMap.

Each generated monitor uses HTTPS, a 60-second interval, and three retries.

## Adding or removing monitoring

A public service becomes monitored through its route definition:

1. add or update the application's public `HTTPRoute`;
2. run `task monitoring:generate-autokuma`;
3. review the generated ConfigMap change;
4. commit the route and generated output together.

Removing the public route and regenerating removes the corresponding monitor. AutoKuma deletes missing Git-managed monitors because `AUTOKUMA__ON_DELETE` is set to `delete`.

For a friendly monitor name, prefer the route annotation:

```yaml
metadata:
  annotations:
    gethomepage.dev/name: Example Service
```

The generator also contains a small set of hostname-based display-name overrides for names such as Argo CD, qBittorrent, SABnzbd, and Stirling PDF.

## Reconciliation flow

1. Argo CD synchronizes the generated ConfigMap.
2. Reloader restarts AutoKuma when the mounted ConfigMap changes.
3. AutoKuma reads JSON monitor files from `/config/monitors`.
4. AutoKuma creates, updates, or deletes its managed monitors in Uptime Kuma.
5. Uptime Kuma performs the external HTTPS checks and stores heartbeats and response-time history.

Do not manually edit an AutoKuma-managed monitor in the Uptime Kuma UI. A later reconciliation may overwrite the change.

## Credentials

AutoKuma authenticates with the `uptime-kuma-credentials` Kubernetes Secret. The Doppler operator populates it from `project-homelab` / `dev_homelab` using:

```text
UPTIME_KUMA_USERNAME
UPTIME_KUMA_PASSWORD
```

The initial Uptime Kuma administrator account must use the same credentials.

## Scope and limitations

The generator intentionally includes only repository-managed public HTTPS routes under `*.krapulax.dev`.

It excludes:

- internal-only `*.krapulax.home` routes;
- raw ClusterIP, node, or IP endpoints;
- services without a public route;
- legacy Docker-hosted DNS records not represented by Kubernetes HTTPRoutes.

An HTTP monitor validates the full user-visible path: public DNS, Cloudflare, the selected tunnel, Kubernetes routing, the service, the application response, and TLS certificate validity. It complements rather than replaces readiness probes, Prometheus, Grafana, Alertmanager, or Pulse.

Some authenticated applications may return redirects, 401, or 403 responses. Those services may need a dedicated health path or an explicit AutoKuma override in a future extension. The generated inventory currently uses the standard HTTP monitor defaults.

## Troubleshooting

### Generated inventory is stale

Run:

```bash
task monitoring:generate-autokuma
```

Then review and commit the ConfigMap diff. `task validate` fails while generated output differs from route discovery.

### Monitor does not appear

Check that:

- the generated hostname exists in `autokuma-monitors.yaml`;
- Argo CD synchronized the `uptime-kuma-infra` application;
- the ConfigMap exists in the `monitoring` namespace;
- AutoKuma restarted after the ConfigMap changed;
- AutoKuma can authenticate to Uptime Kuma;
- AutoKuma logs contain no JSON parsing or API errors.

### Monitor is down but the pod is healthy

Verify in order:

1. public DNS target;
2. Cloudflare Tunnel connection and hostname ingress;
3. Gateway and HTTPRoute attachment;
4. Kubernetes Service and endpoints;
5. application response or authentication behaviour.

### Cloudflare error 1033

Error 1033 normally indicates that the hostname resolves to a tunnel that is not connected or does not own that hostname. Application services should resolve through the apps-cluster endpoint, while infra services should resolve through the infra-cluster endpoint.
