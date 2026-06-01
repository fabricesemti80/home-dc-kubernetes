# CephFS Storage Setup Guide

## Architecture Overview

This Kubernetes cluster uses **CephFS** storage provisioned from a **Ceph cluster running on Proxmox hypervisors**. The setup provides persistent storage for Kubernetes workloads via the **Ceph-CSI driver**.

### Components

-   **Ceph Cluster**: Running on Proxmox nodes (pve-0, pve-1, pve-2) at 10.0.70.x
-   **CephFS Filesystem**: `cephfs-vm` for Kubernetes storage
-   **Ceph-CSI Driver**: Provisioner in `storage` namespace
-   **StorageClass**: `cephfs` for dynamic PV provisioning
-   **Kubernetes Credentials**: Managed via Doppler secrets

---

## Prerequisites

### On Ceph Cluster (Proxmox)

1. **Ceph version 19.2.3 (Squid)** or compatible
2. **CephFS filesystem created**: `cephfs-vm`
3. **CephFS subvolume group**: `csi` (for Kubernetes CSI driver)
4. **Ceph admin credentials**: Available in `/etc/pve/priv/ceph.client.admin.keyring`

### On Kubernetes Cluster

1. **Ceph-CSI Helm chart deployed** (v3.12.3)
2. **Secret `csi-cephfs-secret`** in `kube-system` namespace
3. **StorageClass `cephfs`** configured
4. **Storage namespace** created in Kubernetes

---

## Setup Instructions

### Step 1: Create CephFS Subvolume Group (Proxmox)

SSH to any Proxmox node (pve-0, pve-1, or pve-2):

```bash
# Create the subvolume group for CSI
ceph fs subvolume group create cephfs-vm csi
```

**Verify it was created:**

```bash
ceph fs subvolume-group ls cephfs-vm
```

Expected output should show `csi` in the list.

### Step 2: Deploy Ceph-CSI Helm Chart

The helm chart is deployed via ArgoCD application `ceph-csi` to the `storage` namespace.

**Verify deployment:**

```bash
kubectl get pod -n storage -l app=ceph-csi-ceph-csi-cephfs-provisioner
kubectl get pod -n storage -l app=ceph-csi-ceph-csi-cephfs-nodeplugin
```

### Step 3: Create Secret with Ceph Credentials

The secret is generated from **Doppler** during `task configure`:

```bash
# In the kubernetes repository, run:
task configure

# This will:
# 1. Read CEPH_KEYRING from Doppler
# 2. Render templates with makejinja
# 3. Encrypt secrets with sops
# 4. Create kubernetes/apps/kube-system/ceph-csi/secret.sops.yaml
```

**Deploy the secret:**

```bash
sops -d kubernetes/apps/kube-system/ceph-csi/secret.sops.yaml | kubectl apply -f -

# Verify:
kubectl get secret csi-cephfs-secret -n kube-system
```

### Step 4: Create StorageClass

```bash
kubectl apply -f kubernetes/apps/storage/cephfs-sc.yaml

# Verify:
kubectl get storageclass cephfs
```

---

## Creating Persistent Volumes

### Using PVC with cephfs StorageClass

```yaml
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
    name: my-storage
    namespace: my-app
spec:
    accessModes:
        - ReadWriteMany
    storageClassName: cephfs
    resources:
        requests:
            storage: 10Gi
```

**Verify binding:**

```bash
kubectl get pvc -n my-app
kubectl describe pvc my-storage -n my-app
```

---

## Troubleshooting

### PVC Stuck in Pending

**Check provisioner logs:**

```bash
kubectl logs -n storage -l app=ceph-csi-ceph-csi-cephfs-provisioner -c csi-provisioner --tail=50
```

**Common Issues:**

| Error                                  | Solution                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------- |
| `subvolume group 'csi' does not exist` | Create the group on Ceph: `ceph fs subvolume group create cephfs-vm csi`  |
| `permission denied`                    | Verify `csi-cephfs-secret` exists in kube-system with correct credentials |
| `pool does not exist`                  | Verify `cephfs-vm_data` pool exists on Ceph cluster                       |

**Check Ceph cluster status:**

```bash
# From Proxmox node:
ceph status
ceph fs ls
ceph fs subvolume-group ls cephfs-vm
```

### Pod Not Starting

If pod is pending even after PVC is bound, check pod events:

```bash
kubectl describe pod <pod-name> -n <namespace>
```

Common causes:

-   Node selector constraints
-   Resource limits exceeded
-   Mount path permissions

---

## Monitoring

### Check Ceph Health

```bash
# From Proxmox:
ceph health detail
ceph df
ceph osd pool ls detail
```

### Monitor CSI Provisioner

```bash
# Watch for provisioning events
kubectl logs -n storage -f -l app=ceph-csi-ceph-csi-cephfs-provisioner -c csi-provisioner

# Check PVC status continuously
kubectl get pvc -n storage -w
```

### Provisioner Replica Count

The CephFS CSI provisioner intentionally runs as a single replica in this lab cluster. The control-plane nodes are schedulable and the API server is fronted by the Talos VIP, so a single provisioner avoids unnecessary leader-election traffic during API or etcd latency while retaining the node plugin on every control-plane node.

Assumptions:

-   Control-plane nodes remain schedulable for storage-system workloads.
-   CephFS provisioning availability is acceptable with one active provisioner pod in the lab environment.
-   Node plugins continue to run on every node for mount and unmount handling.

Validation checks:

```bash
kubectl get applications -n argo-system ceph-csi
kubectl get pods -n storage -l app=ceph-csi-cephfs
kubectl get --raw=/readyz
```

Rollback:

-   Increase `provisioner.replicaCount` in `kubernetes/apps/storage/ceph-csi/values.sops.yaml` and allow Argo CD to resync `ceph-csi`.

---

## Automation

### Ansible Deployment

The Proxmox setup is automated via Ansible in `infra-ansible-home-proxmoxhosts`:

```bash
# Create Ceph subvolume group automatically:
ansible-playbook site.yml
```

The playbook includes:

1. Ceph cluster initialization
2. MDS (Metadata Server) creation
3. **CephFS subvolume group creation** for CSI

### Kubernetes Deployment

Kubernetes storage is managed via ArgoCD:

-   **Application**: `ceph-csi-secret` (kube-system) - deploys Ceph credentials
-   **Application**: `storage` (storage namespace) - deploys Ceph-CSI helm chart
-   **Application**: `nginx-test-storage` (storage namespace) - test deployment using cephfs

---

## Testing

### Deploy Test Workload

```bash
kubectl apply -k kubernetes/storage/nginx-test/

# Verify PVC is bound:
kubectl get pvc -n storage

# Verify pod is running:
kubectl get pods -n storage -l app=nginx-test

# Check mounted volume:
kubectl exec -it -n storage <pod-name> -- df -h /usr/share/nginx/html
```

---

## Maintenance

### Expand PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
    name: my-storage
    namespace: my-app
spec:
    accessModes:
        - ReadWriteMany
    storageClassName: cephfs
    resources:
        requests:
            storage: 20Gi # Increased from 10Gi
```

Apply the change:

```bash
kubectl apply -f updated-pvc.yaml
```

### Backup CephFS

CephFS backups are handled by Proxmox backup jobs (configured in Ansible).

From Proxmox:

```bash
# Manual snapshot
ceph fs subvolume snapshot create cephfs-vm csi snapshot-name

# List snapshots
ceph fs subvolume-group snapshot ls cephfs-vm csi

# Remove snapshot
ceph fs subvolume snapshot rm cephfs-vm csi snapshot-name
```

---

## References

-   [Ceph CephFS Documentation](https://docs.ceph.com/en/latest/cephfs/)
-   [Ceph-CSI Driver](https://github.com/ceph/ceph-csi)
-   [Proxmox Ceph Integration](https://pve.proxmox.com/pve-docs/chapter-pveceph.html)
-   Kubernetes Repository: `kubernetes/apps/storage/`
-   Ansible Repository: `infra-ansible-home-proxmoxhosts/`

---

## Related Documentation

-   [Doppler Secrets Integration](./doppler.md)
-   [ArgoCD Applications](./argocd.md)
-   [Kubernetes Storage Classes](./kubernetes.md)
