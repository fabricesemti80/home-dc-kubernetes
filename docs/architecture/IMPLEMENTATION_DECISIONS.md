# Implementation Decisions

## Confirmed

-   Network: VLAN30 (`10.0.30.0/24`).
-   Access model: Tailscale for both node-level and subnet routing scenarios.
-   CNI: Cilium (target configuration enables kube-proxy replacement).
-   Ingress: the migrated cluster currently uses Envoy Gateway; Traefik remains only a historical design idea.
-   Storage: the migrated cluster currently uses Ceph CSI; Longhorn remains optional future work rather than current state.
-   GitOps: Argo CD.
-   Media service: remains on NAS Docker initially, routed via cluster ingress as external upstream.
-   Cluster relocation: keep the old `home-argo-cluster-2025` repo intact, but operate the migrated cluster directly from the `project-homelab` repo root with local state copied over.
-   Worker handling during cutover: keep worker VMs represented in Terraform state, but allow them to remain provisioned and powered off by using per-node `started = false`.

## Active Decisions

### Multi-replica control-plane and edge services

Decision:

-   Run `cloudflare-tunnel`, `cert-manager`, and the `cilium` operator with 2 replicas to reduce outage risk during node failure, pod eviction, and rolling updates.
-   Defer scaling `cloudflare-dns` until the deployed `external-dns` version supports leader election in this cluster path.

Assumptions:

-   The active Talos cluster has enough schedulable capacity across control-plane nodes to carry a second replica for these lightweight services.
-   `cloudflared` can maintain multiple concurrent connectors for the same tunnel without requiring route changes.
-   `external-dns` should only be scaled after leader election is available so only one replica writes DNS changes at a time.

Validation checks:

-   `kubectl get deploy -n network cloudflare-tunnel cloudflare-dns`
-   `kubectl get deploy -n cert-manager cert-manager`
-   `kubectl get deploy -n kube-system cilium-operator`
-   `kubectl get pods -n network -l app.kubernetes.io/name=cloudflare-tunnel -o wide`
-   `kubectl rollout status deploy/cloudflare-tunnel -n network`
-   `kubectl rollout status deploy/cert-manager -n cert-manager`
-   `kubectl rollout status deploy/cilium-operator -n kube-system`

Rollback:

-   Reduce the replica counts back to `1` for the three scaled workloads if resource pressure, chart behavior, or failover behavior is not acceptable.
-   Keep `cloudflare-dns` at a single replica until its deployed version gains a supported leader-election path.

### Productivity namespace and Linkwarden deployment

Decision:

-   Add a dedicated `productivity` namespace and deploy Linkwarden there behind Argo CD.
-   Keep both Linkwarden archive storage and its PostgreSQL data on CephFS-backed PVCs so the app state stays inside the cluster storage layer already used elsewhere in the repo.
-   Source runtime secrets from Doppler via the existing operator pattern instead of committing new encrypted application secrets into Git.
-   Source the Linkwarden `NEXTAUTH_URL` from the same Doppler-managed secret so the external callback URL can vary by environment without another manifest edit.

Assumptions:

-   `linkwarden.krapulax.dev` will be the initial external hostname for the service.
-   A single Linkwarden replica backed by a single PostgreSQL instance is acceptable for the first rollout.
-   The Doppler `project-homelab/dev_homelab` config is the correct source of truth for Linkwarden bootstrap secrets.
-   The Doppler config will be populated with `NEXTAUTH_URL=https://linkwarden.krapulax.dev` before the Kubernetes workload change is synced.

Validation checks:

-   `doppler secrets get NEXTAUTH_URL --project project-homelab --config dev_homelab`
-   `kubectl get dopplersecret -n doppler-operator-system linkwarden-secrets -o yaml`
-   `kubectl get secret -n productivity linkwarden-secrets -o jsonpath='{.data.NEXTAUTH_URL}' | base64 -d`
-   `kubectl get application -n argo-system linkwarden`
-   `kubectl get deploy -n productivity linkwarden`
-   `kubectl get statefulset -n productivity linkwarden-database`
-   `kubectl get pvc -n productivity`
-   `kubectl rollout status deploy/linkwarden -n productivity`
-   `kubectl rollout status statefulset/linkwarden-database -n productivity`
-   `kubectl get httproute -n productivity linkwarden`
-   `kubectl get deploy -n productivity linkwarden -o jsonpath='{.spec.template.spec.containers[0].envFrom[0].secretRef.name}'`
-   `kubectl logs -n productivity deploy/linkwarden --tail=100`

Rollback:

-   Restore the literal `NEXTAUTH_URL` entry in the Linkwarden values file if the Doppler-managed key is missing or incorrect.
-   Delete the Argo CD `linkwarden` application and the `productivity` namespace resources if the rollout is not acceptable.
-   Remove the Doppler-managed Linkwarden secrets after the application is decommissioned.
-   Keep the CephFS PVCs intact until data export or cleanup is explicitly confirmed.

### Monitoring Slack notifications via Alertmanager

Decision:

-   Add a basic Alertmanager Slack receiver for the monitoring stack.
-   Source the Slack incoming webhook from Doppler and mount it into the Alertmanager pods as a Kubernetes secret file instead of embedding it in the Alertmanager config.

Assumptions:

-   The Doppler `project-homelab/dev_homelab` config is the correct source of truth for `SLACK_WEBHOOK_MONITORING`.
-   The intended Slack destination is the `#monitoring` channel.
-   `https://alertmanager.krapulax.dev` is the intended external Alertmanager address.
-   The initial routing policy should stay simple: send normal alerts to Slack and continue discarding the default `Watchdog` alert.

Validation checks:

-   `doppler secrets get SLACK_WEBHOOK_MONITORING --project project-homelab --config dev_homelab`
-   `kubectl get dopplersecret -n doppler-operator-system alertmanager-slack-webhook -o yaml`
-   `kubectl get secret -n monitoring alertmanager-slack-webhook -o jsonpath='{.data.SLACK_WEBHOOK_MONITORING}' | base64 -d`
-   `kubectl get application -n argo-system kube-prometheus-stack`
-   `kubectl get alertmanager -n monitoring kube-prometheus-stack-alertmanager -o yaml`
-   `kubectl get httproute -n monitoring alertmanager`
-   `kubectl rollout status statefulset/alertmanager-kube-prometheus-stack-alertmanager -n monitoring`
-   `kubectl logs -n monitoring statefulset/alertmanager-kube-prometheus-stack-alertmanager --tail=100`

Rollback:

-   Remove the Slack route and receiver from the kube-prometheus-stack values file if notifications behave unexpectedly.
-   Remove the Doppler-managed `alertmanager-slack-webhook` secret if Alertmanager Slack notifications are rolled back entirely.

### Homepage dashboard deployment

Decision:

-   Add Homepage as an additional dashboard application in the `web` namespace.
-   Expose it at `https://homepage.krapulax.dev`.
-   Use Homepage's in-cluster Kubernetes integration with Gateway API discovery enabled so externally routed services can be auto-discovered from annotated `HTTPRoute` objects.
-   Use Homepage layout ordering to keep `Media` after the smaller operational groups so the busiest section does not dominate the top of the page.
-   Expose Prometheus directly at `https://prometheus.krapulax.dev` so the Prometheus expression browser is reachable without going through Grafana.
-   Keep the initial Homepage deployment read-only: use discovery metadata and Kubernetes cluster widgets first, and only add API-backed widgets when their credentials are explicitly stored in Doppler.

Assumptions:

-   `homepage.krapulax.dev` is the intended external hostname for the new dashboard.
-   The current cluster should continue to use Gateway API `HTTPRoute` objects rather than `Ingress` for Homepage service discovery.
-   Homepage can rely on a dedicated service account with read access to namespaces, pods, nodes, ingresses, gateways, httproutes, and metrics APIs.
-   Any future Homepage widget credential or API token should be sourced from Doppler rather than committed in config files.

Validation checks:

-   `kubectl get application -n argo-system homepage`
-   `kubectl get deploy -n web homepage`
-   `kubectl get serviceaccount -n web homepage`
-   `kubectl get clusterrole homepage -o yaml`
-   `kubectl get httproute -n web homepage -o yaml`
-   `kubectl get httproute -n monitoring prometheus -o yaml`
-   `kubectl rollout status deploy/homepage -n web`
-   `kubectl logs -n web deploy/homepage --tail=100`
-   `kubectl get httproute -A -o yaml | rg 'gethomepage.dev/'`

Rollback:

-   Delete the Argo CD `homepage` application if the rollout is not acceptable.
-   Remove Homepage-specific `gethomepage.dev/*` annotations from `HTTPRoute` objects if discovery behavior is not acceptable.
-   Remove any Doppler-managed Homepage widget secrets if API-backed widgets are rolled back.

### Termix internal admin access

Decision:

-   Deploy Termix into the existing `productivity` namespace.
-   Expose Termix only through the internal Envoy Gateway at `http://termix.krapulax.home` and `https://termix.krapulax.home`.
-   Do not add an external `HTTPRoute`, Cloudflare DNS record, or public tunnel route for the initial rollout.
-   Store Termix data on a CephFS-backed PVC mounted at `/app/data`.
-   Pin the Termix image to `ghcr.io/lukegus/termix:release-2.3.1` instead of using `latest`.
-   Defer `guacd` unless RDP, VNC, or Telnet support is explicitly needed for the first rollout.
-   Start without OIDC or Doppler secrets for the Tailscale-only initial rollout; let Termix manage its generated database, JWT, and internal auth secrets in the persistent data directory.

Assumptions:

-   Termix is a user-facing administrative/productivity tool, not cluster platform infrastructure, so `productivity` is the least surprising namespace.
-   `termix.krapulax.home` should CNAME to the internal Kubernetes gateway record.
-   Internal Envoy routing supports the WebSocket upgrade behavior Termix needs for browser terminal sessions.
-   A single replica is acceptable because Termix uses local SQLite-backed state under the data directory.
-   The Termix PVC is sensitive because it can contain saved hosts, encrypted database files, generated encryption material, SSH metadata, and exported connection data.

Validation checks:

-   `doppler secrets get TERMIX_OIDC_CLIENT_ID --project project-homelab --config dev_homelab` if OIDC is enabled
-   `kubectl get application -n argo-system termix`
-   `kubectl get deploy -n productivity termix`
-   `kubectl get pvc -n productivity | rg termix`
-   `kubectl get httproute -n productivity termix-internal -o yaml`
-   `kubectl rollout status deploy/termix -n productivity`
-   `kubectl logs -n productivity deploy/termix --tail=100`
-   `dig +short termix.krapulax.home`
-   Open `http://termix.krapulax.home`
-   Open `https://termix.krapulax.home`
-   Confirm SSH terminal sessions work through the internal route.

Rollback:

-   Remove the Termix Argo CD application and internal `HTTPRoute`.
-   Remove the `termix.krapulax.home` local DNS record if it was added.
-   Remove the Termix DopplerSecret manifest if OIDC secrets were synced.
-   Keep the Termix PVC until saved credentials, generated encryption material, and any exported host data have been backed up or intentionally destroyed.

### Planka productivity deployment

Decision:

-   Deploy Planka into the existing `productivity` namespace.
-   Expose Planka externally at `https://planka.krapulax.dev` and internally at `https://planka.krapulax.home`.
-   Store Planka attachments/app data and PostgreSQL data on CephFS-backed PVCs.
-   Source Planka runtime and bootstrap admin secrets from Doppler through the existing Doppler operator pattern.
-   Model the internal `planka.krapulax.home` CNAME in `infra/terraform_localdns/`.
-   Model the Cloudflare DNS record and Access app for `planka.krapulax.dev` in `infra/terraform_cloudflare/`, using the same bypass policy pattern as Linkwarden.

Assumptions:

-   `planka.krapulax.dev` is the canonical `BASE_URL`.
-   Planka's own authentication is the primary public access control for the initial rollout.
-   A single Planka replica and a single PostgreSQL instance are acceptable for the first deployment.
-   The Doppler `project-homelab/dev_homelab` config is the correct source of truth for Planka secrets.

Validation checks:

-   `doppler secrets get PLANKA_SECRET_KEY --project project-homelab --config dev_homelab`
-   `kubectl get dopplersecret -n doppler-operator-system planka-secrets -o yaml`
-   `kubectl get secret -n productivity planka-secrets`
-   `kubectl get application -n argo-system planka`
-   `kubectl get deploy,statefulset,pvc -n productivity | rg planka`
-   `kubectl rollout status deploy/planka -n productivity`
-   `kubectl rollout status statefulset/planka-database -n productivity`
-   `kubectl get httproute -n productivity planka planka-internal -o yaml`
-   `task tf:cloudflare:plan`
-   Open `https://planka.krapulax.dev`
-   Open `https://planka.krapulax.home`

Rollback:

-   Remove the Planka Argo CD application and its route resources if the rollout is not acceptable.
-   Remove Planka Terraform DNS/Access entries if they were applied.
-   Keep the Planka PVCs until data export or deletion is explicitly confirmed.
-   Remove Planka Doppler secrets only after the app and data are decommissioned.

### Talos VM disk capacity increase

Decision:

-   Increase every Talos VM disk defined in Terraform from `30GB` to `45GB`.
-   Apply the resize uniformly to active control-plane nodes and the powered-off worker rollback nodes so the inventory stays consistent.

Assumptions:

-   Proxmox can expand the existing VM disks in place without forcing VM recreation.
-   Talos and the guest OS will continue to boot normally after the virtual disk size increase.
-   The additional disk capacity is primarily to support cluster workloads and local state growth, including new persistent applications.

Validation checks:

-   `task tf:proxmox:plan`
-   `task tf:proxmox:apply`
-   `kubectl get nodes`
-   `talosctl --talosconfig talos/clusterconfig/talosconfig health`
-   `kubectl -n productivity get pods`

Rollback:

-   Do not attempt to shrink disks in place from Terraform; rollback is operational, not declarative.
-   If a node fails after expansion, recover it from Proxmox backup or rebuild it with the prior known-good configuration.

### Talos worker VM boot policy

Decision:

-   Keep Talos worker VMs represented in the Proxmox/OpenTofu inventory but default their Proxmox `on_boot` policy to `false`.
-   Default control-plane nodes to `on_boot = true` so the active cluster comes back after a Proxmox host reboot.
-   Allow a per-node `on_boot` override for exceptional cases, while retaining `controller` as the default boot-policy signal.
-   Continue using per-node `started = false` for worker power state so workers can remain powered off without being destroyed.

Assumptions:

-   The current steady state is the three control-plane nodes only.
-   Worker VMs are retained as rollback capacity and should not automatically start with their Proxmox hosts.
-   Proxmox `on_boot` changes are in-place VM metadata changes and do not recreate VMs.

Validation checks:

-   `task tf:proxmox:plan`
-   Confirm the plan shows no `on_boot = false -> true` updates for `k8s-wrkr-*`.
-   Confirm Proxmox worker VM Options keep `Start at boot` disabled.

Rollback:

-   Set `on_boot = true` on selected worker entries in `infra/terraform_proxmox/nodes.auto.tfvars` if workers should start with Proxmox again.
-   Set worker `started = true` only when intentionally reintroducing them as active cluster capacity.

### Kubernetes local DNS in UniFi

Decision:

-   Move Kubernetes-required local DNS records from the standalone UniFi Terraform repo into `infra/terraform_localdns/`.
-   Manage only the Kubernetes ingress records in this repo: `kubernetes.krapulax.home` plus internal `krapulax.home` CNAMEs for routable cluster apps.
-   Add internal HTTPRoutes for media apps that already have an external HTTPRoute so LAN clients can use the internal Envoy Gateway without Cloudflare.
-   Leave swarm, Wi-Fi, device, network, port-profile, and non-Kubernetes records in the existing UniFi repo for now.
-   Replace the old 1Password Terraform provider flow with Doppler-injected OpenTofu variables.

Assumptions:

-   `kubernetes.krapulax.home` should continue to point at `10.0.40.102`.
-   `photos.krapulax.home`, `jellyfin.krapulax.home`, `requests.krapulax.home`, `prowlarr.krapulax.home`, `qbittorrent.krapulax.home`, `radarr.krapulax.home`, `sabnzbd.krapulax.home`, `sonarr.krapulax.home`, `tdarr.krapulax.home`, `termix.krapulax.home`, and `planka.krapulax.home` should CNAME to `kubernetes.krapulax.home`.
-   Recyclarr is not exposed through a local HTTPRoute because it has no existing external HTTPRoute or user-facing service in the current media namespace config.
-   Doppler `project-homelab/dev_homelab` will provide `UNIFI_USERNAME`, `UNIFI_PASSWORD`, `UNIFI_API_URL`, and optionally `UNIFI_ALLOW_INSECURE`.

Validation checks:

-   `task tf:localdns:init`
-   `task tf:localdns:plan`
-   `kubectl get httproute -n media`
-   `dig +short kubernetes.krapulax.home`
-   `dig +short photos.krapulax.home`
-   `dig +short jellyfin.krapulax.home`
-   `dig +short requests.krapulax.home`
-   `dig +short prowlarr.krapulax.home`
-   `dig +short qbittorrent.krapulax.home`
-   `dig +short radarr.krapulax.home`
-   `dig +short sabnzbd.krapulax.home`
-   `dig +short sonarr.krapulax.home`
-   `dig +short tdarr.krapulax.home`
-   `dig +short termix.krapulax.home`
-   `dig +short planka.krapulax.home`

Rollback:

-   Remove the added internal HTTPRoutes from the media app config kustomizations if LAN routing through Envoy is not acceptable.
-   Remove the localdns resources from `infra/terraform_localdns/` and return ownership to `/Users/fs/Documents/repositories/terraform/homelab-terraform-unifi` only if UniFi DNS ownership needs to move back.
-   If state was moved, move the relevant `unifi_dns_record.*` addresses back before applying the old UniFi repo.

## Pending final user confirmation

-   Initial 5 application services to onboard after platform baseline.
-   RPO/RTO tier definitions for critical services.
