# Docker Stack

The host-level Docker layer lives under `infra/docker/` and is managed separately from the Kubernetes cluster.

## Purpose

This stack provides the supporting services that either sit outside Kubernetes or help bootstrap and operate the rest of the homelab.

Common examples include:

1. Traefik
2. Cloudflared
3. Beszel
4. WhoAmI
5. Uptime Kuma
6. Arcane
7. Portainer

Current Cloudflare Access intent:

1. `portainer.krapulax.dev` stays protected by Cloudflare Access.
2. `beszel.krapulax.dev` remains the bypassed public service in this Docker tier.
3. Bambuddy is LAN-only at `http://bambuddy.krapulax.home:8000`; UniFi DNS points that name directly to `morpheus`.

Omni and its Proxmox provider are intentionally not part of this Docker tier.

## Deployment Model

The Docker stack is rendered locally from this repository checkout and deployed to `morpheus` over SSH using `task`:

```bash
task stack:render
task stack:config
task stack:deploy
```

## Secrets and Runtime Files

-   Doppler is the source of Docker deployment secrets for this repo
-   active Docker secret scope: `project-homelab / dev_homelab`
-   `DOMAIN` is the primary hostname input; service hostnames and app URLs are derived from it unless explicitly overridden
-   rendered runtime files are written to `infra/docker/runtime/`
-   the default Docker deployment target is `fs@10.0.40.19:/opt/project-homelab/infra/docker` (`morpheus`)
-   rendered `infra/docker/.env` pins `HOMELAB_DOCKER_ROOT` to the Docker stack root so included Compose files bind-mount the shared `runtime/` tree correctly
-   `PORTAINER_ADMIN_PASSWORD` is a required Doppler-backed bootstrap secret for Portainer; the stack passes it to Portainer with `--admin-password-file` so first-run admin creation does not depend on a manual five-minute setup window
-   local secret material belongs under `infra/docker/secrets/`
-   these runtime and secret paths stay out of Git

## Related Documents

-   [Architecture Plan](../architecture/ARCHITECTURE_PLAN.md)
-   [OpenTofu Setup](terraform.md)
