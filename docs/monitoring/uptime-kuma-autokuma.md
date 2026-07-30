# Uptime Kuma and AutoKuma

## Purpose

Uptime Kuma provides external availability checks, response-time history, certificate expiry visibility, and status pages for services exposed under `*.krapulax.dev`.

AutoKuma makes the monitor inventory declarative. Public Kubernetes HTTPRoutes are scanned by a repository generator, a GitHub Action commits the generated monitor ConfigMap to the pull-request branch, Argo CD deploys it, and AutoKuma reconciles the definitions into Uptime Kuma.

## Architecture

```text
Kubernetes HTTPRoutes
        |
        v
GitHub Action
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

-   Uptime Kuma: `/var/uptime-kuma/data`
-   AutoKuma: `/var/autokuma/data`

The UI is exposed at `https://uptime.krapulax.dev` through the infra-cluster Cloudflare Tunnel.

## Automatic monitor generation

The generated output is:

```text
kubernetes/apps/infra-cluster/monitoring/uptime-kuma-infra/config/autokuma-monitors.yaml
```

Do not edit that file manually. After this workflow has been merged to the default branch, pull requests that change Kubernetes route manifests automatically run `.github/workflows/generate-autokuma-monitors.yaml`, which:

1. checks out the pull request's head branch;
2. installs the pinned Mike Farah `yq` binary used by the generator;
3. runs `scripts/generate-autokuma-monitors.py`;
4. detects whether the generated ConfigMap changed;
5. commits and pushes the generated output back to the same branch when required;
6. exits without a commit when the inventory is already current.

The workflow uses a concurrency group per pull request and the bot-generated commit does not create an endless workflow loop.

Manual commands remain available for local verification or troubleshooting, but are not part of the normal application-creation workflow:

```bash
task monitoring:generate-autokuma
task monitoring:check-autokuma
task validate
```

Repository validation also runs the generator in `--check` mode, preventing stale generated output from being merged.

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

A public service becomes monitored by adding or changing its public `HTTPRoute` in a pull request. No separate monitor-maintenance step is required.

The GitHub Action updates the generated ConfigMap on that same branch, leaving the generated diff visible for review before merge. Removing the public route causes the generated monitor to disappear. AutoKuma then deletes the missing Git-managed monitor because `AUTOKUMA__ON_DELETE` is set to `delete`.

For a friendly monitor name, prefer the route annotation:

```yaml
metadata:
    annotations:
        gethomepage.dev/name: Example Service
```

The generator also contains a small set of hostname-based display-name overrides for names such as Argo CD, qBittorrent, SABnzbd, and Stirling PDF.

## Reconciliation flow

1. The GitHub Action keeps the committed monitor inventory synchronized with public routes.
2. Argo CD synchronizes the generated ConfigMap.
3. Reloader restarts AutoKuma when the mounted ConfigMap changes.
4. AutoKuma reads JSON monitor files from `/config/monitors`.
5. AutoKuma creates, updates, or deletes its managed monitors in Uptime Kuma.
6. Uptime Kuma performs the external HTTPS checks and stores heartbeats and response-time history.

Do not manually edit an AutoKuma-managed monitor in the Uptime Kuma UI. A later reconciliation may overwrite the change.

## Credentials

AutoKuma authenticates with the `uptime-kuma-credentials` Kubernetes Secret. The Doppler operator populates it from `home-dc-kubernetes` / `infra` using:

```text
UPTIME_KUMA_USERNAME
UPTIME_KUMA_PASSWORD
```

The initial Uptime Kuma administrator account must use the same credentials.

## Scope and limitations

The generator intentionally includes only repository-managed public HTTPS routes under `*.krapulax.dev`.

It excludes:

-   internal-only `*.krapulax.home` routes;
-   raw ClusterIP, node, or IP endpoints;
-   services without a public route;
-   non-Kubernetes DNS records not represented by Kubernetes HTTPRoutes.

An HTTP monitor validates the full user-visible path: public DNS, Cloudflare, the selected tunnel, Kubernetes routing, the service, the application response, and TLS certificate validity. It complements rather than replaces readiness probes, Prometheus, Grafana, Alertmanager, or Pulse.

Some authenticated applications may return redirects, 401, or 403 responses. Those services may need a dedicated health path or an explicit AutoKuma override in a future extension. The generated inventory currently uses the standard HTTP monitor defaults.

## Troubleshooting

### The workflow did not update the inventory

Check the `Generate AutoKuma Monitors` workflow run for the pull request. Confirm that:

-   the workflow is already present on the default branch;
-   the pull request branch belongs to this repository rather than a fork;
-   Actions has permission to write repository contents;
-   the changed route file matches the workflow path filters;
-   the generator completed without `yq` or YAML parsing errors;
-   branch protection permits the GitHub Actions bot to push to the pull-request branch.

The workflow deliberately does not push to pull requests originating from forks because their token is read-only.

For a local fallback, run:

```bash
task monitoring:generate-autokuma
```

### Monitor does not appear

Check that:

-   the generated hostname exists in `autokuma-monitors.yaml`;
-   Argo CD synchronized the `uptime-kuma-infra` application;
-   the ConfigMap exists in the `monitoring` namespace;
-   AutoKuma restarted after the ConfigMap changed;
-   AutoKuma can authenticate to Uptime Kuma;
-   AutoKuma logs contain no JSON parsing or API errors.

### Monitor is down but the pod is healthy

Verify in order:

1. public DNS target;
2. Cloudflare Tunnel connection and hostname ingress;
3. Gateway and HTTPRoute attachment;
4. Kubernetes Service and endpoints;
5. application response or authentication behaviour.

### Cloudflare error 1033

Error 1033 normally indicates that the hostname resolves to a tunnel that is not connected or does not own that hostname. Application services should resolve through the apps-cluster endpoint, while infra services should resolve through the infra-cluster endpoint.
