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

### Talos VM disk capacity increase

Decision:

-   Increase every Talos VM disk defined in Terraform from `30GB` to `45GB`.
-   Apply the resize uniformly to active control-plane nodes and the powered-off worker rollback nodes so the inventory stays consistent.

Assumptions:

-   Proxmox can expand the existing VM disks in place without forcing VM recreation.
-   Talos and the guest OS will continue to boot normally after the virtual disk size increase.
-   The additional disk capacity is primarily to support cluster workloads and local state growth, including new persistent applications.

Validation checks:

-   `doppler run --project project-homelab --config dev_homelab --name-transformer tf-var -- tofu -chdir=terraform plan`
-   `doppler run --project project-homelab --config dev_homelab --name-transformer tf-var -- tofu -chdir=terraform apply`
-   `kubectl get nodes`
-   `talosctl --talosconfig talos/clusterconfig/talosconfig health`
-   `kubectl -n productivity get pods`

Rollback:

-   Do not attempt to shrink disks in place from Terraform; rollback is operational, not declarative.
-   If a node fails after expansion, recover it from Proxmox backup or rebuild it with the prior known-good configuration.

## Pending final user confirmation

-   Initial 5 application services to onboard after platform baseline.
-   RPO/RTO tier definitions for critical services.
