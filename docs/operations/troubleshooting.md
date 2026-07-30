# 🔧 Troubleshooting

Common issues encountered during cluster bootstrap and their resolutions.

```mermaid
flowchart TD
    Issue[Something is wrong] --> Helm[helm list -A]
    Helm --> Stuck[Stuck release] --> Rollback[helm rollback]
    Helm --> PodFail[Pod failing] --> Logs[kubectl logs]
    Logs --> DNS[DNS/CoreDNS] --> FixImage[Fix container image]
    Logs --> CNI[CNI not ready] --> CheckCilium[Check Cilium pods]
    Logs --> VIP[VIP unreachable] --> Wait[Wait for etcd]
```

## 📌 Helm 4 Post-Renderer Incompatibility

**Symptom:**

```
Error: invalid argument "bash" for "--post-renderer" flag: plugin: {Name:bash Type:postrenderer/v1} not found
```

**Cause:** Helm 4 removed support for arbitrary executables as post-renderers. The `postRenderer: bash` directive in helmfile is no longer valid.

**Fix:** Remove `postRenderer` and `postRendererArgs` from the helmfile CRDs file (`bootstrap/helmfile.d/00-crds.yaml`). The bootstrap script already filters CRDs with `yq` after `helmfile template`, making the post-renderer redundant.

---

## 📌 Stuck Helm Releases (Another Operation in Progress)

**Symptom:**

```
Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress
```

**Cause:** A previous Helm install/upgrade was interrupted, leaving the release in a `pending-install` or `pending-upgrade` state.

**Diagnosis:**

```sh
helm list -A --pending
```

**Fix:** Roll back to the last successful revision:

```sh
helm rollback <release-name> <last-good-revision> -n <namespace>
# e.g. helm rollback coredns 3 -n kube-system

```

If the release has no successful revision (stuck on revision 1), uninstall and let the bootstrap recreate it:

```sh
helm uninstall <release-name> -n <namespace> --no-hooks
```

---

## 🥾 Helm Release Timeout During Initial Bootstrap

**Symptom:**

```
Error: UPGRADE FAILED: resource Deployment/kube-system/coredns not ready. status: Failed, message: Progress deadline exceeded
```

**Cause:** On a fresh cluster, Cilium (CNI) must be fully running before any other pods can get network connectivity. If Helm releases are deployed in parallel without dependency ordering, coredns, argo-cd, and others will time out waiting for pods that can't start without CNI.

**Fix:** Ensure proper dependency ordering in `bootstrap/helmfile.d/01-apps.yaml`:

```yaml
helmDefaults:
    timeout: 600 # 10 minutes for initial image pulls

releases:
    - name: cilium
      # ...
    - name: coredns
      needs: ["kube-system/cilium"]
      # ...
    - name: spegel
      needs: ["kube-system/coredns"]
      # ...
    - name: cert-manager
      needs: ["kube-system/spegel"]
      # ...
    - name: argo-cd
      needs: ["cert-manager/cert-manager"]
      # ...
```

After fixing, roll back any failed releases and re-run `task bootstrap:apps`.

---

## 📌 Argo CD Server-Side Apply Conflict

**Symptom:**

```
Error: UPGRADE FAILED: conflict occurred while applying object argo-system/argocd-secret /v1, Kind=Secret:
Apply failed with 1 conflict: conflict with "argocd-server" using v1: .data.admin.passwordMtime
```

**Cause:** The `argocd-server` controller writes `admin.passwordMtime` and `server.secretkey` fields to the `argocd-secret`, claiming field ownership. When Helm tries to upgrade with server-side apply, it conflicts with those fields.

**Fix:** Delete the secret and let Helm recreate it:

```sh
kubectl delete secret argocd-secret -n argo-system
helm rollback argo-cd <last-revision> -n argo-system
task bootstrap:apps
```

---

## 📌 VIP (Virtual IP) Unreachable

**Symptom:**

```
Unable to connect to the server: dial tcp 10.0.40.101:6443: connect: operation timed out
```

**Cause:** The Talos VIP can temporarily become unreachable during bootstrap, especially when etcd or the control plane is under heavy load. Individual control plane nodes may still be reachable.

**Diagnosis:**

```sh
# Check if individual nodes are reachable

ping 10.0.40.90  # control plane node 1

# Check cluster health via a direct node

talosctl -n 10.0.40.90 health --wait-timeout 30s

# Check etcd status

talosctl -n 10.0.40.90 etcd status
talosctl -n 10.0.40.90 etcd members
```

**Fix:** Usually the VIP recovers on its own once etcd stabilises. Wait a minute and retry. If the VIP stays down, check that the `vip` configuration in `talos/app/talconfig.yaml` is correct and that no other device on the network is using the same IP.

---

## 📌 CoreDNS CrashLoopBackOff — Wrong Container Image

**Symptom:**

```
exec: "-conf": executable file not found in $PATH
```

Both CoreDNS pods enter `CrashLoopBackOff`.

**Cause:** The `image.repository` in `kubernetes/apps/app-cluster/kube-system/coredns/values.yaml` was set to the Helm **chart** OCI artifact (`ghcr.io/coredns/charts/coredns`) instead of the actual CoreDNS **container** image. The chart artifact contains no `/coredns` binary, so the container args `["-conf", "/etc/coredns/Corefile"]` fail because there's no command to run.

**Diagnosis:**

```sh
kubectl -n kube-system describe pod -l k8s-app=kube-dns
# Look for: exec: "-conf": executable file not found in $PATH

kubectl -n kube-system get deploy coredns -o jsonpath='{.spec.template.spec.containers[0].image}'
# If it shows ghcr.io/coredns/charts/coredns:*, that's the chart image, not the runtime image

```

**Fix:** Update `kubernetes/apps/app-cluster/kube-system/coredns/values.yaml`:

```yaml
image:
    repository: registry.k8s.io/coredns/coredns
    tag: v1.12.0
```

> **Note:** Use `registry.k8s.io` instead of `docker.io/coredns/coredns` to avoid Docker Hub unauthenticated pull rate limits (429 Too Many Requests).

If DNS is already broken (preventing ArgoCD sync and image pulls), patch the live deployment directly:

```sh
kubectl -n kube-system set image deployment/coredns coredns=registry.k8s.io/coredns/coredns:v1.12.0
```

Then commit and push the values.yaml fix so ArgoCD keeps it in sync.

---

## 📌 General Tips

-   **Always check release status first:** `helm list -A` shows the state of all releases.
-   **Check pod status:** `kubectl get pods -A` gives a quick overview of what's running.
-   **Check node readiness:** `kubectl get nodes -o wide` — nodes will be `NotReady` until Cilium is running.
-   **Full cluster health check:** `talosctl -n <node-ip> health` validates etcd, kubelet, API server, and all control plane components.
-   **Clear helmfile cache if charts seem stale:** `helmfile cache cleanup`
