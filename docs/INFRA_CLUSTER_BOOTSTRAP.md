# Infra-Cluster Bootstrap Guide

This document describes the manual steps required **outside of this PR** to provision and register the **infra-cluster** — the planned second Kubernetes cluster for base infrastructure (Terraform, Cloudflare, system tools).

This ArgoCD instance (hub) already manages both clusters. The infra-cluster apps live alongside the existing app-cluster apps under `kubernetes/argo/apps/`.

---

## Prerequisites

- Talos v1.7+ nodes (physical or VM) with network connectivity to the hub cluster
- A Talos `.yaml` config file for the new cluster
- `talosctl` installed on your admin machine
- `kubectl` with access to both clusters
- `argocd` CLI installed

---

## Step 1: Bootstrap the Infra-Cluster with Talos

```bash
# Generate configs
talosctl gen config infra-cluster https://<infra-cluster-control-plane-ip>:6443 \
  --output-dir ./infra-cluster

# Apply configs to the control plane node(s)
talosctl apply-config --filename ./infra-cluster/controlplane.yaml \
  --endpoints <infra-cp-ip> --nodes <infra-cp-ip>

# Bootstrap etcd
talosctl bootstrap --endpoints <infra-cp-ip> --nodes <infra-cp-ip>

# Wait for the cluster to come up
talosctl kubeconfig ./infra-cluster/kubeconfig \
  --endpoints <infra-cp-ip> --nodes <infra-cp-ip>
```

## Step 2: Install Cilium on Infra-Cluster

The infra-cluster needs Cilium for CNI (matching the app-cluster pattern).

```bash
# Install Cilium CLI
curl -L https://github.com/cilium/cilium-cli/releases/latest/download/cilium-linux-amd64.tar.gz \
  | tar xz && sudo mv cilium /usr/local/bin/

# Install Cilium on the infra-cluster
cilium install --context infra-cluster \
  --set cluster.name=infra-cluster \
  --set cluster.id=2 \
  --set ipam.mode=cluster-pool \
  --set ipam.operator.clusterPoolIPv4PodCIDRList="10.46.0.0/16" \
  --set ipam.operator.clusterPoolIPv4ServiceCIDRList="10.47.0.0/16"
```

**Note:** Verify the pod/service CIDRs don't overlap with the app-cluster (`10.42.0.0/16` and `10.43.0.0/16`).

## Step 3: Label Nodes (if needed)

```bash
kubectl --kubeconfig ./infra-cluster/kubeconfig label node <node-name> \
  node-role.kubernetes.io/control-plane=""
kubectl --kubeconfig ./infra-cluster/kubeconfig label node <worker-name> \
  node-role.kubernetes.io/worker=""
```

## Step 3b: Rename the Current Cluster to "app-cluster"

The default ArgoCD in-cluster is named `in-cluster`. To match this repo, rename it:

```bash
# Get the ArgoCD cluster server URL for the in-cluster
argocd cluster list

# Rename it
argocd cluster update https://kubernetes.default.svc --name app-cluster

# Verify
argocd cluster list
```

All 39 ArgoCD Application manifests in this repo now reference `destination.name: app-cluster`.

## Step 4: Register Infra-Cluster in ArgoCD (Hub)

On the **hub cluster** (app-cluster):

```bash
# List current clusters (should show app-cluster + in-cluster)
argocd cluster list

# Add the infra-cluster
# Either via kubeconfig context name:
argocd cluster add infra-cluster --name infra-cluster

# OR via kubeconfig file:
argocd cluster add admin@infra-cluster \
  --kubeconfig ./infra-cluster/kubeconfig \
  --name infra-cluster
```

**Verify registration:**
```bash
argocd cluster list
# Expected: app-cluster (current), in-cluster (default), infra-cluster (new)
```

## Step 5: Install Ceph-CSI on Infra-Cluster

If the infra-cluster needs persistent storage:

```bash
# The Ceph-CSI chart is already in the repo at kubernetes/apps/kube-system/ceph-csi/
# argo app at kubernetes/argo/apps/kube-system/ceph-csi.yaml
# Update its destination.name to "infra-cluster" after registration

kubectl --kubeconfig ./infra-cluster/kubeconfig apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: doppler-operator-system
EOF

# Install Doppler operator manually if needed:
kubectl --kubeconfig ./infra-cluster/kubeconfig apply -f https://downloads.doppler.com/public/kubernetes/doppler-operator.yaml
```

## Step 6: Set Up Terraform Backend (Optional)

The infra-cluster is intended to run the Terraform/Cloudflare management plane.

**Prerequisite (one-time, app-cluster):**
```bash
# Create S3 bucket for Terraform state (on Docker host Ceph/S3)
# s3://tf-state/infra-cluster/
```

**ArgoCD Application for Terraform:**
The terraform-controller app `kubernetes/argo/apps/infrastructure/terraform-controller.yaml`
will be synced to `infra-cluster` after registration.

## Step 7: Deploy Infra-Cluster Apps via ArgoCD

Once registered, sync the infra-cluster apps:

```bash
argocd app sync terraform-controller
argocd app sync cert-manager --cluster infra-cluster
# ... etc
```

**Note:** The infra-cluster ArgoCD Applications will be created as part of this PR
(under `kubernetes/argo/apps/infrastructure/`) and will target `destination.name: infra-cluster`.
They sit next to the app-cluster apps in the same ArgoCD hub — the `destination.name` field
determines which cluster they deploy to.

---

## Current Cluster State

| Cluster | ArgoCD Name         | Purpose                          | Nodes |
|---------|---------------------|----------------------------------|-------|
| Current | `app-cluster`       | Workloads (apps, media, CI/CD)   | 1 cp + 3 workers |
| Planned | `infra-cluster`     | Base infrastructure (Terraform, Cloudflare, system) | TBD |

---

## Directory Layout (This PR)

```
kubernetes/
├── argo/apps/
│   ├── ci-cd/            → app-cluster (CI/CD runners)
│   ├── infrastructure/   → infra-cluster (Terraform, Cloudflare operator)  ← NEW
│   ├── kube-system/      → app-cluster (cilium, coredns, ...)
│   ├── media/            → app-cluster
│   ├── monitoring/       → app-cluster
│   ├── network/          → app-cluster
│   ├── productivity/     → app-cluster
│   └── storage/          → app-cluster
└── apps/
    ├── ci-cd/            → app-cluster
    ├── infrastructure/   → infra-cluster                                     ← NEW
    ├── kube-system/
    ├── [...]
```

All existing apps remain unchanged. Infra-cluster apps are added alongside them.
The ArgoCD hub routes via `destination.name` in each Application manifest.
