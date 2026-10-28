# App cluster CephFS mount outage (2026-10-14)

## Impact

CephFS-backed workloads in the Proxmox app cluster could not mount their PVCs. This kept application pods from starting, including the media stack. Jellyfin was the priority service. The outage followed maintenance on the Proxmox and Ceph nodes; the exact trigger for older PVs losing a working mount path was not proven.

At recovery, Ceph itself was healthy. The Talos nodes did not have the Linux `ceph` kernel module, while existing CephFS PVs omitted the CSI `mounter` attribute and therefore attempted kernel mounts. The current StorageClass's `mounter: fuse` setting only affects newly provisioned PVs; it does not change existing PVs. The CSI driver and its node plugins were running, so this was a mount-mode mismatch rather than a CSI pod outage.

## Recovery performed

-   Confirmed the live CephFS StorageClass name is `cephfs` and its intended mount mode is FUSE.
-   Saved the original PV/PVC definitions and replica counts to a mode-0600 recovery snapshot outside Git.
-   Rebound 25 existing CephFS PV/PVC pairs with their original volume handles and Retain reclaim policy, adding the FUSE mounter attribute. No CephFS subvolumes were deleted.
-   Corrected one Home Assistant claim reference after its PVC was recreated. This briefly produced `ClaimMisbound`; the PVC was repaired and is now Bound.
-   Left 12 unused old PVs without FUSE unchanged because no current pod mounts them. Rebind those PVs before scheduling new consumers.
-   Restored the other saved workload replica counts. Home Assistant remains at zero replicas by operator direction; its PVC/data is retained.
-   Waited for Jellyfin initialization to complete, then verified its ready Service endpoint, `/health` response `Healthy`, and `/System/Info/Public` HTTP 200 with `StartupWizardCompleted: true`.

## Maintenance context

The maintenance execution had already encountered preflight, guest-shutdown and Ceph-restoration interruptions. Prior fixes are merged in `home-kestra`: [guest shutdown and continuation PR #9](https://github.com/fabricesemti80/home-kestra/pull/9) and [Ceph maintenance sequence PR #10](https://github.com/fabricesemti80/home-kestra/pull/10). The maintenance design is tracked in [Kubernetes PR #394](https://github.com/fabricesemti80/home-dc-kubernetes/pull/394). This report distinguishes the proven Kubernetes mount and credential failures from earlier workflow interruptions; their exact timing and all original execution errors have not been reconstructed here.

Kestra verifies Ceph and guest power state, but does not verify Kubernetes or application readiness. Until that integration is implemented, an operator must perform the four recovery checks below before declaring maintenance complete. Jellyfin took about six minutes to finish startup even after storage mounted successfully.

## Root cause and contributing issues

1. Existing PVs selected kernel mounting on Talos, which has no `ceph` kernel module. Adding `mounter: fuse` to the StorageClass alone could not repair already-created PVs.
2. Recovery changed immutable CSI PV source fields through object recreation. The first Home Assistant PVC recreation did not preserve the matching `claimRef` UID, causing a binding conflict. The recovery snapshot and retained volume handles allowed repair without deleting subvolumes.
3. Jellyfin's startup/readiness checks used the HTTP status from `/health`. During initialization that endpoint could return HTTP 200 with body `Degraded`, making the probe accept the service before it was usable. The app later completed initialization and is healthy now.
4. CSI credentials had drifted from the live Ceph admin key. The secret template also assigned that key to `csi-user` instead of the matching `admin` identity. Doppler's `home-dc-kubernetes/apps` `CEPH_KEYRING` was stale; it has now been updated and compared with the working live key without logging it.
5. Chart values duplicated the admin key under `csiConfig`, which the chart publishes as a ConfigMap. That copy is unnecessary because StorageClass secret references provide the mount credentials. This PR removes both duplicated values files and moves the public CSI settings to `values.yaml`. A controlled credential rotation remains required to retire the formerly exposed key.
6. Home Assistant's Git definition still enabled automated sync even though the live app had been paused and scaled down. A future sync could have brought it back.

## Durable changes

-   The `cephfs` StorageClass explicitly selects FUSE for new volumes.
-   Existing active PVs were repaired without changing their Ceph subvolumes or reclaim policy. The 12 unused legacy PVs still need the same migration before reuse.
-   The CSI release uses one provisioner replica and `OnDelete` for node plugins. This keeps node plugin replacement deliberate during recovery; apply updates only after checking existing workloads and scheduling a controlled rollout.
-   The CSI Secret and generation template now use the working admin identity/key. Doppler `home-dc-kubernetes/apps` `CEPH_KEYRING` is the generation source; the SOPS-encrypted CSI Secret is the deployment artifact. Public chart values contain no credentials. Keep both layers consistent during any rotation and never print key material.
-   Jellyfin startup and readiness now require the exact `Healthy` response body. Liveness remains a TCP check so a long ffmpeg scan does not restart an otherwise live process.
-   Home Assistant's desired replica count is zero. Its app configuration and PVC remain in Git and Ceph for a deliberate, data-preserving retirement decision.

## Validation and rollback

Before declaring recovery complete, check all four layers:

1. Ceph health and filesystem availability on the Proxmox cluster.
2. CSI node plugin and provisioner readiness in Kubernetes.
3. Every affected PVC is `Bound`, its PV retains the original volume handle and `Retain` policy, and new mount events have stopped.
4. Workload pods are Ready, Services have ready EndpointSlice addresses, and critical applications respond through their Service or route. For Jellyfin, verify `/health` says `Healthy` and `/System/Info/Public` returns 200. Pod `Running` alone is insufficient.

The recovery snapshot is `/private/tmp/cephfs-fuse-rebind-20261014.json` on the recovery workstation. It contains Kubernetes object definitions and must be treated as sensitive operational data. Preserve it until the migration and backup state are reviewed. Do not restore old PV definitions blindly: use the original handles and claim UIDs only after confirming current bindings and that no pod is using the volume.

If a future FUSE mount fails, stop affected consumers and inspect CSI node-plugin logs and pod events before recreating Kubernetes objects. Preserve each PV's `Retain` reclaim policy and CephFS volume handle. Never delete a CephFS subvolume as a mount troubleshooting step. Revert the readiness probe only if the image no longer provides the checked `/health` body; validate the actual application endpoint first.

## Follow-up

-   Test a Jellyfin playback session through the normal client route; only the in-cluster Service endpoints were checked during recovery.
-   Review the 12 unused legacy PVs and migrate them to FUSE before reuse.
-   Verify the CephFS backup schedule and perform a restore test; PV retention and Ceph replication are not backups.
-   Review whether CSI credentials are generated from Doppler or managed directly as SOPS-encrypted values, and document one authoritative rotation path without exposing key material.
-   Decide whether to remove Home Assistant's retained configuration and route in a separate retirement change. It is currently configured for zero replicas.
