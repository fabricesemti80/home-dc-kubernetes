# Pulse retirement

Pulse and its infra-cluster agent are retired. Uptime Kuma remains; it does not replace Pulse's host, VM, backup or Kubernetes alerts. There is an accepted monitoring gap until the new stack is deployed and verified.

The infra `monitoring` namespace is shared and remains managed by `uptime-kuma-infra`. Pulse's hostPath `/var/pulse/data`, existing Backrest snapshots, Kubernetes credentials and Doppler entries are not deleted by the retirement tasks. The Pulse app-protect entry and its Backrest plan are removed together so an orphaned plan cannot keep failing on stale captures.

## Cutover

1. Before merging, run `task infrastructure:prepare-pulse-retirement` to inventory the live Applications and their allowlisted resources. The private inventory is tied to the infra cluster and records UIDs; it contains no secret values.
2. Merge the removal and wait for the parent Argo Application `apps` to mark both Pulse Applications as requiring pruning. The parent does not prune them automatically.
3. Run `task infrastructure:unregister-pulse-retirement`. It refuses changed Applications, finalizers or an unexpected cluster, and unregisters without cascading.
4. Wait for `uptime-kuma-infra` to adopt the shared namespace. Verify its tracking annotation is `uptime-kuma-infra:/Namespace:monitoring/monitoring`; if not, sync that Application and investigate rather than deleting the namespace.
5. Run `task infrastructure:retire-pulse`. It checks the namespace owner and inventoried resource UIDs and Argo ownership, then deletes only the explicitly allowlisted Pulse workload and routing resources. It never deletes the namespace, secrets, hostPath or backup snapshots.
6. Confirm Uptime Kuma remains healthy, Pulse workloads and routes are absent, the app-protect Pulse CronJob is gone, and Backrest no longer lists the `app-pulse` plan. Confirm the Cloudflare ingress and generated AutoKuma monitor no longer reference Pulse.

## Validation and security

Before merge: run `bash scripts/validate.sh`, `python3 scripts/generate-autokuma-monitors.py --check`, and render the Uptime Kuma and app-protect manifests. After merge, perform the cutover checks above. Pulse's privileged agent and cluster RBAC are removed; its credential objects are deliberately left untouched. Remove unused credentials separately only after checking their consumers.

To reverse the GitOps removal if needed, revert the retirement change and reconcile the restored Applications; the preserved data and credentials are not modified by the tasks. A restore to a disposable copy started Pulse and returned HTTP 200, but historical records and notifications were not tested.
