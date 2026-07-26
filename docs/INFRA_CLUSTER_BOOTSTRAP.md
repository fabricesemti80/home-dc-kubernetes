# Infra-cluster build and migration runbook

This runbook creates a small bare-metal Talos cluster for services that should remain available while the Proxmox-hosted application cluster is under maintenance.

## Target state

| Argo CD name    | Platform              | Role                               |
| --------------- | --------------------- | ---------------------------------- |
| `app-cluster`   | Talos VMs on Proxmox  | General workloads                  |
| `infra-cluster` | Two physical mini PCs | Pulse, Uptime Kuma, Technitium DNS |

Initial infra topology:

-   mini PC 1: one Talos control-plane node; workloads may also run here if needed
-   mini PC 2: one Talos worker node
-   control-plane HA is **not** provided or expected
-   a third control-plane node can be added later

A two-control-plane layout must not be used: etcd needs a majority, so two control-plane nodes do not provide useful failure tolerance.

## Network choice

Use VLAN 40 (`10.0.40.0/24`) unless there is a specific reason to isolate the cluster on VLAN 30. VLAN 40 already represents infrastructure and avoids making the core monitoring stack depend on routing between an application VLAN and the infrastructure it monitors.

Use static node addresses in the Talos machine configs. DHCP may still be useful briefly while the machines are booted from the Talos ISO in maintenance mode, but the installed cluster should not depend on DHCP for node identity.

Example values used below:

```text
infra-cp-01    10.0.40.31/24
infra-wk-01    10.0.40.32/24
gateway        10.0.40.1
nameservers    1.1.1.1, 1.0.0.1
```

Replace these addresses everywhere if different static addresses are selected. The nodes need working DNS, NTP, internet access for images, and routed access to the app cluster and monitored devices.

Before reinstalling, record for each mini PC:

```text
hostname       target IP      primary NIC MAC        install disk
infra-cp-01    10.0.40.31     <cp-primary-mac>       /dev/nvme0n1
infra-wk-01    10.0.40.32     <worker-primary-mac>   /dev/nvme0n1
```

Prefer static DHCP reservations as a backup if the router supports them, but do not rely on reservations alone. The Talos configs below set `dhcp: false` and bind each address to the selected NIC MAC address.

## Required workstation tools

Install current stable versions of:

-   `talosctl`
-   `kubectl`
-   `helm`
-   `cilium`
-   `argocd`

Create a working directory:

```bash
mkdir -p ~/clusters/infra-cluster
cd ~/clusters/infra-cluster
```

---

# Phase 0: prepare the app-cluster Argo CD CLI

Complete this phase **before merging this PR**. The manifests in this PR target `app-cluster`; merging before the live Argo CD cluster is renamed can leave Applications with an unknown destination.

Use the repository checkout that will reconcile the app cluster:

```bash
cd /Users/fs/orca/workspaces/home-dc-kubernetes/kittiwake
cp /Users/fs/Documents/repositories/infrastructure/home-dc-kubernetes/kubeconfig ./kubeconfig
```

Create a kubeconfig context that points at the Argo CD namespace. `argocd --core` reads Argo CD resources from the current kube context namespace, so the namespace must be `argo-system`.

```bash
kubectl config set-context argocd \
  --cluster=kubernetes \
  --user=admin@kubernetes \
  --namespace=argo-system
kubectl config use-context argocd
```

If direnv is available, keep the local credentials wired on directory entry:

```bash
cat > .envrc <<'EOF'
export KUBECONFIG="$PWD/kubeconfig"
export TALOSCONFIG="$PWD/talos/app/clusterconfig/talosconfig"
export SOPS_AGE_KEY_FILE="$PWD/age.key"
EOF
direnv allow .
```

Verify local access:

```bash
kubectl get nodes
argocd cluster list --core
```

Expected current Argo CD cluster before the rename:

```text
SERVER                          NAME        STATUS
https://kubernetes.default.svc  in-cluster  Successful
```

If the cluster is already named `app-cluster`, leave it as-is and continue with the pre-merge checks below.

---

# Phase 1: rename the existing Argo CD cluster before merging

Rename the local cluster from `in-cluster` to `app-cluster`:

```bash
argocd cluster set in-cluster --name app-cluster --core
argocd cluster list --core
```

Expected result:

```text
SERVER                          NAME         STATUS
https://kubernetes.default.svc  app-cluster  Successful
```

If the CLI cannot rename the special local-cluster entry, use the Argo CD UI instead:

1. Open **Settings → Clusters**.
2. Open `in-cluster`.
3. Edit its name to `app-cluster`.
4. Save and verify with `argocd cluster list`.

Do not proceed until the live Argo CD cluster entry is named `app-cluster`.

At this point the live Applications may still show `CLUSTER` as `in-cluster` until this PR is merged and reconciled. That is acceptable if they remain `Synced` and `Healthy`; do not force-sync Applications just to change the displayed destination before the manifest change exists on `main`.

Merge this PR only after the rename is done. Then pull `main` and verify that every named destination has moved off `in-cluster`:

```bash
git checkout main
git pull
rg "name: in-cluster" kubernetes/argo kubernetes/components templates/config/kubernetes/components
argocd app get apps --core
argocd app list --core
```

Expected checks:

-   `rg "name: in-cluster" ...` returns no matches.
-   `argocd app list --core` shows Applications targeting `app-cluster`.
-   `argocd cluster list --core` still shows `app-cluster` as `Successful`.

Rollback before adding `infra-cluster`:

```bash
argocd cluster set app-cluster --name in-cluster --core
```

Only use the rollback if the PR is not merged or is reverted. Once manifests target `app-cluster`, keep the live Argo CD cluster name as `app-cluster`.

---

# Phase 2: boot the first mini PC into Talos maintenance mode

Do one node at a time. Start with the node that will become `infra-cp-01`.

1. Download the current stable Talos `metal-amd64.iso` from the Talos release or Image Factory page.
2. Write it to a USB drive.
3. Boot the mini PC from USB in UEFI mode.
4. Disable Secure Boot unless a Talos Secure Boot image has deliberately been prepared.
5. Stop at the Talos maintenance-mode screen. Do not install from the screen.
6. Note the IP address shown on the Talos screen. This is only the temporary maintenance address.

From the workstation, set a variable for that temporary address:

```bash
NODE=10.0.40.31
```

If the Talos screen shows a different temporary address, use that value instead:

```bash
NODE=<temporary-address-shown-on-screen>
```

Confirm the node answers the maintenance API:

```bash
talosctl version --insecure --nodes "$NODE"
```

Discover disks and network links:

```bash
talosctl get disks --insecure --nodes "$NODE"
talosctl get links --insecure --nodes "$NODE"
```

Record:

```text
role            hostname       temporary IP     target IP      primary NIC MAC        install disk
control-plane   infra-cp-01    <screen-ip>      10.0.40.31     <cp-primary-mac>       /dev/nvme0n1
```

Pick the normal LAN NIC MAC address, not loopback, bridge, VLAN, or virtual interfaces. The install disk is usually the internal SSD, for example `/dev/nvme0n1`; verify it from size/model before wiping.

For `talosctl wipe disk`, use the disk name without `/dev/`. Example:

```text
machine config install disk    talosctl wipe disk argument
/dev/nvme0n1                   nvme0n1
/dev/sda                       sda
```

Repeat this phase for the worker after the control-plane machine config has been prepared:

```text
role     hostname       temporary IP     target IP      primary NIC MAC        install disk
worker   infra-wk-01    <screen-ip>      10.0.40.32     <worker-primary-mac>   /dev/nvme0n1
```

If DHCP is available, use it only to reach maintenance mode and discover hardware details:

```bash
talosctl get disks --insecure --nodes 10.0.40.31
talosctl get disks --insecure --nodes 10.0.40.32
talosctl get links --insecure --nodes 10.0.40.31
talosctl get links --insecure --nodes 10.0.40.32
```

Record the primary NIC MAC address and installation disk shown by both machines. The examples below assume `/dev/nvme0n1`; change it if the hardware reports a different device.

If DHCP is not available, set a temporary static address from the Talos boot media or firmware/network console if supported, then apply the permanent static network config in the next phase. Do not hand-edit network state after installation; Talos should receive the final network state through machine config.

---

# Phase 3: generate Talos configuration from the workstation

Run this phase from the repository checkout on the workstation, not on the Talos console:

```bash
cd /Users/fs/orca/workspaces/home-dc-kubernetes/kittiwake
mkdir -p .private/infra-cluster/generated
```

The committed infra Talos source patches live in `talos/infra/`:

-   `talos/infra/cilium-patch.yaml`
-   `talos/infra/controlplane-patch.yaml`
-   `talos/infra/worker-patch.yaml`

Before generating, confirm these match the recorded NIC MAC addresses and install disks. Update the patch files first if the hardware changes.

Generate the cluster configuration:

```bash
talosctl gen config infra-cluster https://10.0.40.31:6443 \
  --output-dir .private/infra-cluster/generated \
  --config-patch @talos/infra/cilium-patch.yaml \
  --config-patch-control-plane @talos/infra/controlplane-patch.yaml \
  --config-patch-worker @talos/infra/worker-patch.yaml
```

The generated secrets are the identity of this cluster. Keep the directory private and backed up; do not commit it.

Confirm the generated machine configs contain the intended static addresses before applying them:

```bash
grep -n "10.0.40.31/24" .private/infra-cluster/generated/controlplane.yaml
grep -n "10.0.40.32/24" .private/infra-cluster/generated/worker.yaml
grep -n "hardwareAddr" .private/infra-cluster/generated/controlplane.yaml .private/infra-cluster/generated/worker.yaml
```

Optionally inspect the generated files before applying them:

```bash
talosctl validate --config .private/infra-cluster/generated/controlplane.yaml --mode metal
talosctl validate --config .private/infra-cluster/generated/worker.yaml --mode metal
```

---

# Phase 4: install Talos to the physical nodes

Install the control-plane node first. Use the temporary maintenance IP shown on the Talos screen as `--nodes`; the static IP from the generated config takes effect after Talos installs and reboots.

```bash
CP_NODE=<temporary-control-plane-address-shown-on-screen>
CP_DISK=nvme0n1
```

Confirm the disk one more time, then wipe it:

```bash
talosctl get disks --insecure --nodes "$CP_NODE"
talosctl wipe disk "$CP_DISK" --insecure --nodes "$CP_NODE"
```

This destroys data on the selected disk. Stop if the disk name does not match the internal SSD selected in `controlplane-patch.yaml`.

Apply the control-plane configuration after the wipe completes:

```bash
talosctl apply-config --insecure \
  --nodes "$CP_NODE" \
  --file .private/infra-cluster/generated/controlplane.yaml
```

The node writes Talos to the selected disk and reboots. Remove the USB media when the machine restarts so it boots from the internal disk.

Wait until the control-plane node answers on its permanent static IP:

```bash
until talosctl version --insecure --nodes 10.0.40.31; do sleep 10; done
```

Now boot the second mini PC from the Talos USB and stop at the maintenance screen. Record its temporary IP, NIC MAC, and install disk as in Phase 2. If the worker MAC or disk differs from `talos/infra/worker-patch.yaml`, update the patch and rerun `talosctl gen config` before applying the worker config.

Install the worker:

```bash
WK_NODE=<temporary-worker-address-shown-on-screen>
WK_DISK=nvme0n1
```

Confirm the disk one more time, then wipe it:

```bash
talosctl get disks --insecure --nodes "$WK_NODE"
talosctl wipe disk "$WK_DISK" --insecure --nodes "$WK_NODE"
```

Apply the worker configuration after the wipe completes:

```bash
talosctl apply-config --insecure \
  --nodes "$WK_NODE" \
  --file .private/infra-cluster/generated/worker.yaml
```

Remove the USB media when the worker restarts. Wait until it answers on its permanent static IP:

```bash
until talosctl version --insecure --nodes 10.0.40.32; do sleep 10; done
```

Configure `talosctl` to use the new cluster credentials:

```bash
export TALOSCONFIG=$PWD/.private/infra-cluster/generated/talosconfig
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

# Phase 5: bootstrap Kubernetes and install Cilium

Bootstrap etcd exactly once:

```bash
task talos:infra:bootstrap
```

Retrieve kubeconfig and give the context an explicit name:

```bash
task talos:infra:kubeconfig
```

Confirm the API responds. Nodes may remain `NotReady` until Cilium is installed:

```bash
kubectl --kubeconfig .private/infra-cluster/kubeconfig get nodes -o wide
```

Install Cilium using the Talos-compatible settings. Keep the chart version aligned with the version used by the repository/app cluster rather than blindly using `latest`.

```bash
task talos:infra:cilium
```

Verify networking and node readiness:

```bash
task talos:infra:verify
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

# Phase 6: register infra-cluster in the existing Argo CD hub

Argo CD remains hosted on `app-cluster` and manages both clusters.

Keep two kubeconfigs distinct:

-   app-cluster kubeconfig: repository-local `./kubeconfig`, current context `argocd`, namespace `argo-system`
-   infra-cluster kubeconfig: `~/clusters/infra-cluster/kubeconfig`, context `infra-cluster`

From the repository checkout, verify Argo CD still sees the renamed app cluster:

```bash
cd /Users/fs/orca/workspaces/home-dc-kubernetes/kittiwake
argocd cluster list --core
```

From the infra working directory, confirm the target kubeconfig context:

```bash
cd ~/clusters/infra-cluster
kubectl --kubeconfig ./kubeconfig config get-contexts
```

Register that exact context in the existing Argo CD hub. The command talks to Argo CD through the app-cluster repo kubeconfig and installs management credentials into the infra-cluster kubeconfig context:

```bash
KUBECONFIG=/Users/fs/orca/workspaces/home-dc-kubernetes/kittiwake/kubeconfig \
  argocd cluster add infra-cluster \
  --core \
  --kubeconfig ~/clusters/infra-cluster/kubeconfig \
  --name infra-cluster
```

Argo CD creates its management ServiceAccount and credentials on the target cluster. Review and accept the privilege prompt.

Verify registration:

```bash
cd /Users/fs/orca/workspaces/home-dc-kubernetes/kittiwake
argocd cluster list --core
argocd cluster get infra-cluster --core
```

Expected managed clusters:

```text
app-cluster
infra-cluster
```

Do not merge any Application targeting `infra-cluster` until this registration is healthy.

---

# Phase 7: storage and service placement decisions

The initial infra cluster must not depend on storage hosted inside `app-cluster` or on the Proxmox nodes it is intended to monitor.

Before deploying Pulse, Uptime Kuma, or Technitium, choose one of these storage patterns:

1. **Local persistent volumes on the physical nodes** — simplest, but tied to one node.
2. **External NAS-backed NFS/iSCSI** — preferred when the NAS remains online during Proxmox maintenance.
3. **Replicated storage across the two mini PCs** — possible, but two-node storage systems have quorum and split-brain trade-offs and add complexity.

For this small core cluster, external NAS-backed storage or explicitly node-pinned local storage is preferable to introducing Ceph.

Technitium DNS needs special planning:

-   expose DNS on stable LAN addresses using the existing load-balancer approach or dedicated node addresses
-   do not switch DHCP clients to the new resolver until the deployment is tested
-   retain the existing DNS server as a rollback path during migration
-   consider running a second Technitium instance outside this cluster if DNS availability must survive loss of the control-plane node

---

# Phase 8: deploy the core applications through a follow-up PR

After `infra-cluster` is registered and storage is ready, add separate Argo CD Applications targeting:

```yaml
destination:
    name: infra-cluster
```

Deploy in this order:

1. Doppler secret operator (`doppler-operator-infra`)
2. storage prerequisites
3. Pulse (`pulse-infra`) — pinned to `infra-wk-01` with `hostPath` storage for the first pass
4. Uptime Kuma
5. Technitium DNS (future deployment)

The old `technitium-dns` Application was an ExternalDNS webhook integration, not the DNS server itself, and is intentionally removed for now. Create or migrate the actual DNS-server workload deliberately and keep app-cluster-specific integrations separate where required.

Validate each application before proceeding:

```bash
argocd app get <application-name> --core
argocd app sync <application-name> --core
kubectl --context infra-cluster get pods -A
```

---

# Phase 9: maintenance test

Prove that the design meets its purpose:

1. Confirm Pulse, Uptime Kuma, and any future Technitium deployment are healthy on `infra-cluster`.
2. Shut down or pause the app-cluster VMs during a maintenance window.
3. Confirm the infra services remain reachable.
4. Confirm they correctly report the app cluster as unavailable.
5. Restore the app cluster and confirm recovery is detected.

## Recovery notes

Back up these items outside both clusters:

-   `generated/talosconfig`
-   Talos machine configuration/secrets
-   `infra-cluster` kubeconfig
-   application data for Pulse, Uptime Kuma, and Technitium
-   the Argo CD registration and deployment instructions in this repository

Because the initial cluster has one control-plane node, losing `infra-cp-01` makes the Kubernetes API unavailable. Existing workloads on the worker may continue running, but scheduling and reconciliation stop until the control-plane node is restored. This is an accepted initial limitation.
