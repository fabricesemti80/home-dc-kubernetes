variable "proxmox_endpoint" {
  type        = string
  description = "Proxmox API endpoint."
}

variable "proxmox_insecure" {
  type        = bool
  description = "Allow self-signed Proxmox TLS certificates."
  default     = true
}

variable "proxmox_token_id" {
  type        = string
  description = "Proxmox API token ID."
  sensitive   = true
}

variable "proxmox_token_secret" {
  type        = string
  description = "Proxmox API token secret."
  sensitive   = true
}

variable "root_ssh_public_keys" {
  type        = list(string)
  description = "SSH public keys to install for root in managed guests."
  default     = []
}
