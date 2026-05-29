# Termix Rollout

## Scope

-   [x] Deploy Termix into the existing `productivity` namespace.
-   [x] Expose Termix internally only at `http://termix.krapulax.home`.
-   [x] Do not create an external `HTTPRoute`, Cloudflare DNS record, or public tunnel route.
-   [x] Persist Termix application data at `/app/data` on a CephFS-backed PVC.
-   [ ] Include `guacd` as an optional sidecar or companion controller only if RDP, VNC, or Telnet support is required for the first rollout.
-   [x] Start without OIDC or Doppler secrets for the Tailscale-only initial rollout.
-   [x] Keep Termix-generated database, JWT, and internal auth keys in the persistent data volume, not in Git.

## Namespace

Use `productivity`.

Termix is a user-facing admin/productivity application, similar in placement to Linkwarden. It should not live in `network`, `monitoring`, `storage`, or `kube-system` because it is not cluster infrastructure. It should not live in `media` because it does not consume the shared media storage conventions.

## Upstream References

-   Termix repository: `https://github.com/Termix-SSH/Termix`
-   Docker install docs: `https://docs.termix.site/install/server/docker/`
-   Environment variable docs: `https://docs.termix.site/environment-variables/`
-   Reverse proxy docs: `https://docs.termix.site/reverse-proxy/`
-   Remote desktop docs: `https://docs.termix.site/remote-desktop/`
-   OIDC docs: `https://docs.termix.site/oidc/`

## Proposed Kubernetes Shape

-   Argo CD app: `kubernetes/argo/apps/productivity/termix.yaml`
-   App config: `kubernetes/apps/productivity/termix/`
-   Helm chart: existing `app-template` pattern
-   Main image: `ghcr.io/lukegus/termix:release-2.3.1`
-   Main container port: `8080`
-   Required env:
    -   `PORT=8080`
    -   `DATA_DIR=/app/data`
    -   `NODE_ENV=production`
    -   `SSL_ENABLED=false`
-   Optional remote desktop env:
    -   `ENABLE_GUACAMOLE=true`
    -   `GUACD_HOST=termix-guacd`
    -   `GUACD_PORT=4822`
-   Persistence:
    -   `config` or `data` PVC
    -   `storageClass: cephfs`
    -   start at `5Gi`, expand if saved host metadata, SSH keys, logs, or exports grow
    -   mount at `/app/data`
-   Internal route:
    -   `HTTPRoute` named `termix-internal`
    -   parent `envoy-internal` in namespace `network`
    -   section `http`
    -   hostname `termix.krapulax.home`
-   Local DNS:
    -   add `termix.krapulax.home` as a CNAME to `kubernetes.krapulax.home` in `infra/terraform_localdns/`

## Doppler Secrets

Required only if OIDC is enabled at rollout:

-   `TERMIX_OIDC_CLIENT_ID`
-   `TERMIX_OIDC_CLIENT_SECRET`
-   `TERMIX_OIDC_ISSUER_URL`
-   `TERMIX_OIDC_AUTHORIZATION_URL`
-   `TERMIX_OIDC_TOKEN_URL`

Optional OIDC controls:

-   `TERMIX_OIDC_USERINFO_URL`
-   `TERMIX_OIDC_IDENTIFIER_PATH`
-   `TERMIX_OIDC_NAME_PATH`
-   `TERMIX_OIDC_SCOPES`
-   `TERMIX_OIDC_ALLOWED_USERS`
-   `TERMIX_OIDC_FORCE_HTTPS`
-   `TERMIX_OIDC_ALLOW_REGISTRATION`

Do not add these to Doppler for a normal fresh install:

-   `JWT_SECRET`
-   `DATABASE_KEY`
-   `INTERNAL_AUTH_TOKEN`

Termix auto-generates those values on first startup and stores them in `{DATA_DIR}/.env`. Only add them to Doppler for a restore workflow where an existing backup requires exact secret reuse.

## Security Impact

-   Termix can store SSH hosts, credentials, keys, command history, file access metadata, API keys, and remote desktop credentials, so internal-only routing is mandatory for the first rollout.
-   The service must not be reachable through `envoy-external`, Cloudflare Tunnel, or public DNS.
-   Prefer OIDC plus a narrow allow list before saving any privileged SSH credentials.
-   Keep local Termix registration disabled after the initial admin account exists unless OIDC registration is intentionally configured.
-   Do not mount Docker socket access into Termix for the initial cluster deployment.
-   Treat the Termix PVC as sensitive backup material because it contains encrypted database files and generated encryption material.

## Assumptions

-   `productivity` remains the namespace for user-facing non-media applications.
-   `termix.krapulax.home` is the intended internal hostname.
-   The internal Envoy Gateway path supports WebSockets for SSH terminal sessions.
-   A single Termix replica is acceptable because the SQLite data and generated secrets live in a single persistent data directory.
-   CephFS is the correct storage class for app configuration/data PVCs.
-   Remote desktop support can be deferred if SSH-only access is enough for the first rollout.

## Validation

-   [ ] `doppler secrets get TERMIX_OIDC_CLIENT_ID --project project-homelab --config dev_homelab` if OIDC is enabled
-   [ ] `kubectl get application -n argo-system termix`
-   [ ] `kubectl get deploy -n productivity termix`
-   [ ] `kubectl get pvc -n productivity | rg termix`
-   [ ] `kubectl get httproute -n productivity termix-internal -o yaml`
-   [ ] `kubectl rollout status deploy/termix -n productivity`
-   [ ] `kubectl logs -n productivity deploy/termix --tail=100`
-   [ ] `dig +short termix.krapulax.home`
-   [ ] Open `http://termix.krapulax.home`
-   [ ] Confirm terminal sessions work through the internal route
-   [ ] If `guacd` is enabled, confirm RDP/VNC/Telnet connection tests work and that `termix-guacd` is not externally exposed

## Rollback

-   [ ] Remove the Termix Argo CD application.
-   [ ] Remove the `termix-internal` `HTTPRoute`.
-   [ ] Remove the `termix.krapulax.home` local DNS record.
-   [ ] Remove the Termix DopplerSecret manifest if OIDC secrets were synced.
-   [ ] Keep the Termix PVC until exported data, saved credentials, and generated encryption material are no longer needed.
-   [ ] Delete the Termix PVC only after backup or destruction is explicitly confirmed.
