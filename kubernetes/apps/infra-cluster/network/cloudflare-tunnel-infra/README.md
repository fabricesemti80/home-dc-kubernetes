# Infra Cloudflare Tunnel

This connector runs in `infra-cluster` and routes infra-owned public hostnames
directly to local services.

Terraform creates the separate tunnel and writes `TUNNEL_TOKEN_INFRA` to
Doppler. Public infra service hostnames should target
`external-infra.krapulax.dev`; only that canonical endpoint should point at the
infra tunnel ID.

Until infra-cluster has its own Cloudflare external-dns controller, those public
DNS records are declared in `kubernetes/apps/app-cluster/network/cloudflare-tunnel`.
