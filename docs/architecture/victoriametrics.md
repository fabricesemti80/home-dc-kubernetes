# VictoriaMetrics monitoring

**Decision date:** 2026-11-01. **Status:** work in progress; not deployed. This design supersedes Pulse monitoring, retired in PR #460. The planned end-to-end coverage and acceptance criteria are in [the monitoring plan](../plan/victoriametrics-monitoring.md). Do not merge or deploy this partial configuration as a complete replacement.

## Scope and security

The infra-cluster hosts the VictoriaMetrics operator and single-node metrics store, vmagent, vmalert, Alertmanager and Grafana. Grafana is exposed only through the internal `grafana.krapulax.home` HTTPRoute. This HTTP endpoint assumes the home network is trusted; Grafana requires authentication and public exposure is not configured. Its admin user and password are stored in `home-dc-kubernetes/infra` in Doppler as `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD`. Alertmanager syncs only `SLACK_WEBHOOK_MONITORING` into its own namespace-scoped Secret, mounts it as a file and sends resolved notifications. The notification route has not yet been exercised.

The PVE exporter is an independently reconciled app in infra-cluster. It uses the dedicated `prometheus@pve!victoriametrics` read-only, privilege-separated `PVEAuditor` token, maintained by the Ansible role in `home-dc-proxmox`. Doppler exposes the host project's `PVE_MONITORING_TOKEN_SECRET` to the infra config by cross-project reference; the operator's service identity was verified to resolve it. The token is mounted as a file, never baked into the chart or command line. The exporter validates `10.0.40.10:8006` against the independently acquired PVE CA. A certificate-authority replacement must be verified via a trusted host connection and updated in Git before it can be trusted by the exporter. See the host repository's `docs/monitoring-credentials.md` for token provisioning, expiry, rotation and revocation.

The separately reconciled PBS exporter uses `prometheus@pbs!victoriametrics`, an audit-only token provisioned by `home-dc-terraform`'s `pbs-monitoring-apply` task. Its token is referenced into `home-dc-kubernetes/infra` from Doppler and mounted as a file. PBS uses a self-signed certificate whose SAN contains `pbs.krapulax.home`, not its IP; the exporter pins the public certificate and maps that name to `10.0.40.20`. Verify a replacement certificate over trusted PVE access before updating the pinned public certificate in Git. The exporter was tested against PBS 4.2.8 with verified TLS. The certificate and ACLs must be rotated deliberately; see `home-dc-terraform/proxmox/README.md`.

## Coverage and deliberate gaps

-   Infra vmagent is configured to discover resources across namespaces, with `cluster=infra-cluster`. Kube-state-metrics and node-exporter provide initial node, workload and filesystem signals. Actual target health and Talos host mounts are not yet verified.
-   Kubelet, cAdvisor and resource scrapes are disabled because the node-serving certificates do not chain to the cluster CA. API-server proxying is not assumed to fix this. Do not use insecure TLS verification; restore these metrics only after establishing verified serving identities.
-   PVE host, VM and storage metrics and PBS availability, datastore capacity and snapshot timestamps were tested with isolated hardened exporters. SMART, ZFS pool health, PVE backup jobs and PBS task/GC/prune/sync outcomes are not yet covered.
-   App-cluster collection and authenticated, encrypted remote write are not yet implemented. The dashboard currently cannot represent both clusters.
-   QNAP telemetry is optional and not implemented. Uptime Kuma continues to own external website checks.
-   No live firing/resolved Slack notification, dashboard, storage capacity, backup restore or end-to-end runtime validation has yet been completed. Pulse's monitoring gap remains open.

## Storage and recovery

VictoriaMetrics uses a 20 GiB `local-path` PVC with 30-day retention. Its metric history is intentionally opted out of app-protect and can be lost with the worker; a retained local PV is not an offsite backup. Grafana has no persistent database: provisioned dashboards, datasource settings and admin credentials are reconstructed from Git and Doppler. UI-created dashboards, user accounts and other unprovisioned changes will not survive a restart. Alertmanager silence persistence is not configured; active silences can be lost on restart.

## Validation and lifecycle

Render the chart with `helm template --include-crds`, render both kustomizations, and validate custom resources against the rendered CRD schemas. The chart's mutable dashboard/rule download job and Helm pre-delete cleanup hook are disabled; CRDs require an explicit reviewed lifecycle and must not be removed while other VictoriaMetrics resources use them. Validate rules with `promtool` and Alertmanager config with `amtool`. After deployment verify all scrape targets and labels, the internal Grafana route, correct dashboard data, firing and resolved Slack delivery, resource use and retention. Exercise recovery without disrupting Backrest.

Rollback is to revert the relevant Argo Applications and manifests, preserving PVCs, Doppler secrets and shared CRDs until their ownership is reviewed. Do not delete the monitoring namespace or Uptime Kuma. A complete infra-cluster, NAS or power outage can also take down this monitoring stack; an independent external dead-man alert remains separate work.
