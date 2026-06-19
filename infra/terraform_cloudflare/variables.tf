variable "cloudflare_api_token" {
  description = "Cloudflare API token."
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID."
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for krapulax.dev."
  type        = string
  sensitive   = true
}

variable "kubernetes_tunnel_name" {
  description = "Cloudflare tunnel name used by the Kubernetes cloudflared deployment."
  type        = string
  default     = "kubernetes"
}

variable "tunnel_secret" {
  description = "Optional pre-existing Kubernetes tunnel secret."
  type        = string
  sensitive   = true
  default     = ""
}

variable "doppler_token" {
  description = "Doppler token used to publish generated Cloudflare tunnel material."
  type        = string
  sensitive   = true
  default     = ""
}

locals {
  base_domain = "krapulax.dev"

  kubernetes_tunnel_secret = var.tunnel_secret != "" ? var.tunnel_secret : random_id.kubernetes_tunnel_secret.b64_std
  kubernetes_tunnel_id     = cloudflare_zero_trust_tunnel_cloudflared.kubernetes.id
  kubernetes_account_tag   = var.cloudflare_account_id
  kubernetes_tunnel_token = base64encode(jsonencode({
    a = var.cloudflare_account_id
    t = local.kubernetes_tunnel_id
    s = local.kubernetes_tunnel_secret
  }))
  kubernetes_tunnel_credentials_json = jsonencode({
    AccountTag   = local.kubernetes_account_tag
    TunnelID     = local.kubernetes_tunnel_id
    TunnelSecret = local.kubernetes_tunnel_secret
    TunnelName   = var.kubernetes_tunnel_name
  })

  dns_apps = {
    "arcane"    = "arcane"
    "beszel"    = "beszel"
    "uptime"    = "uptime"
    "whoami"    = "whoami"
    "portainer" = "portainer"
    "kestra"    = "kestra"
  }

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
    "n8n" = {
      name          = "n8n"
      subdomain     = "n8n"
      policy_type   = "allow"
      session_hours = 24
      auto_redirect = false
    }
    "kestra" = {
      name          = "Kestra"
      subdomain     = "kestra"
      policy_type   = "allow"
      session_hours = 24
      auto_redirect = false
    }
  }
}
