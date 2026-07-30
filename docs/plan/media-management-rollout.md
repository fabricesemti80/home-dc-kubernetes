# 🎬 Media Management Rollout

![🎬 Media Management Rollout](../img/plan-media-management-rollout.svg)

## 📌 Phase 1

-   [x] Decide to reuse the `media` namespace for management services
-   [x] Choose `sabnzbd` instead of `nzbget` for the first downloader rollout
-   [x] Keep NFS for media paths and CephFS for app configs
-   [x] Defer cross-app API-key automation until base services are stable

## 📌 Implementation

-   [x] Add architecture notes for the media-management stack
-   [x] Scaffold `sabnzbd` application manifests
-   [x] Scaffold `qbittorrent` application manifests
-   [x] Scaffold `sonarr` application manifests
-   [x] Scaffold `prowlarr` application manifests
-   [x] Scaffold `recyclarr` application manifests
-   [x] Scaffold `radarr` application manifests
-   [x] Scaffold `jellyseerr` application manifests
-   [x] Add Argo CD applications for the first services
-   [ ] Sync Argo CD and verify workloads become healthy

## 📌 Operator Steps

-   [ ] Confirm `/media/downloads/complete` exists on the NFS server
-   [ ] Confirm `/media/downloads/incomplete` exists on the NFS server
-   [ ] Open `https://sabnzbd.krapulax.dev`
-   [ ] Complete SABnzbd first-run setup
-   [ ] Add Usenet server details in the SABnzbd UI unless a later Doppler-backed bootstrap is introduced
-   [ ] Open `https://qbittorrent.krapulax.dev`
-   [ ] Complete qBittorrent first-run setup
-   [ ] Set qBittorrent save path to `/downloads` and temporary path to `/incomplete-downloads`
-   [ ] Forward `6881/TCP` and `6881/UDP` from the router to `10.0.40.104:6881`
-   [ ] Open `https://sonarr.krapulax.dev`
-   [ ] Configure Sonarr root folders and downloader integration
-   [ ] Open `https://prowlarr.krapulax.dev`
-   [ ] Add indexers in Prowlarr
-   [ ] Add Sonarr as an app in Prowlarr using `http://sonarr.media.svc.cluster.local:8989`
-   [ ] Add `SONARR_API_KEY` to Doppler for Recyclarr
-   [ ] Verify Recyclarr syncs Sonarr quality settings
-   [ ] Open `https://radarr.krapulax.dev`
-   [ ] Configure Radarr root folders and downloader integration
-   [ ] Open `https://requests.krapulax.dev`
-   [ ] Connect Jellyseerr to Jellyfin, Sonarr, and Radarr

## ✅ Validation

-   [ ] `kubectl get pods -n media`
-   [ ] `kubectl get pvc -n media`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=sabnzbd`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=qbittorrent`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=sonarr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=prowlarr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=recyclarr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=radarr`
-   [ ] `kubectl describe pod -n media -l app.kubernetes.io/name=jellyseerr`
-   [ ] `kubectl exec -n media deploy/sabnzbd -- grep '^host_whitelist' /config/sabnzbd.ini`
-   [ ] `curl -I https://sabnzbd.krapulax.dev/`
-   [ ] `curl -I https://qbittorrent.krapulax.dev/`
-   [ ] `kubectl get svc -n media qbittorrent-peer`
-   [ ] `curl -I https://sonarr.krapulax.dev/`
-   [ ] `curl -I https://prowlarr.krapulax.dev/`
-   [ ] `curl -I https://radarr.krapulax.dev/`
-   [ ] `curl -I https://requests.krapulax.dev/`
-   [ ] `kubectl logs -n media deploy/recyclarr --tail=100`

## 📌 Follow-Up

-   [ ] Design and implement API-key bootstrap automation
