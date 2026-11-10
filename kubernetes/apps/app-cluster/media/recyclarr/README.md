# ♻️ Recyclarr Notes

Recyclarr syncs TRaSH-style quality settings into Sonarr and Radarr.

Required Doppler secrets:

-   `SONARR_API_KEY`
-   `RADARR_API_KEY`

The deployment uses:

-   Sonarr URL: `http://sonarr.media.svc.cluster.local:8989`
-   Radarr URL: `http://radarr.media.svc.cluster.local:7878`
-   schedule: `0 4 * * *`

Current intent:

-   Sonarr gets a `Series 1080p` profile
-   Radarr gets a `Movies 1080p` profile
-   movie quality definitions are tightened so obviously bogus tiny grabs are rejected by minimum size rules

Storage: `/config` uses the Longhorn claim `recyclarr-longhorn`; see [the migration record](../../../../../docs/operations/local-path-to-longhorn.md#recyclarr-cutover-completed-2026-11-10). The old local-path claim was deleted on 2026-11-10.

Validation:

-   check the pod logs for successful Sonarr and Radarr sync runs
-   confirm Sonarr and Radarr quality profiles update as expected
