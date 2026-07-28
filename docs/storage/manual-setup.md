# Manual CephFS Setup Instructions

If you need to manually create the CephFS subvolume group or verify the setup, use these commands.

## Proxmox Side (Ceph Cluster)

### 1. SSH to a Proxmox Node

```bash
ssh root@pve-0
# or pve-1 or pve-2
```

### 2. Create CephFS Subvolume Group

**Create the group** (idempotent - safe to run multiple times):

```bash
ceph fs subvolumegroup create cephfs-vm csi
```

**Verify it was created:**

```bash
ceph fs subvolume-group ls cephfs-vm
```

Expected output:

```
[
  {
    "name": "csi"
  }
]
```

### 3. Verify Ceph Health

```bash
ceph status
ceph health detail
ceph fs ls
```

---

## Kubernetes Side (Verify Deployment)

### 1. Check ArgoCD Applications

```bash
# List all storage-related applications
kubectl get applications -n argo-system | grep -E "(ceph|storage)"

# Check sync status
kubectl get applications -n argo-system ceph-csi-secret -o jsonpath='{.status.sync.status}'
kubectl get applications -n argo-system storage -o jsonpath='{.status.sync.status}'
kubectl get applications -n argo-system nginx-test-storage -o jsonpath='{.status.sync.status}'
```

### 2. Verify Secrets

```bash
# Check if csi-cephfs-secret exists
kubectl get secret csi-cephfs-secret -n kube-system
kubectl describe secret csi-cephfs-secret -n kube-system

# Verify it has the required keys
kubectl get secret csi-cephfs-secret -n kube-system -o jsonpath='{.data}' | jq 'keys'
```

**Required keys**: `adminID`, `adminKey`, `userID`, `userKey`

### 3. Verify StorageClass

```bash
# Check StorageClass
kubectl get storageclass cephfs
kubectl describe storageclass cephfs

# Verify parameters
kubectl get storageclass cephfs -o jsonpath='{.parameters}'
```

### 4. Check Ceph-CSI Deployment

```bash
# Check if ceph-csi chart was deployed
kubectl get pods -n storage -l app=ceph-csi-ceph-csi-cephfs-provisioner
kubectl get pods -n storage -l app=ceph-csi-ceph-csi-cephfs-nodeplugin

# Check provisioner logs for errors
kubectl logs -n storage -l app=ceph-csi-ceph-csi-cephfs-provisioner -c csi-provisioner --tail=50

# Check nodeplugin logs
kubectl logs -n storage -l app=ceph-csi-ceph-csi-cephfs-nodeplugin -c csi-nodeplugin --tail=50
```

### 5. Check PVC Status

```bash
# Create namespace if missing
kubectl create namespace storage --dry-run=client -o yaml | kubectl apply -f -

# Check PVC
kubectl get pvc -n storage
kubectl describe pvc nginx-test-pvc -n storage

# Watch PVC binding
kubectl get pvc -n storage -w
```

### 6. Check nginx-test Pod

```bash
# Check pod status
kubectl get pods -n storage -l app=nginx-test
kubectl describe pod -n storage -l app=nginx-test

# Check pod logs
kubectl logs -n storage -l app=nginx-test

# Watch pod startup
kubectl get pods -n storage -l app=nginx-test -w
```

### 7. Test Volume Mount (if pod is running)

```bash
# Get pod name
POD=$(kubectl get pods -n storage -l app=nginx-test -o jsonpath='{.items[0].metadata.name}')

# Check mount
kubectl exec -it -n storage $POD -- df -h /usr/share/nginx/html

# Check content
kubectl exec -it -n storage $POD -- cat /usr/share/nginx/html/index.html

# Verify it's mounted from CephFS
kubectl exec -it -n storage $POD -- mount | grep nginx
```

---

## Troubleshooting Common Issues

### Issue: PVC Stuck in Pending

**Check provisioner logs:**

```bash
kubectl logs -n storage -l app=ceph-csi-ceph-csi-cephfs-provisioner -c csi-provisioner --tail=100 | grep -i error
```

**Common error messages and solutions:**

| Error                                  | Solution                                                      |
| -------------------------------------- | ------------------------------------------------------------- |
| `subvolume group 'csi' does not exist` | Run: `ceph fs subvolumegroup create cephfs-vm csi` on Proxmox |
| `permission denied`                    | Check Doppler secret and CEPH_KEYRING value                   |
| `pool does not exist`                  | Verify `cephfs-vm_data` pool on Ceph: `ceph osd pool ls`      |
| `connection refused`                   | Verify Ceph cluster IP connectivity and firewall              |

### Issue: Secret Not Deployed

**Verify secret was generated from Doppler:**

```bash
# In the kubernetes repository:
task configure

# This should generate kubernetes/apps/app-cluster/kube-system/ceph-csi/secret.sops.yaml
ls -la kubernetes/apps/app-cluster/kube-system/ceph-csi/secret.sops.yaml
```

**Manually decrypt and check:**

```bash
sops -d kubernetes/apps/app-cluster/kube-system/ceph-csi/secret.sops.yaml
```

### Issue: CSI Provisioner Not Running

```bash
# Check if storage namespace exists
kubectl get namespace storage

# Check ceph-csi deployment in storage namespace
kubectl get deployments -n storage
kubectl describe deployment ceph-csi-ceph-csi-cephfs-provisioner -n storage

# Check pod events
kubectl describe pod -n storage -l app=ceph-csi-ceph-csi-cephfs-provisioner
```

---

## Manual Testing Workflow

If automated sync isn't working, deploy components manually:

### 1. Create Namespace

```bash
kubectl create namespace storage
```

### 2. Create Secret

```bash
# First, ensure Doppler secret exists locally
task configure

# Then deploy the secret
sops -d kubernetes/apps/app-cluster/kube-system/ceph-csi/secret.sops.yaml | kubectl apply -f -

# Verify
kubectl get secret csi-cephfs-secret -n kube-system
```

### 3. Create StorageClass

```bash
kubectl apply -f kubernetes/apps/app-cluster/storage/cephfs-sc.yaml

# Verify
kubectl get storageclass cephfs
```

### 4. Deploy Ceph-CSI (if not using ArgoCD)

```bash
# First check values
cat kubernetes/apps/app-cluster/storage/ceph-csi/values.sops.yaml

# Add the helm repo
helm repo add ceph-csi https://ceph.github.io/ceph-csi
helm repo update

# Install (adjust values as needed)
helm install ceph-csi ceph-csi/ceph-csi-cephfs \
  -n storage \
  --create-namespace \
  -f kubernetes/apps/app-cluster/storage/ceph-csi/values.sops.yaml
```

### 5. Deploy Test Application

```bash
kubectl apply -k kubernetes/apps/app-cluster/storage/nginx-test/

# Watch it come up
kubectl get pvc,pods -n storage -w
```

---

## Verification Checklist

-   [ ] Ceph subvolume group `csi` exists on Proxmox
-   [ ] Secret `csi-cephfs-secret` exists in `kube-system` namespace
-   [ ] StorageClass `cephfs` exists
-   [ ] Ceph-CSI provisioner pods are running
-   [ ] PVC `nginx-test-pvc` status is `Bound`
-   [ ] Pod `nginx-test-*` status is `Running`
-   [ ] Mount shows CephFS filesystem inside pod
-   [ ] Can read/write files to mounted volume

---

## Recovery Steps

### Reset Everything and Start Over

```bash
# Delete test application
kubectl delete -k kubernetes/apps/app-cluster/storage/nginx-test/ 2>/dev/null || true

# Delete StorageClass (will orphan PVs)
kubectl delete storageclass cephfs 2>/dev/null || true

# Delete secret
kubectl delete secret csi-cephfs-secret -n kube-system 2>/dev/null || true

# Delete namespace (will delete all pods/services/pvcs)
kubectl delete namespace storage 2>/dev/null || true

# On Proxmox, delete subvolume group (WARNING: deletes data)
# SSH to pve-0
ssh root@pve-0 "ceph fs subvolume-group rm cephfs-vm csi" 2>/dev/null || true

# Then re-run the setup from this document
```

⚠️ **WARNING**: Deleting the subvolume group will delete all data stored in that group.

---

## See Also

-   [Storage Setup Guide](./overview.md) - Complete architecture and setup guide
-   [Storage Verification](./verification.md) - Verification checklist
