locals {
  tailscale_services = {
    beszel         = "Beszel"
    portainer      = "Portainer"
    pulse          = "Pulse"
    start          = "Homepage dashboard"
    "technitium-0" = "Technitium primary"
    "uptime-kuma"  = "Uptime Kuma"
    vaultwarden    = "Vaultwarden"
    whoami         = "Whoami"
  }
}

resource "tailscale_service" "homelab" {
  for_each = local.tailscale_services

  name    = "svc:${each.key}"
  comment = each.value
  ports   = ["tcp:443"]
  tags    = ["tag:container"]
}
