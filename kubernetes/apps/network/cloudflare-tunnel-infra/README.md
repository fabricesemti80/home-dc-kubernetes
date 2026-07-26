# Infra Cloudflare Tunnel

This connector runs in `infra-cluster` and routes infra-owned public hostnames
directly to local services.

Terraform creates the separate tunnel and writes `TUNNEL_TOKEN_INFRA` to
Doppler. After Terraform applies, update the Cloudflare DNS target for
infra hostnames to the new tunnel ID before removing matching routes from the
app-cluster tunnel.
