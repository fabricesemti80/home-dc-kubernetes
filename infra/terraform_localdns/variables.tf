variable "unifi_username" {
  description = "UniFi local API username."
  type        = string
  sensitive   = true
}

variable "unifi_password" {
  description = "UniFi local API password."
  type        = string
  sensitive   = true
}

variable "unifi_api_url" {
  description = "UniFi Network API URL."
  type        = string
  sensitive   = true
}

variable "unifi_allow_insecure" {
  description = "Allow self-signed TLS certificates when connecting to UniFi."
  type        = bool
  default     = true
}

locals {
  internal_domain = "krapulax.home"

  kubernetes_internal_gateway_ip = "10.0.40.102"
}
