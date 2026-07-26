variable "tailscale_oauth_client_id" {
  type        = string
  description = "Tailscale OAuth client ID for managing ACLs and DNS."
}

variable "tailscale_oauth_client_secret" {
  type        = string
  description = "Tailscale OAuth client secret for managing ACLs and DNS."
  sensitive   = true
}

variable "tailscale_tailnet" {
  type        = string
  description = "Tailnet name, e.g. example.ts.net."
  default     = "koala-dominant.ts.net"
}

variable "tailscale_technitium_primary_dns_server" {
  type        = string
  description = "Primary Technitium DNS server used for Tailscale split DNS."
  default     = "10.0.40.53"
}

variable "tailscale_technitium_secondary_dns_server" {
  type        = string
  description = "Secondary Technitium DNS server used for Tailscale split DNS."
  default     = "10.0.40.54"
}
