# Docker Deployment

This directory owns the Docker deployment for services that used to be declared as NixOS `oci-containers` on `trinity`.
It is intentionally plain Docker Compose so it can run on non-Nix machines.

## Layout

-   `docker-compose.yml`: main Compose entrypoint. It includes each service-specific Compose file.
-   `arcane/`, `beszel/`, `cloudflared/`, `portainer/`, `traefik/`, `uptime-kuma/`, `whoami/`: one directory per service group.
-   `scripts/render-secrets.sh`: renders ignored runtime files from Doppler-injected environment variables.
-   `scripts/deploy.sh`: renders runtime files locally, syncs the Docker bundle to `morpheus`, and applies the stack there over SSH.
-   `runtime/`: generated config and secret mounts consumed by Compose. Ignored by Git.
-   `secrets/`: local source secret material. Ignored by Git.

Rendered `infra/docker/.env` should keep `HOMELAB_DOCKER_ROOT` pointed at the `infra/docker` directory itself. This avoids included service Compose files resolving shared bind mounts into service-local `runtime/` directories.

## Required Secrets

The Docker tasks now expect their runtime values to be injected from Doppler:

-   project: `project-homelab`
-   config: `dev_homelab`

The key values used by the Docker stack include:

-   `DOMAIN`
-   `CLOUDFLARED_TUNNEL_TOKEN`
-   `TRAEFIK_CLOUDFLARE_API_TOKEN`, `TRAEFIK_CLOUDFLARE_ZONE_ID`, `TRAEFIK_CLOUDFLARE_EMAIL`
-   `ARCANE_ENCRYPTION_KEY`, `ARCANE_JWT_SECRET`
-   `PORTAINER_ADMIN_PASSWORD`

Per-service values such as `ARCANE_HOSTNAME` or `BESZEL_APP_URL` are now optional overrides. By default the render step derives them from `DOMAIN`.
`PORTAINER_ADMIN_PASSWORD` is required when Portainer is part of the stack. The render step writes it to an ignored runtime secret that Portainer reads through `--admin-password-file`.

## Deploy

Render runtime files and deploy the stack to `morpheus` from this checkout:

```sh
task stack:render
task stack:config
task stack:deploy
```

By default the deploy script targets:

```sh
HOMELAB_DOCKER_HOST=fs@10.0.40.19
HOMELAB_DOCKER_REMOTE_DIR=/opt/project-homelab/infra/docker
```

Override those variables only when you intentionally want a different Docker host.

The deploy script renders `runtime/` and `infra/docker/.env`, syncs the Docker bundle to the remote host without copying local source `secrets/`, then runs:

```sh
docker compose -f docker-compose.yml up -d --remove-orphans
```

## Beszel Agent

The Beszel agent is behind the `agent` Compose profile and is configured to monitor the Docker host itself over a local Unix socket.
Enable it only when `BESZEL_AGENT_KEY` is set in Doppler:

```sh
export COMPOSE_PROFILES=agent
task stack:deploy
```

In the Beszel Hub, add the host system with `/beszel_socket/beszel.sock` as the Host / IP.
`BESZEL_AGENT_KEY` is the Hub public key shown when adding the system.

## Rollback

From the Docker host directory:

```sh
ssh fs@10.0.40.19 'cd /opt/project-homelab/infra/docker && sudo docker compose -f docker-compose.yml down'
```

Persistent state is in Docker named volumes prefixed with `homelab_`. Do not remove those volumes unless you intentionally want to erase service data.
