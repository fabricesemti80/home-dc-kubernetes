# Planka Decommission

## Scope

-   [x] Remove Planka from Argo CD desired state.
-   [x] Remove Planka Kubernetes manifests from the repository.
-   [x] Remove `planka.krapulax.home` from local DNS Terraform.
-   [x] Remove `planka.krapulax.dev` from Cloudflare Access Terraform.
-   [x] Remove Planka from dashboard navigation.
-   [x] Preserve live PVCs and Doppler secrets until data deletion is explicitly confirmed.
-   [x] Add validation and rollback steps.

## Non-Goals

-   Do not delete live Planka PVCs.
-   Do not delete Doppler Planka secrets.
-   Do not create a replacement project-management app in this change.

## Removed Desired State

-   Argo CD app: `kubernetes/argo/apps/productivity/planka.yaml`
-   App config: `kubernetes/apps/productivity/planka/`
-   Local DNS resource: `unifi_dns_record.planka_internal`
-   Cloudflare Access app key: `planka`
-   Dashboard link: `Planka`

## Secrets And Data

-   Keep existing Doppler Planka keys until the Planka data-retention decision is complete.
-   Keep Planka PVCs until exported data and attachments are no longer needed.
-   Delete Doppler keys only after confirming there is no rollback or export requirement.

## Security Impact

-   Removing the external route and Cloudflare Access entry reduces public exposure.
-   Removing the internal route and local DNS entry reduces LAN-visible attack surface.
-   Retained PVCs may still contain user data and should remain backup-sensitive.
-   Retained Doppler secrets remain secret material and must not be committed.

## Assumptions

-   Planka is no longer needed as an active service.
-   Argo CD will prune resources for removed applications during sync.
-   PVCs may remain in the cluster even after workload resources are removed.
-   Cloudflare and local DNS Terraform state currently own the records being removed.

## Validation

-   [ ] `kubectl get application -n argo-system planka`
-   [ ] `kubectl get deploy,statefulset,httproute -n productivity | rg planka`
-   [ ] `kubectl get pvc -n productivity | rg planka`
-   [ ] `task tf:localdns:plan`
-   [ ] `task tf:cloudflare:plan`
-   [ ] `dig +short planka.krapulax.home`

## Rollback

-   [ ] Restore `kubernetes/argo/apps/productivity/planka.yaml` from Git history.
-   [ ] Restore `kubernetes/apps/productivity/planka/` from Git history.
-   [ ] Restore the `planka` Cloudflare Access app entry and `planka.krapulax.home` local DNS resource from Git history.
-   [ ] Re-sync the restored Argo CD application.
-   [ ] Re-apply local DNS and Cloudflare Terraform plans.
-   [ ] Reuse retained PVCs and Doppler secrets if they were not deleted.
