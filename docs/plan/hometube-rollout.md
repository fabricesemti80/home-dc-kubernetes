# 🎬 HomeTube Rollout

## 📌 Scope

-   [x] Deploy HomeTube into the existing `media` namespace.
-   [x] Expose externally at `https://hometube.krapulax.dev` behind Cloudflare Access (allow-only).
-   [x] Expose internally at `http://hometube.krapulax.home`.
-   [x] Persist downloaded videos on the shared NFS `media-library-pvc` under `downloads/hometube/videos`.
-   [x] Use `downloads/hometube/tmp` as the transient staging area.
-   [x] Run non-root (UID 1000) with an init container creating/chowning the NFS subdirectories.

## 📌 Namespace

Use `media` — HomeTube writes to the shared media NFS and serves video downloads, matching the existing media-stack conventions (jellyfin, radarr, sonarr, qbittorrent, sabnzbd, immich, prowlarr, jellyseerr all use `media` + `media-library-pvc`).

## 📚 Upstream References

-   HomeTube repository: `https://github.com/EgalitarianMonkey/hometube`
-   Deployment docs: `https://github.com/EgalitarianMonkey/hometube/blob/main/docs/deployment.md`
-   Installation docs: `https://github.com/EgalitarianMonkey/hometube/blob/main/docs/installation.md`

## 💡 Proposed Kubernetes Shape

-   Argo CD app: `kubernetes/argo/apps/app-cluster/media/hometube.yaml`
-   App config: `kubernetes/apps/app-cluster/media/hometube/`
-   Helm chart: existing `app-template` pattern (5.0.1)
-   Main image: `ghcr.io/egalitarianmonkey/hometube:2.9.1` (pinned)
-   Main container port: `8501` (Streamlit)
-   Health probe: HTTP `GET /_stcore/health`
-   Runs as image default user (UID 1000, `streamlit`), non-root
-   Persistence:
    -   `media-videos` → `media-library-pvc` subPath `downloads/hometube/videos`, mounted at `/data/videos`
    -   `media-tmp` → `media-library-pvc` subPath `downloads/hometube/tmp`, mounted at `/data/tmp`
    -   `media-init` → `media-library-pvc` mounted at `/init` in the init container only
-   Init container (`busybox`, runs as root by default):
    -   creates `downloads/hometube/videos` and `downloads/hometube/tmp` on the NFS
    -   chowns them to `1000:1000` so the non-root app can write
-   External route:
    -   `HTTPRoute` named `hometube`, parent `envoy-external` in namespace `network`, section `https`
    -   hostname `hometube.krapulax.dev`, external-dns annotation targets `external-apps.krapulax.dev`
-   Internal route:
    -   `HTTPRoute` named `hometube-internal`, parent `envoy-internal`, hostname `hometube.krapulax.home`
-   Local DNS:
    -   add `hometube.krapulax.home` as a CNAME to `kubernetes.krapulax.home` in `infra/terraform_localdns/`
-   Cloudflare Access:
    -   add `hometube` to `zero_trust_apps` in `infra/terraform_cloudflare/variables.tf`
    -   `policy_type = "allow"` → only the allow-listed email can reach the public route

## 🔐 Security Impact

-   HomeTube is a **public downloader**: without protection, anyone on the Internet could submit download jobs that consume bandwidth and write to the shared 8 TiB media volume.
-   Therefore the public route is gated by Cloudflare Access with an **allow-only** policy (matches the n8n pattern), while the internal route stays open on the LAN.
-   The app runs non-root (UID 1000) with no cluster RBAC (`createDefaultServiceAccount: false`, `automountServiceAccountToken: false`).
-   Only the `downloads/hometube/*` subpaths are writable by the app; it cannot touch other media folders.
-   YouTube cookies are not mounted; if signature errors appear, mount a small CephFS PVC with `youtube_cookies.txt` (do not put cookies in Git).

## 🤔 Assumptions

-   `media` namespace and `media-library-pvc` already exist (true — used by jellyfin/radarr/sonarr/qbittorrent/sabnzbd/immich/prowlarr/jellyseerr).
-   The NFS server is writable from pods; init container can chown subdirectories to UID 1000.
-   The internal Envoy Gateway supports WebSockets/streaming needed by Streamlit.
-   `downloads/hometube/` does not exist yet — created by the init container on first start.
-   A single replica is acceptable.

## ✅ Validation

-   [ ] `kubectl get application -n argo-system hometube` → `Synced` / `Healthy`
-   [ ] `kubectl get deploy -n media hometube` → 1/1 Ready
-   [ ] `kubectl get pods -n media -l app.kubernetes.io/name=hometube` → Running
-   [ ] `kubectl logs -n media deploy/hometube --tail=100` → no permission errors on `/data/videos`
-   [ ] `kubectl exec -n media deploy/hometube -- ls -la /data/videos /data/tmp` → dirs exist, owned by 1000
-   [ ] `kubectl get httproute -n media hometube hometube-internal` → Accepted
-   [ ] `dig +short hometube.krapulax.home` → internal gateway IP
-   [ ] `dig +short hometube.krapulax.dev` → `external-apps.krapulax.dev` (external-dns)
-   [ ] Open `https://hometube.krapulax.dev` → Cloudflare Access login, then HomeTube UI
-   [ ] Open `http://hometube.krapulax.home` → HomeTube UI
-   [ ] Submit a short test download → file appears under `downloads/hometube/videos` on the NFS

## ↩️ Rollback

-   [ ] Delete the `hometube` Argo CD application (cascade delete: patch with `resources-finalizer.argocd.argoproj.io` finalizer, then `kubectl -n argo-system delete application hometube`), or revert this PR and let Argo self-heal back.
-   [ ] Remove the `hometube` / `hometube-internal` HTTPRoutes.
-   [ ] Remove the `hometube.krapulax.home` local DNS record and the `hometube` Cloudflare Access app entry.
-   [ ] Keep `downloads/hometube/` on the NFS — it contains user downloads; do not delete without confirmation.
