# Planka Rollout

## Scope

-   [x] Deploy Planka into the existing `productivity` namespace.
-   [x] Expose Planka externally at `https://planka.krapulax.dev`.
-   [x] Expose Planka internally at `https://planka.krapulax.home`.
-   [x] Store Planka attachments and app data on a CephFS-backed PVC mounted at `/app/data`.
-   [x] Store PostgreSQL data on a CephFS-backed PVC.
-   [x] Source runtime secrets from Doppler via the existing operator pattern.
-   [x] Model the internal UniFi DNS CNAME in Terraform for later apply.
-   [x] Model the external Cloudflare DNS record and Access app in Terraform for later apply.

## Namespace

Use `productivity`.

Planka is a user-facing planning and project-management application. It fits beside Linkwarden and Termix rather than `media`, `monitoring`, `network`, `storage`, or `kube-system`.

## Upstream References

-   Planka repository: `https://github.com/plankanban/planka`
-   Docker production docs: `https://docs.planka.cloud/docs/installation/docker/production-version/`
-   Upstream Docker Compose: `https://raw.githubusercontent.com/plankanban/planka/master/docker-compose.yml`

## Proposed Kubernetes Shape

-   Argo CD app: `kubernetes/argo/apps/productivity/planka.yaml`
-   App config: `kubernetes/apps/productivity/planka/`
-   Helm chart: existing `app-template` pattern
-   Main image: `ghcr.io/plankanban/planka:2.1.1`
-   Main container port: `1337`
-   Required env:
    -   `BASE_URL=https://planka.krapulax.dev`
    -   `DATABASE_URL` from Doppler-managed secret
    -   `SECRET_KEY` from Doppler-managed secret
    -   `TRUST_PROXY=true`
-   Bootstrap admin env:
    -   `DEFAULT_ADMIN_EMAIL` from Doppler-managed secret
    -   `DEFAULT_ADMIN_PASSWORD` from Doppler-managed secret
    -   `DEFAULT_ADMIN_NAME=Fabrice`
    -   `DEFAULT_ADMIN_USERNAME=fabrice`
-   PostgreSQL:
    -   `postgres:16-alpine`
    -   service name `planka-postgres`
    -   database/user `planka`
-   Routes:
    -   external `HTTPRoute` on `envoy-external` section `https`, hostname `planka.krapulax.dev`
    -   internal `HTTPRoute` on `envoy-internal` sections `http` and `https`, hostname `planka.krapulax.home`
-   Cloudflare DNS:
    -   proxied CNAME `planka.krapulax.dev` to `external.krapulax.dev`

## Doppler Secrets

Required in `project-homelab/dev_homelab`:

-   `PLANKA_DATABASE_URL`
-   `PLANKA_SECRET_KEY`
-   `PLANKA_DB_PASSWORD`
-   `PLANKA_DEFAULT_ADMIN_EMAIL`
-   `PLANKA_DEFAULT_ADMIN_PASSWORD`

`PLANKA_DATABASE_URL` should use the in-cluster service:

```text
postgresql://planka:<PLANKA_DB_PASSWORD>@planka-postgres/planka
```

## Security Impact

-   Planka is externally reachable, so application authentication must remain enabled.
-   The default admin password is sensitive and must stay in Doppler only.
-   `SECRET_KEY` must be stable across restarts and restores; changing it can invalidate sessions and signed tokens.
-   The Planka app PVC and PostgreSQL PVC contain user content and should be treated as backup-sensitive data.
-   Cloudflare Access is modeled as bypass to match Linkwarden's current external-app pattern; Planka's own authentication is the primary public access control.

## Assumptions

-   `planka.krapulax.dev` is the canonical external URL.
-   `planka.krapulax.home` should CNAME to `kubernetes.krapulax.home`.
-   The external route should be discoverable by Homepage under `Productivity`.
-   A single Planka replica and single PostgreSQL instance are acceptable for the first rollout.
-   CephFS remains the default storage class for app configuration and data PVCs.

## Validation

-   [ ] `doppler secrets get PLANKA_SECRET_KEY --project project-homelab --config dev_homelab`
-   [ ] `kubectl get dopplersecret -n doppler-operator-system planka-secrets -o yaml`
-   [ ] `kubectl get secret -n productivity planka-secrets`
-   [ ] `kubectl get application -n argo-system planka`
-   [ ] `kubectl get deploy,statefulset,pvc -n productivity | rg planka`
-   [ ] `kubectl rollout status deploy/planka -n productivity`
-   [ ] `kubectl rollout status statefulset/planka-database -n productivity`
-   [ ] `kubectl get httproute -n productivity planka planka-internal -o yaml`
-   [ ] `task tf:cloudflare:plan`
-   [ ] Open `https://planka.krapulax.dev`
-   [ ] Open `https://planka.krapulax.home`
-   [ ] Login with the Doppler-managed default admin credentials

## Rollback

-   [ ] Remove the Planka Argo CD application.
-   [ ] Remove the Planka `HTTPRoute` resources.
-   [ ] Remove the local DNS and Cloudflare Access Terraform entries if they were applied.
-   [ ] Keep the Planka PVCs until exported data and attachments are no longer needed.
-   [ ] Remove Planka Doppler secrets only after the app and data are intentionally decommissioned.
