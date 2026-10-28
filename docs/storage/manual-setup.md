# 🔧 Manual Storage Setup Instructions

If you need to manually verify or repair the app-cluster storage layer, use these commands.

## ☸️ Verify Talos User Volumes

### 🔹 1. List volumes on a worker

```bash
talosctl --talosconfig talos/app/clusterconfig/talosconfig -n <worker-ip> get volumestatus u-local-path-provisioner
talosctl --talosconfig talos/app/clusterconfig/talosconfig -n <worker-ip> get mountstatus u-local-path-provisioner
```

Look for the `local-path-provisioner` user volume mounted at `/var/mnt/local-path-provisioner`.

### 🔹 2. Inspect the mount

```bash
talosctl --talosconfig talos/app/clusterconfig/talosconfig -n <worker-ip> ls /var/mnt/local-path-provisioner
```

---

## 🚀 Kubernetes Side (Verify Deployment)

### 📦 1. Check ArgoCD Applications

```bash
kubectl get application -n argo-system local-path jellyfin
```

### 💾 2. Verify StorageClass

```bash
kubectl get storageclass local-path
kubectl describe storageclass local-path
kubectl get storageclass local-path -o jsonpath='{.reclaimPolicy}'
kubectl get storageclass local-path -o jsonpath='{.volumeBindingMode}'
```

Expected: `reclaimPolicy: Retain`, `volumeBindingMode: WaitForFirstConsumer`.

### 💾 3. Verify NFS PV/PVC

```bash
kubectl get pv media-library-pv
kubectl describe pv media-library-pv
kubectl get pvc -n media media-library-pvc
```

Expected: `persistentVolumeReclaimPolicy: Retain`, `accessModes: ReadWriteMany`.

### 🚀 4. Check local-path-provisioner Pods

```bash
kubectl get pods -n local-path-storage
kubectl logs -n local-path-storage deployment/local-path-local-path-provisioner --tail=50
```

### 📊 5. Check PVC Status

```bash
kubectl get pvc -A
kubectl describe pvc <name> -n <namespace>
```

### 🔹 6. Check Pod Mount

```bash
POD=$(kubectl get pods -n <namespace> -l app=<app> -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n <namespace> $POD -- df -h <mount-path>
```

---

## 🚑 Troubleshooting Common Issues

### 🔹 Issue: PVC Stuck in Pending

**Check provisioner logs:**

```bash
kubectl logs -n local-path-storage -l app=local-path-provisioner --tail=100
```

**Common errors:**

| Error                               | Solution                                                                    |
| ----------------------------------- | --------------------------------------------------------------------------- |
| `no available nodes`                | Confirm the target worker has the user volume mounted and is Ready.         |
| `volume node affinity conflict`     | The pod is scheduled on a different worker than the bound PV; restore data. |
| `multiple PVCs requested same path` | Do not hard-code host paths; let the provisioner assign sub-paths.          |

### 🔹 Issue: NFS PV Not Bound

**Verify the NFS export from a worker:**

```bash
kubectl exec -it -n <namespace> <pod> -- showmount -e 10.0.40.2
```

**Check NFS PV events:**

```bash
kubectl describe pv media-library-pv
```

### 🔹 Issue: local-path-provisioner Not Running

```bash
kubectl get namespace local-path-storage
kubectl get deployments -n local-path-storage
kubectl describe pod -n local-path-storage -l app=local-path-provisioner
```

---

## 🔄 Recovery Steps

### 🔄 Restore a local-path Volume After Worker Failure

1.  Identify the application backup to restore.
2.  Ensure the replacement worker has a user volume at `/var/mnt/local-path-provisioner`.
3.  Create the new PVC and let it bind on the replacement worker.
4.  Restore the backup into the app container/database.
5.  Verify ownership, permissions, and application consistency.

⚠️ **WARNING**: A `local-path` PV cannot be moved to another worker. Restore is the only recovery path.

---

## 📌 See Also

-   [Storage Overview](./overview.md)
-   [Media NFS Storage](./media-nfs.md)
-   [Storage Verification](./verification.md)
-   [Database Backups](../cluster/database-backups.md)
