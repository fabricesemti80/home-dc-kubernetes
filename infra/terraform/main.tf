# Cloudflare Tunnel
resource "cloudflare_zero_trust_tunnel_cloudflared" "trinity" {
  count = 1

  account_id    = var.cloudflare_account_id
  name          = "trinity"
  tunnel_secret = null # Managed locally via config.yml
}

# DNS Records & Zero Trust Applications
locals {
  base_domain = "krapulax.dev"

  dns_apps = {
    "arcane"    = "arcane"
    "beszel"    = "beszel"
    "uptime"    = "uptime"
    "whoami"    = "whoami"
    "portainer" = "portainer"
    "tdarr"     = "tdarr"
  }

  # Zero Trust Applications configuration
  # policy_type: "allow" or "bypass"
  # session_hours: session duration multiplier
  zero_trust_apps = {
    "arcane" = {
      name          = "Arcane"
      subdomain     = "arcane"
      policy_type   = "allow"
      session_hours = 24
      auto_redirect = false
    }
    "uptime" = {
      name          = "Uptime Kuma"
      subdomain     = "uptime"
      policy_type   = "allow"
      session_hours = 24
      auto_redirect = false
    }
    "portainer" = {
      name          = "Portainer"
      subdomain     = "portainer"
      policy_type   = "allow"
      session_hours = 24
      auto_redirect = false
    }
    "beszel" = {
      name          = "Beszel"
      subdomain     = "beszel"
      policy_type   = "bypass"
      session_hours = 24
      auto_redirect = false
    }
    "jellyfin" = {
      name          = "Jellyfin"
      subdomain     = "jelly"
      policy_type   = "bypass"
      session_hours = 720
      auto_redirect = false
    }
    "jellyseerr" = {
      name          = "Jellyseerr"
      subdomain     = "requests"
      policy_type   = "bypass"
      session_hours = 720
      auto_redirect = false
    }
    "linkwarden" = {
      name          = "Linkwarden"
      subdomain     = "linkwarden"
      policy_type   = "bypass"
      session_hours = 720
      auto_redirect = false
    }
    "immich" = {
      name          = "Immich"
      subdomain     = "photos"
      policy_type   = "bypass"
      session_hours = 720
      auto_redirect = false
    }
  }
}

resource "cloudflare_dns_record" "app" {
  for_each = local.dns_apps

  zone_id = var.cloudflare_zone_id
  name    = "${each.value}.${local.base_domain}"
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
  domain     = "${each.value.subdomain}.${local.base_domain}"
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
