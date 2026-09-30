# ARC Runner Image Policy

## Decision (2026-09-30)

Pin the Actions runner image used by the `home-dc-kubernetes` ARC scale set to an immutable digest. The chart uses the runner image for both the runner container and the Docker-in-Docker init container, so the pinned value must render to both references.

The `latest` tag remains alongside the digest so Renovate can discover digest changes and propose reviewed updates. This supersedes resolving the runner image from the mutable tag alone.

## Assumptions and security impact

-   Renovate continues to detect and propose updates for the tag-plus-digest reference.
-   The pinned digest is the image currently used by the ARC scale set.
-   Pinning prevents an upstream tag move from changing runner code without a Git change; it does not replace review of updates or limit the permissions available to a runner job.

## Validation

Render `gha-runner-scale-set` chart version `0.14.2` with the production values and confirm both the runner and Docker-in-Docker init container resolve to the same digest. After merge, verify the runner scale set remains available and completes a repository workflow.

## Rollback

Revert the digest pin to restore tag-only resolution. If a pinned image cannot start, restore the previous known-good digest before investigating the new image.
