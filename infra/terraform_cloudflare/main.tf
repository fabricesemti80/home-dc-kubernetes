provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

provider "doppler" {
  doppler_token = var.doppler_token
}

data "doppler_secrets" "cloudflare" {
  count = var.doppler_token != "" ? 1 : 0

  config  = "dev_homelab"
  project = "project-homelab"
}

resource "random_id" "kubernetes_tunnel_secret" {
  byte_length = 35
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "kubernetes" {
  account_id    = var.cloudflare_account_id
  name          = var.kubernetes_tunnel_name
  tunnel_secret = local.kubernetes_tunnel_secret

  lifecycle {
    ignore_changes = [tunnel_secret]
  }
}

resource "local_file" "kubernetes_tunnel_credentials" {
  count = var.doppler_token != "" ? 1 : 0

  content  = local.kubernetes_tunnel_credentials_json
  filename = pathexpand("${path.module}/../../cloudflare-tunnel.json")
}

resource "doppler_secret" "kubernetes_tunnel_credentials" {
  count = var.doppler_token != "" ? 1 : 0

  config     = "dev_homelab"
  project    = "project-homelab"
  name       = "TUNNEL_CREDENTIALS"
  value      = local.kubernetes_tunnel_credentials_json
  value_type = "json"
}

resource "doppler_secret" "kubernetes_tunnel_id" {
  count = var.doppler_token != "" ? 1 : 0

  config  = "dev_homelab"
  project = "project-homelab"
  name    = "TUNNEL_ID"
  value   = local.kubernetes_tunnel_id
}

resource "doppler_secret" "kubernetes_tunnel_token" {
  count = var.doppler_token != "" ? 1 : 0

  config  = "dev_homelab"
  project = "project-homelab"
  name    = "TUNNEL_TOKEN"
  value   = local.kubernetes_tunnel_token
}

resource "cloudflare_zero_trust_access_policy" "argo_webhook_bypass" {
  account_id       = var.cloudflare_account_id
  name             = "Argo Webhook Bypass"
  decision         = "bypass"
  session_duration = "30m"

  include = [
    {
      everyone = {}
    }
  ]
}

resource "cloudflare_zero_trust_access_application" "argo_webhook" {
  account_id                 = var.cloudflare_account_id
  name                       = "Argo Webhook"
  domain                     = "argo.krapulax.dev/api/webhook"
  type                       = "self_hosted"
  http_only_cookie_attribute = false
  session_duration           = "30m"
  skip_interstitial          = true
  auto_redirect_to_identity  = false

  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.argo_webhook_bypass.id
      precedence = 1
    }
  ]
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "trinity" {
  count = 1

  account_id    = var.cloudflare_account_id
  name          = "trinity"
  tunnel_secret = null
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

resource "cloudflare_dns_record" "kubernetes_app" {
  for_each = local.kubernetes_dns_apps

  zone_id = var.cloudflare_zone_id
  name    = "${each.value}.${local.base_domain}"
  content = "external.${local.base_domain}"
  type    = "CNAME"
  proxied = true
  ttl     = 1
}

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

moved {
  from = random_id.tunnel_secret
  to   = random_id.kubernetes_tunnel_secret
}

moved {
  from = cloudflare_zero_trust_tunnel_cloudflared.tunnel
  to   = cloudflare_zero_trust_tunnel_cloudflared.kubernetes
}

moved {
  from = local_file.credentials
  to   = local_file.kubernetes_tunnel_credentials
}

moved {
  from = doppler_secret.tunnel_credentials
  to   = doppler_secret.kubernetes_tunnel_credentials
}

moved {
  from = doppler_secret.tunnel_id
  to   = doppler_secret.kubernetes_tunnel_id
}

moved {
  from = doppler_secret.tunnel_token
  to   = doppler_secret.kubernetes_tunnel_token
}
