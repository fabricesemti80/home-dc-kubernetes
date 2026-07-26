# Infra Cloudflare Tunnel

This connector runs in `infra-cluster` and routes `pulse.krapulax.dev`
directly to the local Pulse service.

Terraform creates the separate tunnel and writes `TUNNEL_TOKEN_INFRA` to
Doppler. After Terraform applies, update the Cloudflare DNS target for
`pulse.krapulax.dev` to the new tunnel ID before removing the Pulse route from
the app-cluster tunnel.
