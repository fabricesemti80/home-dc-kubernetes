# 💾 Storage Verification

This checklist verifies the app-cluster storage layer after bootstrap or recovery.

## 📌 Setup Checklist

### ☸️ Prerequisites on Proxmox / Terraform

-   [ ] App-cluster worker VMs have dedicated data disks provisioned.
-   [ ] Talos user volume `local-path-provisioner` is mounted at `/var/mnt/local-path-provisioner` on each worker.
-   [ ] NAS export `10.0.40.2:/media` is reachable from every worker.

### 🚀 Kubernetes Deployment

#### 1. **ArgoCD Applications**

-   `local-path` — deploys the local-path provisioner.
-   `jellyfin` — deploys the static NFS PV/PVC in its `config/` directory.

```bash
kubectl get application -n argo-system local-path jellyfin
```

#### 2. **StorageClass `local-path`**

```bash
kubectl get storageclass local-path
kubectl describe storageclass local-path
```

Confirm:

-   `provisioner: rancher.io/local-path`
-   `reclaimPolicy: Retain`
-   `volumeBindingMode: WaitForFirstConsumer`

#### 3. **NFS PV/PVC**

```bash
kubectl get pv media-library-pv
kubectl get pvc -n media media-library-pvc
```

Confirm:

-   `persistentVolumeReclaimPolicy: Retain`
-   `accessModes: ReadWriteMany`
-   NFS server `10.0.40.2`, path `/media`

#### 4. **local-path-provisioner Pods**

```bash
kubectl get pods -n local-path-storage
kubectl logs -n local-path-storage deployment/local-path-local-path-provisioner --tail=50
```

---

## 📋 Prerequisites Status

### ✅ Kubernetes Side

-   [ ] ArgoCD Applications configured and synced
-   [ ] `local-path-provisioner` deployed
-   [ ] StorageClass `local-path` created with `Retain` and `WaitForFirstConsumer`
-   [ ] Static NFS PV/PVC created

### ✅ Worker Side

-   [ ] Talos user volumes mounted on each worker
-   [ ] NAS reachable from each worker

---

## 📌 End-to-End Testing

### Local-path write/restart/read

Jellyfin's `/config` PVC is worker-local and uses a `Recreate` Deployment. After the GPU operator has advertised `nvidia.com/gpu` and Jellyfin is healthy, test persistence across a controlled restart:

```bash
kubectl -n media rollout status deployment/jellyfin
kubectl -n media exec deployment/jellyfin -c app -- sh -c 'printf local-path-ok > /config/.storage-check'
kubectl -n media rollout restart deployment/jellyfin
kubectl -n media rollout status deployment/jellyfin
kubectl -n media exec deployment/jellyfin -c app -- cat /config/.storage-check
kubectl -n media exec deployment/jellyfin -c app -- rm /config/.storage-check
kubectl -n media get pvc -o wide
```

The `cat` must return `local-path-ok`; inspect the bound config PV's node affinity and the replacement pod's node. **Do not delete the PVC or retained PV as a smoke test**. `Retain` intentionally leaves orphaned storage requiring deliberate recovery/cleanup.

### NFS media smoke test

```bash
kubectl exec -n media deploy/jellyfin -- df -h /data
kubectl exec -n media deploy/jellyfin -- ls /data
```

---

## 🚑 Troubleshooting

### 🔹 local-path PVC Stuck in Pending

```bash
kubectl logs -n local-path-storage deployment/local-path-local-path-provisioner --tail=50
kubectl describe pvc <name> -n <namespace>
```

Common causes:

-   No Ready worker with the user volume mounted
-   Pod scheduled on a different worker than the bound PV

### 🔹 NFS Mount Fails

```bash
kubectl describe pv media-library-pv
kubectl describe pvc media-library-pvc -n media
kubectl describe pod -n media -l app.kubernetes.io/instance=jellyfin
```

---

## ⚙️ Files & Configuration

### 🔹 Kubernetes Files

| File                                                 | Purpose                          |
| ---------------------------------------------------- | -------------------------------- |
| `kubernetes/apps/app-cluster/storage/local-path/`    | local-path-provisioner manifests |
| `kubernetes/apps/app-cluster/media/jellyfin/config/` | NFS PV/PVC and media app config  |
| `talos/app/talconfig.yaml`                           | Worker user volume configuration |

### 📚 Documentation

-   [Storage Overview](./overview.md)
-   [Media NFS Storage](./media-nfs.md)
-   [Storage Manual Setup](./manual-setup.md)
-   [Database Backups](../cluster/database-backups.md)

---

## 📌 Success Criteria

✅ **All steps complete when:**

1.  `local-path` StorageClass exists with `Retain` and `WaitForFirstConsumer`.
2.  local-path-provisioner pods are `Running`.
3.  A test local-path PVC binds, writes data, and retains its PV after PVC deletion.
4.  `media-library-pvc` is `Bound` and mountable from media pods.
