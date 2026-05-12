# Cloudflare Tunnel
resource "cloudflare_zero_trust_tunnel_cloudflared" "trinity" {
  count = 1

  account_id    = var.cloudflare_account_id
  name          = "trinity"
  tunnel_secret = null # Managed locally via config.yml
}

# DNS Records & Zero Trust Applications
locals {
  dns_apps = {
    "arcane"    = "arcane.krapulax.dev"
    "beszel"    = "beszel.krapulax.dev"
    "uptime"    = "uptime.krapulax.dev"
    "whoami"    = "whoami.krapulax.dev"
    "portainer" = "portainer.krapulax.dev"
    "tdarr"     = "tdarr.krapulax.dev"
  }

  # Zero Trust Applications configuration
  # policy_type: "allow" or "bypass"
  # session_hours: session duration multiplier
  zero_trust_apps = {
    "arcane" = {
      name          = "Arcane"
      domain        = local.dns_apps["arcane"]
      policy_type   = "allow"
      session_hours = 24
      auto_redirect = false
    }
    "uptime" = {
      name          = "Uptime Kuma"
      domain        = local.dns_apps["uptime"]
      policy_type   = "allow"
      session_hours = 24
      auto_redirect = false
    }
    "portainer" = {
      name          = "Portainer"
      domain        = local.dns_apps["portainer"]
      policy_type   = "allow"
      session_hours = 24
      auto_redirect = false
    }
    "beszel" = {
      name          = "Beszel"
      domain        = local.dns_apps["beszel"]
      policy_type   = "bypass"
      session_hours = 24
      auto_redirect = false
    }
    "jellyfin" = {
      name          = "Jellyfin"
      domain        = "jelly.krapulax.dev"
      policy_type   = "bypass"
      session_hours = 720
      auto_redirect = false
    }
    "jellyseerr" = {
      name          = "Jellyseerr"
      domain        = "requests.krapulax.dev"
      policy_type   = "bypass"
      session_hours = 720
      auto_redirect = false
    }
    "linkwarden" = {
      name          = "Linkwarden"
      domain        = "linkwarden.krapulax.dev"
      policy_type   = "bypass"
      session_hours = 720
      auto_redirect = false
    }
    "immich" = {
      name          = "Immich"
      domain        = "photos.krapulax.dev"
      policy_type   = "bypass"
      session_hours = 720
      auto_redirect = false
    }
  }
}

resource "cloudflare_dns_record" "app" {
  for_each = local.dns_apps

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

# Access Applications (using locals with foreach)
resource "cloudflare_zero_trust_access_application" "app" {
  for_each = local.zero_trust_apps

  account_id = var.cloudflare_account_id
  name       = each.value.name
  domain     = each.value.domain
  type       = "self_hosted"

  http_only_cookie_attribute = true
  session_duration           = "${each.value.session_hours}h"
  auto_redirect_to_identity  = each.value.auto_redirect

  policies = [
    {
      id         = each.value.policy_type == "allow" ? cloudflare_zero_trust_access_policy.allow_emails[0].id : cloudflare_zero_trust_access_policy.bypass[0].id
      precedence = 1
    }
  ]
}
