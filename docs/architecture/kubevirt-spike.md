# KubeVirt GUI spike

Date: 2026-10-15. Environment: lab. Status: proposed, not deployed.

## Context and decision

Evaluate real KVM guests and KubeVirt Manager before deciding whether to replace
Proxmox with bare-metal Kubernetes. This spike does not migrate existing workloads.
Prefer infra-cluster: its Dell control plane is bare metal; app-cluster currently
runs inside Proxmox VMs and would need nested KVM exposed and verified first.

The recorded infra capacity is approximately 16 GiB + 8 GiB. Historical audit data
does not establish current free capacity. No live kubeconfig or metrics are available
in this development environment. Therefore installation is manual-sync and gated on
a live capacity/KVM/version check; this PR does not claim infra is presently large
enough. If the check fails, use the documented app-cluster adaptation after verifying
nested virtualisation, rather than deploying blindly onto critical infra services.

## Proposed architecture

-   Pinned upstream KubeVirt and CDI operators, separate from their custom resources
    so CRDs can become established before runtime sync.
-   KubeVirt Manager via the repository's app-template chart, ClusterIP only, accessed
    through a localhost kubectl port-forward. Ingress is denied by NetworkPolicy.
-   Opt-in node label confines operator/runtime/GUI pods to preflight-approved nodes.
    Initially label only infra-cp-01, keeping the smaller infra worker untouched.
-   One manually created, initially stopped CirrOS guest in kubevirt-lab; one vCPU,
    512 MiB guest RAM, disposable container disk. No default guest starts on merge.
-   CDI supports the GUI's disk-import workflow. Optional persistent disk testing
    uses explicit local-path storage (Retain), not the media share or CephFS: this
    is a disposable VM disk trial, not application configuration storage. Local
    disks do not migrate or replicate; retained PVs require explicit cleanup.
-   Namespace-scoped GUI writes in kubevirt-lab; cluster-wide discovery reads only.
    Cluster API, RBAC management and cross-namespace secret access are excluded.

## Constraints and risks

KubeVirt requires privileged host access and installs cluster-scoped CRDs, RBAC and
webhooks. It is not just a dashboard pod. Budget at least 3 GiB and 2 CPUs of live
headroom on the selected node before installation, then measure the actual operator
footprint before starting a guest. This is a planning gate, not a guaranteed maximum.
KubeVirt's infrastructure replicas are reduced to one for this explicitly non-HA lab.

No physical bridge, Multus, GPU passthrough, new storage system or Talos networking
change is needed for the first test. Default pod-network masquerade is sufficient.
The GUI is an optional third-party component, not a built-in KubeVirt console.
Some advanced UI pages intentionally lack permissions or backing operators.

## Validation criteria

-   Verify live Kubernetes version against the pinned KubeVirt support matrix.
-   Verify node readiness, free memory/CPU, requests and absence of pressure.
-   Require real schedulable KVM; do not use software emulation to mask a failed check.
-   Operators, KubeVirt and CDI report Available before GUI/guest testing.
-   GUI lists the guest; start/stop, serial console and VNC work.
-   GUI cannot read infra secrets or modify workloads outside kubevirt-lab.
-   Existing DNS, Argo, automation and monitoring remain healthy.

## Rollback

Follow the application README: remove test guests/disks first, uninstall KubeVirt and
CDI custom resources while their operators still run, then remove operators and GUI.
Do not delete CRDs first or delete retained PV data without checking its path.
No existing cluster applications or Proxmox hosts are removed by this spike.

## Next actions

-   [ ] Run the live preflight and choose infra or the documented app fallback.
-   [ ] Sync operator, runtime and GUI applications in order.
-   [ ] Evaluate the GUI and one guest; record measured resource use.
-   [ ] Remove the spike or design durable storage/availability separately.

## References

-   https://kubevirt.io/user-guide/cluster_admin/installation/
-   https://github.com/kubevirt/sig-release/blob/main/releases/k8s-support-matrix.md
-   https://docs.siderolabs.com/talos/v1.13/advanced-guides/install-kubevirt
-   https://docs.kubevirt-manager.io/
