# CephFS Storage Setup Verification

**Status**: ✅ All Kubernetes components deployed and ready
**Last Updated**: 2026-03-14

## Setup Checklist

### Prerequisites on Ceph Cluster (Proxmox)

-   [ ] **CephFS Subvolume Group Created**: `ceph fs subvolumegroup create cephfs-vm csi`
    -   **Command**: SSH to any Proxmox node (pve-0, pve-1, or pve-2) and run the above
    -   **Verify**: `ceph fs subvolume-group ls cephfs-vm` should show `csi`
    -   **Status**: Required for PVC provisioning

### Kubernetes Deployment

The following has been automatically configured:

#### 1. **ArgoCD Applications** ✅

-   `ceph-csi-secret` (kube-system) - Deploys Ceph credentials from Doppler
-   `storage` (storage namespace) - Deploys Ceph-CSI Helm chart and StorageClass
-   `nginx-test-storage` (storage namespace) - Test deployment for verification

**Verification**:

```bash
kubectl get applications -n argo-system | grep ceph
kubectl get applications -n argo-system | grep storage
```

#### 2. **Ceph-CSI Secret** ✅

-   **Source**: `kubernetes/apps/kube-system/ceph-csi/`
-   **Template**: `templates/config/kubernetes/apps/kube-system/ceph-csi/secret.sops.yaml.j2`
-   **Integration**: Pulls `CEPH_KEYRING` from Doppler during `task configure`
-   **Deployment**: ArgoCD syncs encrypted secret to `kube-system` namespace

**Verification**:

```bash
kubectl get secret csi-cephfs-secret -n kube-system
kubectl describe secret csi-cephfs-secret -n kube-system
```

#### 3. **StorageClass** ✅

-   **File**: `kubernetes/apps/storage/cephfs-sc.yaml`
-   **Configuration**:
    ```yaml
    provisioner: cephfs.csi.ceph.com
    clusterID: a74bdf84-c6e5-4a3c-acf2-6c307f5c15a4
    fsName: cephfs-vm
    reclaimPolicy: Retain
    allowVolumeExpansion: true
    ```

**Verification**:

```bash
kubectl get storageclass cephfs
kubectl describe storageclass cephfs
```

#### 4. **Test Deployment (nginx-test)** ✅

-   **Location**: `kubernetes/storage/nginx-test/`
-   **Components**:
    -   **PVC**: `nginx-test-pvc` (1Gi, ReadWriteMany)
    -   **Deployment**: Single nginx pod using the PVC
    -   **Service**: ClusterIP for accessing nginx
    -   **HTTPRoute**: Gateway route via `envoy-internal` gateway

**Verification**:

```bash
# Check if namespace was created
kubectl get namespace storage

# Check PVC status (should be Bound after subvolume group is created)
kubectl get pvc -n storage
kubectl describe pvc nginx-test-pvc -n storage

# Check pod status
kubectl get pods -n storage -l app=nginx-test
kubectl describe pod -n storage -l app=nginx-test

# Test mount (if pod is running)
kubectl exec -it -n storage <pod-name> -- df -h /usr/share/nginx/html
kubectl exec -it -n storage <pod-name> -- cat /usr/share/nginx/html/index.html
```

---

## Prerequisites Status

### ✅ Kubernetes Side (Complete)

-   [x] ArgoCD Applications configured and synced
-   [x] Ceph-CSI Helm chart deployed via ArgoCD
-   [x] csi-cephfs-secret created with Doppler integration
-   [x] StorageClass `cephfs` created
-   [x] Test deployment manifests ready

### ✅ Proxmox Side (Complete)

-   [x] CephFS subvolume group `csi` created
    -   **Command**: `ceph fs subvolumegroup create cephfs-vm csi`
    -   **Status**: Verified with `ceph fs subvolumegroup ls cephfs-vm`
    -   **Result**: Subvolume group exists and ready for CSI provisioning

---

## End-to-End Testing

Once Ceph subvolume group is created, the flow is:

1. **PVC Creation** (ArgoCD syncs)

    - PVC `nginx-test-pvc` is created in `storage` namespace
    - Status: `Pending` → Waiting for provisioner

2. **Volume Provisioning** (CSI Provisioner)

    - Ceph-CSI provisioner detects PVC
    - Creates CephFS subvolume in `cephfs-vm/csi` group
    - Binds PVC to PersistentVolume
    - Status: `Pending` → `Bound`

3. **Pod Scheduling** (Kubernetes)

    - nginx pod is scheduled to a node
    - CephFS volume is mounted to pod
    - Pod starts successfully

4. **Verification**
    - Pod writes test content to `/usr/share/nginx/html`
    - Content is persisted on CephFS
    - Pod is accessible via HTTPRoute

---

## Troubleshooting

### PVC Stuck in Pending

**Check CSI provisioner logs:**

```bash
kubectl logs -n storage -l app=ceph-csi-ceph-csi-cephfs-provisioner -c csi-provisioner --tail=50
```

**Common errors:**

-   `subvolume group 'csi' does not exist` → Run: `ceph fs subvolumegroup create cephfs-vm csi` on Proxmox
-   `permission denied` → Verify Doppler secret and CEPH_KEYRING
-   `pool does not exist` → Verify `cephfs-vm_data` pool exists on Ceph

### Check Ceph Cluster Health

From Proxmox:

```bash
ceph status
ceph health detail
ceph fs ls
ceph fs subvolume-group ls cephfs-vm
```

### Pod Not Starting After PVC Binds

```bash
kubectl describe pod -n storage <pod-name>
kubectl logs -n storage <pod-name>
```

Common causes:

-   Mount permission issues
-   Resource constraints
-   Node selector mismatches

---

## Files & Configuration

### Kubernetes Files

| File                                                     | Purpose                      |
| -------------------------------------------------------- | ---------------------------- |
| `kubernetes/apps/storage/cephfs-sc.yaml`                 | StorageClass definition      |
| `kubernetes/storage/nginx-test/`                         | Test deployment manifests    |
| `kubernetes/apps/kube-system/ceph-csi/`                  | Secret kustomization         |
| `kubernetes/argo/apps/storage/`                          | ArgoCD Applications          |
| `templates/config/kubernetes/apps/kube-system/ceph-csi/` | Secret template with Doppler |

### Ansible Automation

| File                                       | Purpose                                               |
| ------------------------------------------ | ----------------------------------------------------- |
| `infra-ansible-home-proxmoxhosts/site.yml` | Proxmox deployment including subvolume group creation |

### Documentation

| File                           | Purpose                            |
| ------------------------------ | ---------------------------------- |
| `docs/storage/overview.md`     | Complete CephFS setup guide        |
| `docs/storage/verification.md` | This file - verification checklist |

---

## Next Steps

1. **Create Ceph Subvolume Group** (if not already done)

    ```bash
    # SSH to Proxmox node
    ssh root@pve-0
    ceph fs subvolumegroup create cephfs-vm csi
    ceph fs subvolume-group ls cephfs-vm  # Verify
    ```

2. **Trigger ArgoCD Sync**

    - Applications will automatically sync
    - Or trigger manually: `argocd app sync storage`

3. **Monitor Pod Startup**

    ```bash
    kubectl get pvc -n storage -w
    kubectl get pods -n storage -l app=nginx-test -w
    ```

4. **Verify Mount**
    ```bash
    kubectl exec -it -n storage <pod-name> -- df -h /usr/share/nginx/html
    ```

---

## Success Criteria

✅ **All steps complete when:**

1. ✅ Ceph subvolume group `csi` exists
2. ✅ PVC `nginx-test-pvc` status is `Bound`
3. ✅ Pod `nginx-test-xxxxx` status is `Running`
4. ✅ Mount shows CephFS filesystem in pod
5. ✅ Test content accessible in pod

---

## Verification Results (2026-03-14)

### ✅ All Prerequisites Met

**Ceph Cluster (Proxmox)**:

```bash
$ ceph fs subvolumegroup ls cephfs-vm
[
    {
        "name": "csi"
    }
]
```

**Kubernetes - PVC Status**:

```bash
$ kubectl get pvc -n storage
NAME             STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS
nginx-test-pvc   Bound    pvc-424871c0-4629-4413-b665-ee86c8f5d279   1Gi        RWX            cephfs
```

**Kubernetes - Pod Status**:

```bash
$ kubectl get pods -n storage -l app=nginx-test
NAME                          READY   STATUS    RESTARTS   AGE
nginx-test-7547d46bfd-lg9kb   1/1     Running   0          23m
```

**Mount Verification**:

```bash
$ kubectl exec -n storage nginx-test-7547d46bfd-lg9kb -- df -h /usr/share/nginx/html
Filesystem                                                                                    Size  Used Avail Use% Mounted on
10.0.70.10:6789,10.0.70.11:6789,10.0.70.12:6789:/volumes/csi/...                          1.0G     0  1.0G   0% /usr/share/nginx/html
```

**Content Verification**:

```bash
$ kubectl exec -n storage nginx-test-7547d46bfd-lg9kb -- cat /usr/share/nginx/html/index.html
<h1>Hello from Nginx on CephFS!</h1>
Storage Class: cephfs
PVC Name: nginx-test-pvc
```

### Conclusion

✅ **CephFS storage provisioning is fully operational**

-   Ceph cluster properly configured with CSI subvolume group
-   Kubernetes secret credentials deployed
-   StorageClass provisioning working
-   PVC successfully bound to CephFS volume
-   Pod mounted and serving content from CephFS
-   End-to-end integration verified

---

## References

-   [Storage Setup Guide](./overview.md)
-   [Ceph-CSI Documentation](https://github.com/ceph/ceph-csi)
-   [Ceph Documentation](https://docs.ceph.com/en/latest/cephfs/)
