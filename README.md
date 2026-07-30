# 🏠 home-dc-kubernetes

![🏠 home-dc-kubernetes](docs/img/home-dc-kubernetes.svg)

This repository is the rebuild source of truth for the Kubernetes homelab. It
manages the Talos app cluster, the physical infra cluster, Argo CD GitOps, and
Kubernetes-specific OpenTofu stacks.

The rebuild flow is staged in the same spirit as the upstream
[`ajaykumar4/cluster-template`](https://github.com/ajaykumar4/cluster-template):
prepare hardware, prepare the workstation, render configuration, bootstrap
Talos, bootstrap Argo, then verify GitOps.

## 🎯 Target State

| Cluster       | Argo name       | Platform             | Role                              |
| ------------- | --------------- | -------------------- | --------------------------------- |
| App cluster   | `app-cluster`   | Talos VMs on Proxmox | Argo CD hub and general workloads |
| Infra cluster | `infra-cluster` | Physical Talos nodes | Core infra services and monitors  |

Argo CD runs on `app-cluster` and manages both clusters. The cluster-aware app
layout is:

```text
kubernetes/argo/apps/app-cluster/<namespace>/*.yaml
kubernetes/argo/apps/infra-cluster/<namespace>/*.yaml
kubernetes/apps/app-cluster/<namespace>/<app>/
kubernetes/apps/infra-cluster/<namespace>/<app>/
```

## 🛤️ Stage 0: Recovery Inputs

Before rebuilding, recover or recreate these local-only inputs. They must not be
committed:

```text
age.key
kubeconfig
.private/infra-cluster/kubeconfig
.private/infra-cluster/generated/
infra/terraform_*/*.auto.tfvars
infra/terraform_*/terraform.tfstate
```

For infra-cluster recovery, `.private/infra-cluster/generated/` is the physical
cluster identity bundle. Keep the whole directory, not only `talosconfig`, when
recovering existing infra nodes.

Also confirm access to:

-   Proxmox, if rebuilding the app-cluster VMs
-   Cloudflare account, DNS zone, and tunnel credentials
-   Doppler project `home-dc-kubernetes` with configs `apps` and `infra`
-   the legacy `project-homelab/dev_homelab` Doppler config while
    `CEPH_KEYRING` remains a template-render bootstrap input
-   GitHub deploy key or repository credentials for Argo CD
-   Ceph on Proxmox for the app-cluster `cephfs` storage class

If state files are unavailable, treat the rebuild as new infrastructure and plan
OpenTofu imports before applying.

## 🛤️ Stage 1: Workstation

Clone the repo outside iCloud-synced folders, then install the pinned tools:

```bash
git clone git@github.com:fabricesemti80/home-dc-kubernetes.git
cd home-dc-kubernetes
nix develop
task deps
```

Check required secrets and local config:

```bash
test -f age.key
test -f .sops.yaml
test -f kubernetes/apps/app-cluster/doppler-operator-system/doppler-operator/config/secret-apps.sops.yaml
test -f kubernetes/apps/infra-cluster/doppler-operator-system/doppler-operator-infra/config/secret-infra.sops.yaml
task secrets:validate-bootstrap
task --list
```

If using direnv, allow the repo-local age key export:

```bash
direnv allow .
echo "$SOPS_AGE_KEY_FILE"
```

Useful docs:

-   [docs/README.md](docs/README.md)
-   [docs/cluster/README.md](docs/cluster/README.md)
-   [docs/cluster/dual-cluster-management.md](docs/cluster/dual-cluster-management.md)
-   [docs/cluster/secret-strategy.md](docs/cluster/secret-strategy.md)

## 🏗️ Stage 2: Infrastructure

For VM-based app-cluster rebuilds, initialize and review OpenTofu first:

```bash
task tf:init
task tf:plan
```

These tasks read infrastructure credentials from `home-dc-kubernetes/infra`.
Cloudflare tunnel outputs are written back to `home-dc-kubernetes/apps` or
`home-dc-kubernetes/infra` according to the cluster that consumes them.

Apply only after the plan matches the intended rebuild:

```bash
task tf:apply
```

For physical Talos hosts, skip Proxmox provisioning and instead prepare Talos
boot media, static IPs, NIC MAC addresses, and install disks. The infra-cluster
physical flow is documented in [docs/INFRA_CLUSTER_BOOTSTRAP.md](docs/INFRA_CLUSTER_BOOTSTRAP.md).

Useful docs:

-   [docs/infrastructure/terraform.md](docs/infrastructure/terraform.md)
-   [talos/README.md](talos/README.md)
-   [talos/infra/README.md](talos/infra/README.md)

## ☸️ Stage 3: App Cluster Talos

Generate Talos machine config and bootstrap the app cluster:

```bash
task talos:app:generate-config
task talos:app:bootstrap
```

Do not run `task template:configure` as a routine rebuild step. It re-renders
repository templates and currently still needs bootstrap-only `CEPH_KEYRING`
from `project-homelab/dev_homelab`; use it only when intentionally regenerating
templated source files.

Compatibility aliases still exist:

```bash
task talos:genconfig
task talos:bootstrap
```

After bootstrap, verify local access:

```bash
kubectl --kubeconfig ./kubeconfig get nodes -o wide
talosctl --talosconfig talos/app/clusterconfig/talosconfig get members
```

## ☸️ Stage 4: App Cluster GitOps

Bootstrap the base apps and Argo CD app-of-apps:

```bash
task apps:bootstrap
task sync-argo-bootstrap
task reconcile
```

Before syncing, confirm both scoped Doppler operator token Secrets are present
in Git and decryptable:

```bash
task secrets:validate-bootstrap
```

Watch convergence:

```bash
kubectl get pods -A --watch
kubectl get applications.argoproj.io -n argo-system
```

The root Argo app should be `Synced` and `Healthy`:

```bash
kubectl get application apps -n argo-system
```

## ☸️ Stage 5: Infra Cluster

Build or recover the physical infra cluster using
[docs/INFRA_CLUSTER_BOOTSTRAP.md](docs/INFRA_CLUSTER_BOOTSTRAP.md), then register
it with the app-cluster Argo CD hub as `infra-cluster`.

Common checks:

```bash
task talos:infra:kubeconfig
task talos:infra:cilium
task talos:infra:verify
task clusters:status
```

Generate a Lens kubeconfig when both clusters are reachable:

```bash
task clusters:lens-kubeconfig
```

## 💾 Stage 6: Storage, DNS, and Public Access

Verify storage before restoring stateful workloads:

```bash
kubectl get storageclass
kubectl get pvc -A
kubectl get application ceph-csi -n argo-system
```

Verify public and internal routing:

```bash
kubectl get httproute -A
kubectl get dnsendpoint -A
kubectl get application cloudflare-dns cloudflare-tunnel cloudflare-tunnel-infra -n argo-system
```

Verify Doppler runtime secret sync after Argo converges:

```bash
kubectl -n doppler-operator-system get dopplersecret
kubectl --kubeconfig .private/infra-cluster/kubeconfig -n doppler-operator-system get dopplersecret
```

Useful docs:

-   [docs/storage/overview.md](docs/storage/overview.md)
-   [docs/cluster/domains.md](docs/cluster/domains.md)
-   [docs/monitoring/uptime-kuma-autokuma.md](docs/monitoring/uptime-kuma-autokuma.md)

## ✅ Stage 7: Final Validation

Run the repo checks and cluster checks:

```bash
task validate
task verify:cluster
task clusters:status
```

Expected state:

-   both Lens contexts exist: `app-cluster` and `infra-cluster`
-   Argo Applications are `Synced` and `Healthy`
-   `kubernetes/apps/app-cluster/...` apps target `app-cluster`
-   `kubernetes/apps/infra-cluster/...` apps target `infra-cluster`
-   no application manifests target `in-cluster`
-   no untracked duplicate `* 2` or `* 3` paths exist in `git status`

## ↩️ Rollback and Reset

For GitOps changes, revert the PR and reconcile Argo:

```bash
git revert <merge-commit>
git push
task reconcile
```

For a full app-cluster Talos reset, confirm every target node and disk first:

```bash
task talos:reset
```

This task is cluster-wide. For a single-node repair, use an explicit
node-scoped `talosctl` command or the manual infra-cluster wipe/apply flow in
[docs/INFRA_CLUSTER_BOOTSTRAP.md](docs/INFRA_CLUSTER_BOOTSTRAP.md).

Use destructive OpenTofu actions only after reviewing the reverse dependency
order:

```bash
task tf:destroy
```

Troubleshooting entry point: [docs/operations/troubleshooting.md](docs/operations/troubleshooting.md).
