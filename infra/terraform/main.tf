# Cloudflare Tunnel
resource "cloudflare_zero_trust_tunnel_cloudflared" "trinity" {
  count = 1

  account_id    = var.cloudflare_account_id
  name          = "trinity"
  tunnel_secret = null # Managed locally via config.yml
}

# DNS Records
locals {
  apps = {
    "arcane"    = "arcane.krapulax.dev"
    "beszel"    = "beszel.krapulax.dev"
    "uptime"    = "uptime.krapulax.dev"
    "whoami"    = "whoami.krapulax.dev"
    "portainer" = "portainer.krapulax.dev"
  }
}

resource "cloudflare_dns_record" "app" {
  for_each = local.apps

  zone_id = var.cloudflare_zone_id
  name    = each.value
  content = "${cloudflare_zero_trust_tunnel_cloudflared.trinity[0].id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
  ttl     = 1
}

# Access Policies (Standalone in v5)
resource "cloudflare_zero_trust_access_policy" "allow_emails" {
  count = 1

  account_id = var.cloudflare_account_id
  name       = "Allow selected users"
  decision   = "allow"

  include = [
    {
      email = {
        email = "emilfabrice@gmail.com"
      }
    }
  ]
}

resource "cloudflare_zero_trust_access_policy" "bypass" {
  count = 1

  account_id = var.cloudflare_account_id
  name       = "Bypass public service hostnames"
  decision   = "bypass"

  include = [
    {
      everyone = {}
    }
  ]
}

# Access Applications (Referencing policies in v5)
resource "cloudflare_zero_trust_access_application" "app" {
  for_each = toset(["arcane", "uptime", "portainer"])

  account_id = var.cloudflare_account_id
  name       = each.key == "arcane" ? "Arcane" : (each.key == "portainer" ? "Portainer" : "Uptime Kuma")
  domain     = local.apps[each.key]
  type       = "self_hosted"

  http_only_cookie_attribute = true
  session_duration           = "24h"

  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.allow_emails[0].id
      precedence = 1
    }
  ]
}

resource "cloudflare_zero_trust_access_application" "bypass_app" {
  for_each = toset(["beszel"])

  account_id = var.cloudflare_account_id
  name       = "Beszel Bypass"
  domain     = local.apps[each.key]
  type       = "self_hosted"

  http_only_cookie_attribute = true
  session_duration           = "24h"

  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.bypass[0].id
      precedence = 1
    }
  ]
}

resource "cloudflare_zero_trust_access_application" "jellyfin" {
  count = 1

  account_id = var.cloudflare_account_id
  name       = "Jellyfin"
  domain     = "jelly.krapulax.dev"
  type       = "self_hosted"

  http_only_cookie_attribute = true
  session_duration           = "720h"
  auto_redirect_to_identity  = false

  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.bypass[0].id
      precedence = 1
    }
  ]
}

resource "cloudflare_zero_trust_access_application" "jellyseerr" {
  count = 1

  account_id = var.cloudflare_account_id
  name       = "Jellyseerr"
  domain     = "requests.krapulax.dev"
  type       = "self_hosted"

  http_only_cookie_attribute = true
  session_duration           = "720h"
  auto_redirect_to_identity  = false

  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.bypass[0].id
      precedence = 1
    }
  ]
}

resource "cloudflare_zero_trust_access_application" "linkwarden" {
  count = 1

  account_id = var.cloudflare_account_id
  name       = "Linkwarden"
  domain     = "linkwarden.krapulax.dev"
  type       = "self_hosted"

  http_only_cookie_attribute = true
  session_duration           = "720h"
  auto_redirect_to_identity  = false

  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.bypass[0].id
      precedence = 1
    }
  ]
}

resource "cloudflare_zero_trust_access_application" "immich" {
  count = 1

  account_id = var.cloudflare_account_id
  name       = "Immich"
  domain     = "photos.krapulax.dev"
  type       = "self_hosted"

  http_only_cookie_attribute = true
  session_duration           = "720h"
  auto_redirect_to_identity  = false

  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.bypass[0].id
      precedence = 1
    }
  ]
}
