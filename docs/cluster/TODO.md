# TODO: Homelab Improvement Tasks

## Completed (High Priority)

### 1. Domain Documentation

-   **Issue:** Hardcoded domains in http-route.yaml (34 locations)
-   **Status:** Done
-   **Action:** Created `docs/cluster/domains.md` as central reference

### 2. Health Probes

-   **Issue:** Verify all apps have proper health probe configs
-   **Status:** Done
-   **Action:** Verified: All 13 apps have probes (Recyclarr is cron job, doesn't need)

### 3. Resource Limits

-   **Issue:** Add memory/cpu limits to apps missing them
-   **Status:** Done
-   **Action:** Verified: All apps with resources define both requests AND limits

### 4. Database Backups

-   **Issue:** Document or implement backup for databases
-   **Status:** Done
-   **Action:** Created `docs/cluster/database-backups.md` with manual backup commands

### 5. TZ Consolidation

-   **Issue:** TZ: Europe/London repeated in ~10 values.yaml files
-   **Status:** Deferred
-   **Action:** Per-app TZ is correct - must be injected as env var into containers

---

## Completed (Medium Priority)

### 6. Image Tags

-   **Issue:** Some apps use `release` or `latest` instead of pinned versions
-   **Files:** media/\*arr apps, immich, jellyfin, etc.
-   **Status:** Done (with 3 reverted to latest)
-   **Action:** Updated:
    -   jellyfin: latest → 10.11.7
    -   sonarr: latest → 4.0.17
    -   radarr: latest → 6.1.1
    -   sabnzbd: latest → 4.5.5
    -   immich: release → v2.7.5 (2 containers)
    -   jellyseerr/prowlarr/qbittorrent: reverted to latest (version tags unavailable)

### 7. Security Contexts

-   **Issue:** Inconsistent - some explicit, some inherit
-   **Status:** Deferred
-   **Action:** Most apps inherit pod defaults; LinuxServer images require root

### 8. Registry Auth in Git

-   **Issue:** Hardcoded registry credentials in Talos machine config
-   **Status:** Deferred
-   **Action:** Requires careful migration, low priority

### 9. Inconsistent Values Structure

-   **Issue:** Mix of `values.yaml`, `values.sops.yaml`, plain config
-   **Status:** Deferred
-   **Action:** Low risk, low priority - accept current pattern

### 10. Add Common Helm Values

-   **Issue:** Repeated patterns (probes, security contexts, resources)
-   **Status:** Deferred
-   **Action:** High effort, low benefit

---

## Completed (Low Priority)

-   Create master app catalog/index
-   Document app addition workflow
-   Improve Taskfiles organization

## ---

## All Tasks Complete
