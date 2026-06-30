# Talos module variables

variable "cluster_name" {
  description = "Name of the Talos cluster"
  type        = string
}

variable "talos_version" {
  description = "Talos version to deploy"
  type        = string
  default     = "v1.12.0"
}

variable "talos_image_type" {
  description = "Type of Talos image to use (metal or nocloud)"
  type        = string
  default     = "metal"
  validation {
    condition     = contains(["metal", "nocloud"], var.talos_image_type)
    error_message = "talos_image_type must be either 'metal' or 'nocloud'"
  }
}

variable "kubernetes_version" {
  description = "Kubernetes version to deploy"
  type        = string
  default     = "v1.35.0"
}

variable "nodes" {
  description = "List of nodes to create"
  type = list(object({
    name         = string
    address      = string
    controller   = bool
    started      = optional(bool, true)
    on_boot      = optional(bool)
    schematic_id = string
    proxmox_node = string
    vm_id        = number
    cpu_cores    = number
    memory_mb    = number
    disk_size_gb = number
    mac_address  = optional(string, "")
    mtu          = optional(number, 1500)
    subnet_mask  = optional(number, 24)
  }))
}

variable "cluster_endpoint" {
  description = "Kubernetes API endpoint (VIP or first control plane IP)"
  type        = string
}

variable "gateway" {
  description = "Network gateway"
  type        = string
}

variable "cidr_prefix" {
  description = "CIDR prefix length"
  type        = number
}

variable "dns_servers" {
  description = "DNS servers"
  type        = list(string)
  default     = ["1.1.1.1", "1.0.0.1"]
}

variable "ntp_servers" {
  description = "NTP servers"
  type        = list(string)
  default     = ["time.cloudflare.com"]
}

variable "proxmox_endpoint" {
  description = "Proxmox API endpoint"
  type        = string
}

variable "proxmox_insecure" {
  description = "Skip TLS verification for Proxmox"
  type        = bool
  default     = true
}

variable "proxmox_token_id" {
  description = "Proxmox API token ID"
  type        = string
  sensitive   = true
}

variable "proxmox_token_secret" {
  description = "Proxmox API token secret"
  type        = string
  sensitive   = true
}

variable "storage_pool" {
  description = "Proxmox storage pool for VM disks"
  type        = string
  default     = "local"
}

variable "ceph_network" {
  description = "Ceph network configuration for storage traffic"
  type = object({
    vlan_id      = number
    network_cidr = string
    bridge       = string
  })
  default = {
    vlan_id      = 70
    network_cidr = "10.0.70.0/24"
    bridge       = "vmbr0"
  }
}
