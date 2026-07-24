# Infra-cluster build and migration runbook

This runbook creates a small bare-metal Talos cluster for services that should remain available while the Proxmox-hosted application cluster is under maintenance.

## Target state

| Argo CD name | Platform | Role |
|---|---|---|
| `app-cluster` | Talos VMs on Proxmox | General workloads |
| `infra-cluster` | Two physical mini PCs | Pulse, Uptime Kuma, Technitium DNS |

Initial infra topology:

- mini PC 1: one Talos control-plane node; workloads may also run here if needed
- mini PC 2: one Talos worker node
- control-plane HA is **not** provided or expected
- a third control-plane node can be added later

A two-control-plane layout must not be used: etcd needs a majority, so two control-plane nodes do not provide useful failure tolerance.

## Network choice

Use VLAN 40 (`10.0.40.0/24`) unless there is a specific reason to isolate the cluster on VLAN 30. VLAN 40 already represents infrastructure and avoids making the core monitoring stack depend on routing between an application VLAN and the infrastructure it monitors.

Create DHCP reservations before installation. Example values used below:

```text
infra-cp-01    10.0.40.31
infra-wk-01    10.0.40.32
```

Replace these addresses everywhere if different reservations are selected. The nodes need working DNS, NTP, internet access for images, and routed access to the app cluster and monitored devices.

## Required workstation tools

Install current stable versions of:

- `talosctl`
- `kubectl`
- `helm`
- `cilium`
- `argocd`

Create a working directory:

```bash
mkdir -p ~/clusters/infra-cluster
cd ~/clusters/infra-cluster
```

---

# Phase 0: rename the existing Argo CD cluster before merging

Complete this phase **before merging this PR**. The manifests in this PR target `app-cluster`; merging before the rename would temporarily leave the Applications with an unknown destination.

Log in to the existing Argo CD instance and inspect the current entry:

```bash
argocd cluster list
```

Rename the local cluster:

```bash
argocd cluster set in-cluster --name app-cluster
```

If the CLI cannot rename the special local-cluster entry, use the Argo CD UI:

1. Open **Settings → Clusters**.
2. Open `in-cluster`.
3. Edit its name to `app-cluster`.
4. Save and verify with `argocd cluster list`.

Expected result:

```text
NAME         SERVER
app-cluster  https://kubernetes.default.svc
```

Do not proceed until existing Applications remain healthy when addressed through `app-cluster`.

After the rename is confirmed, merge this PR and verify that Argo CD reconciles the renamed Application destinations successfully.

---

# Phase 1: boot Talos maintenance mode on both mini PCs

1. Download the current stable Talos `metal-amd64.iso` from the Talos release or Image Factory page.
2. Write it to a USB drive.
3. Boot each mini PC from USB in UEFI mode.
4. Disable Secure Boot unless a Talos Secure Boot image has deliberately been prepared.
5. Leave each node at the Talos maintenance-mode console.
6. Confirm the DHCP reservations were assigned.

From the workstation, verify each machine responds:

```bash
talosctl get disks --insecure --nodes 10.0.40.31
talosctl get disks --insecure --nodes 10.0.40.32
```

Record the installation disk shown by both machines. The examples below assume `/dev/nvme0n1`; change it if the hardware reports a different device.

---

# Phase 2: generate Talos configuration

Cilium will provide the CNI and replace kube-proxy. Create `cilium-patch.yaml`:

```yaml
cluster:
  network:
    cni:
      name: none
  proxy:
    disabled: true
```

Create a machine patch that selects the installation disk and permits scheduling on the single control-plane node. This allows core workloads to continue on the control-plane node if the worker is unavailable.

Create `controlplane-patch.yaml`:

```yaml
machine:
  install:
    disk: /dev/nvme0n1
cluster:
  allowSchedulingOnControlPlanes: true
```

Create `worker-patch.yaml`:

```yaml
machine:
  install:
    disk: /dev/nvme0n1
```

Generate the cluster configuration:

```bash
talosctl gen config infra-cluster https://10.0.40.31:6443 \
  --output-dir ./generated \
  --config-patch @cilium-patch.yaml \
  --config-patch-control-plane @controlplane-patch.yaml \
  --config-patch-worker @worker-patch.yaml
```

The generated secrets are the identity of this cluster. Keep the directory private and backed up; do not commit it.

Optionally inspect the generated files before applying them:

```bash
talosctl validate --config ./generated/controlplane.yaml --mode metal
talosctl validate --config ./generated/worker.yaml --mode metal
```

---

# Phase 3: install Talos to the physical nodes

Apply the control-plane configuration:

```bash
talosctl apply-config --insecure \
  --nodes 10.0.40.31 \
  --file ./generated/controlplane.yaml
```

Apply the worker configuration:

```bash
talosctl apply-config --insecure \
  --nodes 10.0.40.32 \
  --file ./generated/worker.yaml
```

Remove the USB media when the machines restart and ensure they boot from their internal disks.

Configure `talosctl` to use the new cluster credentials:

```bash
export TALOSCONFIG=$PWD/generated/talosconfig
talosctl config endpoint 10.0.40.31
talosctl config node 10.0.40.31
```

Wait for the control-plane node to become reachable:

```bash
talosctl version
talosctl health --wait-timeout 10m
```

The health command may wait for CNI-related checks until Cilium is installed.

---

# Phase 4: bootstrap Kubernetes and install Cilium

Bootstrap etcd exactly once:

```bash
talosctl bootstrap --nodes 10.0.40.31
```

Retrieve kubeconfig and give the context an explicit name:

```bash
talosctl kubeconfig ./kubeconfig --nodes 10.0.40.31
kubectl --kubeconfig ./kubeconfig config rename-context admin@infra-cluster infra-cluster
export KUBECONFIG=$PWD/kubeconfig
```

Confirm the API responds. Nodes may remain `NotReady` until Cilium is installed:

```bash
kubectl get nodes -o wide
```

Install Cilium using the Talos-compatible settings. Keep the chart version aligned with the version used by the repository/app cluster rather than blindly using `latest`.

```bash
helm repo add cilium https://helm.cilium.io/
helm repo update

CILIUM_VERSION='<repository-cilium-version>'

helm upgrade --install cilium cilium/cilium \
  --version "$CILIUM_VERSION" \
  --namespace kube-system \
  --set operator.replicas=1 \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true \
  --set securityContext.capabilities.ciliumAgent='{CHOWN,KILL,NET_ADMIN,NET_RAW,IPC_LOCK,SYS_ADMIN,SYS_RESOURCE,DAC_OVERRIDE,FOWNER,SETGID,SETUID}' \
  --set securityContext.capabilities.cleanCiliumState='{NET_ADMIN,SYS_ADMIN,SYS_RESOURCE}' \
  --set cgroup.autoMount.enabled=false \
  --set cgroup.hostRoot=/sys/fs/cgroup \
  --set k8sServiceHost=localhost \
  --set k8sServicePort=7445 \
  --set bpf.hostLegacyRouting=true
```

Verify networking and node readiness:

```bash
cilium status --wait
cilium connectivity test
kubectl get nodes -o wide
kubectl get pods -A
```

Expected node roles:

```text
infra-cp-01   control-plane   Ready
infra-wk-01   <none>          Ready
```

The worker does not require a cosmetic worker-role label, but one may be added:

```bash
kubectl label node infra-wk-01 node-role.kubernetes.io/worker=''
```

---

# Phase 5: register infra-cluster in the existing Argo CD hub

Argo CD remains hosted on `app-cluster` and manages both clusters.

First confirm the kubeconfig context:

```bash
kubectl --kubeconfig ./kubeconfig config get-contexts
```

Register the exact context shown by that command:

```bash
argocd cluster add infra-cluster \
  --kubeconfig ./kubeconfig \
  --name infra-cluster
```

Argo CD creates its management ServiceAccount and credentials on the target cluster. Review and accept the privilege prompt.

Verify registration:

```bash
argocd cluster list
argocd cluster get infra-cluster
```

Expected managed clusters:

```text
app-cluster
infra-cluster
```

Do not merge any Application targeting `infra-cluster` until this registration is healthy.

---

# Phase 6: storage and service placement decisions

The initial infra cluster must not depend on storage hosted inside `app-cluster` or on the Proxmox nodes it is intended to monitor.

Before deploying Pulse, Uptime Kuma, or Technitium, choose one of these storage patterns:

1. **Local persistent volumes on the physical nodes** — simplest, but tied to one node.
2. **External NAS-backed NFS/iSCSI** — preferred when the NAS remains online during Proxmox maintenance.
3. **Replicated storage across the two mini PCs** — possible, but two-node storage systems have quorum and split-brain trade-offs and add complexity.

For this small core cluster, external NAS-backed storage or explicitly node-pinned local storage is preferable to introducing Ceph.

Technitium DNS needs special planning:

- expose DNS on stable LAN addresses using the existing load-balancer approach or dedicated node addresses
- do not switch DHCP clients to the new resolver until the deployment is tested
- retain the existing DNS server as a rollback path during migration
- consider running a second Technitium instance outside this cluster if DNS availability must survive loss of the control-plane node

---

# Phase 7: deploy the core applications through a follow-up PR

After `infra-cluster` is registered and storage is ready, add separate Argo CD Applications targeting:

```yaml
destination:
  name: infra-cluster
```

Deploy in this order:

1. storage prerequisites and any required secret operator
2. Pulse
3. Uptime Kuma
4. Technitium DNS

Do not move the existing `technitium-dns` Application blindly: the current repository object is an ExternalDNS webhook integration, not necessarily the Technitium DNS server itself. Create or migrate the actual DNS-server workload deliberately and keep app-cluster-specific integrations separate where required.

Validate each application before proceeding:

```bash
argocd app get <application-name>
argocd app sync <application-name>
kubectl --context infra-cluster get pods -A
```

---

# Phase 8: maintenance test

Prove that the design meets its purpose:

1. Confirm Pulse, Uptime Kuma, and Technitium are healthy on `infra-cluster`.
2. Shut down or pause the app-cluster VMs during a maintenance window.
3. Confirm the infra services remain reachable.
4. Confirm they correctly report the app cluster as unavailable.
5. Restore the app cluster and confirm recovery is detected.

## Recovery notes

Back up these items outside both clusters:

- `generated/talosconfig`
- Talos machine configuration/secrets
- `infra-cluster` kubeconfig
- application data for Pulse, Uptime Kuma, and Technitium
- the Argo CD registration and deployment instructions in this repository

Because the initial cluster has one control-plane node, losing `infra-cp-01` makes the Kubernetes API unavailable. Existing workloads on the worker may continue running, but scheduling and reconciliation stop until the control-plane node is restored. This is an accepted initial limitation.
