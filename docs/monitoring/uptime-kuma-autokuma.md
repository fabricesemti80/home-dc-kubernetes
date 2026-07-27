# Uptime Kuma and AutoKuma

## Purpose

Uptime Kuma provides external availability checks, response-time history, certificate expiry visibility, and status pages for services exposed under `*.krapulax.dev`.

AutoKuma makes the monitor inventory declarative. Monitor definitions live in Git, Argo CD deploys them as a ConfigMap, and AutoKuma reconciles them into Uptime Kuma automatically.

## Architecture

```text
Git repository
  kubernetes/apps/monitoring/uptime-kuma-infra/
    values.yaml
    config/autokuma-monitors.yaml
          |
          v
Argo CD application: uptime-kuma-infra
          |
          v
infra-cluster / monitoring namespace
  Uptime Kuma  <---- AutoKuma
       ^              |
       |              +-- reads monitor JSON files from /config/monitors
       +-- credentials supplied by uptime-kuma-credentials Secret
```

Uptime Kuma and AutoKuma run as separate controllers in the same app-template Helm release. Both are pinned to `infra-wk-01` and use hostPath persistence:

- Uptime Kuma: `/var/uptime-kuma/data`
- AutoKuma: `/var/autokuma/data`

The Uptime Kuma UI is exposed at `https://uptime.krapulax.dev` through the infra-cluster Cloudflare Tunnel.

## Declarative monitor flow

The monitor inventory is defined in:

```text
kubernetes/apps/monitoring/uptime-kuma-infra/config/autokuma-monitors.yaml
```

Each ConfigMap entry is one AutoKuma JSON monitor:

```yaml
example.json: |-
  {
    "type": "http",
    "name": "Example",
    "url": "https://example.krapulax.dev",
    "interval": 60,
    "max_retries": 3
  }
```

The ConfigMap is mounted into AutoKuma at `/config/monitors`. A change follows this path:

1. A monitor definition is added, updated, or removed in Git.
2. Argo CD synchronizes the ConfigMap.
3. Reloader restarts AutoKuma when the mounted configuration changes.
4. AutoKuma reconciles Uptime Kuma to the desired state.
5. Removed Git-managed monitors are deleted because `AUTOKUMA__ON_DELETE` is set to `delete`.

Do not manually edit an AutoKuma-managed monitor in the Uptime Kuma UI. The next reconciliation may overwrite that change.

## Credentials

AutoKuma authenticates to Uptime Kuma using the Kubernetes Secret:

```text
uptime-kuma-credentials
```

The Secret is populated by the Doppler operator from:

```text
project: project-homelab
config:  dev_homelab
keys:
  UPTIME_KUMA_USERNAME
  UPTIME_KUMA_PASSWORD
```

The initial Uptime Kuma administrator account must use the same credentials. After that one-time bootstrap, AutoKuma can connect and provision monitors.

## Monitor inclusion policy

For now, the inventory includes services that have a repository-managed HTTPS route using a public `*.krapulax.dev` hostname.

Excluded by default:

- internal-only `*.krapulax.home` routes;
- raw ClusterIP or node endpoints;
- services without a public HTTPS hostname;
- legacy Docker-hosted records not represented by the Kubernetes route inventory.

An HTTP monitor validates the complete external path, including public DNS, Cloudflare, the appropriate Cloudflare Tunnel, the Kubernetes service, and the application response. This is intentionally different from a Kubernetes readiness probe, which only validates the workload from inside the cluster.

## Adding a monitor

When a new public HTTPS route is introduced:

1. Confirm the hostname resolves through the correct cluster endpoint.
2. Add a JSON entry to `autokuma-monitors.yaml`.
3. Use a stable, user-facing monitor name.
4. Start with a 60-second interval and three retries unless the service needs different behaviour.
5. Merge and allow Argo CD and AutoKuma to reconcile it.

For services that return an expected non-2xx response, require authentication, or expose a dedicated health endpoint, extend the monitor definition rather than accepting a permanently failing default check.

## Operations and troubleshooting

### Monitor does not appear

Check:

- the `autokuma-monitors` ConfigMap exists in `monitoring`;
- AutoKuma has restarted after the ConfigMap update;
- the AutoKuma pod can read `/config/monitors`;
- the credential Secret exists and matches the Uptime Kuma account;
- AutoKuma logs for JSON parsing or authentication errors.

### Monitor is down but the pod is healthy

The public HTTP monitor covers more dependencies than the pod probe. Verify in order:

1. public DNS target;
2. Cloudflare Tunnel status and hostname ingress;
3. Gateway or route attachment;
4. Kubernetes Service and endpoints;
5. application response and authentication behaviour.

### Cloudflare error 1033

Error 1033 normally means Cloudflare resolved the hostname to a tunnel that is not connected or does not own that hostname. Verify that application services point to the apps-cluster endpoint and infra services point to the infra-cluster endpoint.

## Relationship to other monitoring

Uptime Kuma complements rather than replaces Prometheus, Grafana, Alertmanager, Pulse, readiness probes, and liveness probes:

- probes determine whether Kubernetes should route traffic or restart a workload;
- Prometheus and Grafana provide metrics and internal observability;
- Alertmanager handles metric-based alerting;
- Pulse provides infrastructure visibility;
- Uptime Kuma validates user-visible external reachability and TLS certificates.
