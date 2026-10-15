# KubeVirt GUI trial (infra-cluster)

This PR registers three **manual-sync** Argo applications. Merging does not start
operators or a VM. No production application, Talos network or Proxmox setting is
changed. Design: [KubeVirt spike](../../../../docs/architecture/kubevirt-spike.md).

| Component                         | Pin     | Purpose                                 |
| --------------------------------- | ------- | --------------------------------------- |
| KubeVirt                          | v1.9.1  | Real QEMU/KVM guests                    |
| Containerized Data Importer (CDI) | v1.66.1 | GUI disk imports and DataVolumes        |
| KubeVirt Manager                  | 1.5.4   | Third-party web UI, serial/VNC consoles |
| app-template                      | 5.0.1   | Repository-standard GUI deployment      |

## 1. Live preflight: choose the cluster

Run from your administration machine, at the repository root. This development
session has no live cluster credentials: the 16 GiB Dell + 8 GiB worker inventory
and August resource audit are capacity clues, not current utilisation measurements.

```bash
kubectl config get-contexts
export SPIKE_CONTEXT=infra-cluster # replace with the actual infra kubeconfig context
export SPIKE_NODE=infra-cp-01
kubectl --context "$SPIKE_CONTEXT" version
kubectl --context "$SPIKE_CONTEXT" get nodes -o wide
kubectl --context "$SPIKE_CONTEXT" top nodes
kubectl --context "$SPIKE_CONTEXT" describe node "$SPIKE_NODE"
```

Proceed only if:

-   Kubernetes is **1.34–1.36**, supported by the pinned KubeVirt 1.9 release.
    Infra's live version is not recorded here; the app Talos source pins 1.36.3.
-   The selected node is Ready with no memory/disk/PID pressure and has at least
    **3 GiB RAM and 2 CPU cores of headroom**, considering both live use and existing
    pod requests. Keep critical infra services' burst capacity in reserve.
-   Hardware virtualisation is enabled. Use your existing infra Talos credentials
    to inspect `/dev/kvm` (for the Dell: `talosctl -n 10.0.40.31 ls /dev/kvm`).
    If missing, check BIOS virtualisation and the loaded KVM driver first.
-   Metrics are available. Missing metrics is not a pass.

Label only the approved Dell initially. Every spike component is constrained to
this opt-in label; the 8 GiB worker is excluded.

```bash
kubectl --context "$SPIKE_CONTEXT" label node "$SPIKE_NODE" \
  homelab.krapulax.dev/kubevirt-spike=true --overwrite
```

The headroom figure is a planning gate, not a measured or enforced cap on all
operator-created pods. Measure again after installation and before starting a VM.

### If infra does not fit

Do not sync the infra apps. The app cluster is the fallback, but its Talos nodes
currently run in Proxmox VMs: enable/verify host CPU passthrough and nested KVM on
the selected Proxmox host/guest first. Do not enable KubeVirt software emulation;
it would give a misleading performance test.

For a reviewed fallback change, move `kubernetes/apps/infra-cluster/kubevirt` to
`kubernetes/apps/app-cluster/kubevirt`, move the three Argo application files to
`kubernetes/argo/apps/app-cluster/kubevirt`, rename their `-infra` names to `-app`,
change every source/valueFiles path and `destination.name` to app-cluster.
Use the same opt-in label on one approved app node. Change CDI's scratch class and
persistent VM example to an explicitly verified, Retain storage class available
there (for example the existing `cephfs`), rather than assuming `local-path`
exists. Do not deploy both copies accidentally. No Proxmox or Talos machine
configuration changes are bundled with this trial.

## 2. Sync operators, then runtime, then GUI

After merge, let the existing root `apps` application discover the three child
applications. In Argo, sync **kubevirt-operators-infra only** first. Alternatively:

```bash
argocd app sync kubevirt-operators-infra
argocd app wait kubevirt-operators-infra --sync --health --timeout 300
kubectl --context "$SPIKE_CONTEXT" wait --for=condition=Established \
  crd/kubevirts.kubevirt.io crd/cdis.cdi.kubevirt.io --timeout=180s
kubectl --context "$SPIKE_CONTEXT" -n kubevirt rollout status deploy/virt-operator --timeout=300s
kubectl --context "$SPIKE_CONTEXT" -n cdi rollout status deploy/cdi-operator --timeout=300s

argocd app sync kubevirt-runtime-infra
kubectl --context "$SPIKE_CONTEXT" -n kubevirt wait kubevirt/kubevirt \
  --for=condition=Available --timeout=600s
kubectl --context "$SPIKE_CONTEXT" wait cdi/cdi --for=condition=Available --timeout=600s
kubectl --context "$SPIKE_CONTEXT" get node "$SPIKE_NODE" \
  -o jsonpath='{.status.allocatable.devices\.kubevirt\.io/kvm}{"\n"}'
kubectl --context "$SPIKE_CONTEXT" top nodes
kubectl --context "$SPIKE_CONTEXT" get pods -n kubevirt -o wide
kubectl --context "$SPIKE_CONTEXT" get pods -n cdi -o wide
```

Require positive allocatable KVM devices before testing guests. If runtime fails,
inspect its events/operator logs before proceeding. If headroom has disappeared,
stop here and uninstall using the sequence below.

```bash
argocd app sync kubevirt-manager-infra
argocd app wait kubevirt-manager-infra --sync --health --timeout 300
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-manager \
  port-forward --address 127.0.0.1 svc/kubevirt-manager 8080:8080
```

Open **http://127.0.0.1:8080** and keep the port-forward running. There is no DNS,
HTTPRoute, Cloudflare tunnel, NodePort or LoadBalancer endpoint. The GUI's ingress
NetworkPolicy blocks ordinary pod-network access; kubectl port-forward uses the
API/kubelet channel. Validate this behaviour with the installed Cilium policy.
Kubernetes port-forward permission is the access gate; do not bind it to 0.0.0.0.

Manual sync is intentional: child application sync waves alone would not guarantee
that CRDs/controllers become ready across separate Applications.

## 3. Put a stopped VM in the GUI

Install `virtctl` **v1.9.1** from the matching KubeVirt GitHub release for your OS
and architecture (or use `kubectl virt` with a matching krew plugin version).

```bash
kubectl --context "$SPIKE_CONTEXT" apply -f \
  kubernetes/apps/infra-cluster/kubevirt/kubevirt-runtime/examples/cirros-vm.yaml
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-lab get vm,vmi
```

In the UI, select **kubevirt-lab**, find **cirros-spike**, then try:

1. Inspect CPU, memory, disks and networking.
2. Start it, inspect the running instance and open serial console / VNC.
3. Log in using the demo image's public credentials: `cirros` / `gocubsgo`.
4. Stop it, start it again and delete/recreate it when finished.

CLI equivalents:

```bash
virtctl --context "$SPIKE_CONTEXT" -n kubevirt-lab start cirros-spike
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-lab get vmi -w
virtctl --context "$SPIKE_CONTEXT" -n kubevirt-lab console cirros-spike
virtctl --context "$SPIKE_CONTEXT" -n kubevirt-lab stop cirros-spike
```

This is a one-vCPU, 512 MiB guest; host overhead is additional. Its container disk
is **ephemeral**: stopping/removing the instance discards guest writes. No SSH or
LAN service is exposed. The guest uses pod-network masquerade. The example is
applied once, outside Argo reconciliation, so GUI edits and start/stop are not
immediately reverted by GitOps. The lab quota permits only one VM at a time.

GUI permissions allow VM/disk/service management in kubevirt-lab and read-only
cluster discovery. Cluster API, autoscaling, RBAC editing and other advanced pages
are outside this spike; permission errors there are expected. Snapshot/restore
requires a compatible CSI snapshot implementation and is not enabled here.

## 4. Optional: test disk import and persistence

After stopping the first guest, replace it with the persistent version:

```bash
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-lab delete vm cirros-spike --wait=true
kubectl --context "$SPIKE_CONTEXT" get storageclass local-path -o yaml
kubectl --context "$SPIKE_CONTEXT" apply -f \
  kubernetes/apps/infra-cluster/kubevirt/kubevirt-runtime/examples/cirros-persistent-vm.yaml
virtctl --context "$SPIKE_CONTEXT" -n kubevirt-lab start cirros-spike
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-lab get dv,pvc,pods -w
```

CDI imports a tiny CirrOS disk to a 4 GiB filesystem PVC. WaitForFirstConsumer can
leave the DataVolume waiting until you start the VM; this is expected. The existing
infra local-path provisioner is pinned to infra-cp-01: keep this trial on that node.
For GUI-created disks, choose local-path explicitly and stay within the 16 GiB lab
storage quota. A StorageProfile may need explicit RWO/Filesystem selections in the
GUI; the supplied example sets both.

Write a file inside the guest, stop/start it and verify the file remains. This tests
persistence, **not host failover, live migration or backup**. Node-local PVs remain
on the Dell. Do not put valuable data in this trial.

## 5. Permission and health checks

```bash
kubectl --context "$SPIKE_CONTEXT" auth can-i get secrets -n ai \
  --as=system:serviceaccount:kubevirt-manager:kubevirt-manager
# Expected: no
kubectl --context "$SPIKE_CONTEXT" auth can-i create virtualmachines.kubevirt.io -n kubevirt-lab \
  --as=system:serviceaccount:kubevirt-manager:kubevirt-manager
# Expected: yes
kubectl --context "$SPIKE_CONTEXT" auth can-i create virtualmachines.kubevirt.io -n default \
  --as=system:serviceaccount:kubevirt-manager:kubevirt-manager
# Expected: no
kubectl --context "$SPIKE_CONTEXT" top nodes
kubectl --context "$SPIKE_CONTEXT" get events -A --sort-by=.lastTimestamp
```

Record actual idle/guest-start RAM and CPU, UI errors, console operation and the
impact on DNS, monitoring, Argo and automation before deciding to keep it.

## 6. Uninstall in dependency order

All three child applications have no automatic sync or automatic prune. Keep this
true during removal; delete operator custom resources while operators still run.

```bash
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-lab delete vm --all --wait=true
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-lab delete dv --all --wait=true
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-lab get pvc
# Inspect the list; delete only spike PVCs that are no longer needed.
kubectl --context "$SPIKE_CONTEXT" -n kubevirt-lab delete pvc cirros-spike-root --ignore-not-found

kubectl --context "$SPIKE_CONTEXT" -n kubevirt delete kubevirt kubevirt --wait=true --timeout=300s
kubectl --context "$SPIKE_CONTEXT" delete cdi cdi --wait=true --timeout=300s
```

Revert/remove this PR's three Argo Application manifests from Git and sync the root
`apps` Application. Its `Prune=false` means the child Applications may remain;
remove them explicitly after the revert. On the Argo management cluster:

```bash
argocd app delete kubevirt-manager-infra --cascade --yes
argocd app delete kubevirt-runtime-infra --cascade --yes
argocd app delete kubevirt-operators-infra --cascade --yes
kubectl --context "$SPIKE_CONTEXT" label node "$SPIKE_NODE" \
  homelab.krapulax.dev/kubevirt-spike-
kubectl --context "$SPIKE_CONTEXT" get pv
```

`Retain` PVs/local directories survive PVC deletion. Inspect each PV's claimRef and
local path before explicitly removing the disposable data/PV. Do not delete shared
storage or forcibly strip finalizers. Check for operator-created CRDs/RBAC left
behind; remove them only after confirming no remaining workloads use them.
