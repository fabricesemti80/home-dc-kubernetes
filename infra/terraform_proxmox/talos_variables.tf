# OpenTofu variables for Talos VM deployment.
# These variables define the configuration for Proxmox and node provisioning.

# Proxmox API endpoint URL (e.g., "https://192.168.1.100:8006")
variable "proxmox_endpoint" {
  description = "Proxmox API endpoint URL"
  type        = string
}

# Skip TLS verification for Proxmox API (true for self-signed certificates)
variable "proxmox_insecure" {
  description = "Skip TLS verification for Proxmox API"
  type        = bool
  default     = false
}

# Proxmox node name where VMs will be created (e.g., "pve-1")
variable "proxmox_node" {
  description = "Proxmox node name where VMs will be created"
  type        = string
}

# Proxmox API token ID (format: "user@realm!tokenname", e.g., "terraform@pve!terraform")
variable "proxmox_token_id" {
  description = "Proxmox API token ID"
  type        = string
  sensitive   = true
}

# Proxmox API token secret (UUID format)
variable "proxmox_token_secret" {
  description = "Proxmox API token secret"
  type        = string
  sensitive   = true
}

# List of Talos nodes to provision
# Each node requires name, address, controller flag, MAC address, schematic ID, and resource specifications
variable "nodes" {
  description = "List of Talos nodes to provision"
  type = list(object({
    name         = string           # VM name (alphanumeric with hyphens)
    address      = string           # Static IP address (must be in the network CIDR)
    controller   = bool             # true for control plane nodes, false for worker nodes
    started      = optional(bool)   # VM power state in Proxmox (defaults to true)
    on_boot      = optional(bool)   # Proxmox host boot policy; defaults to controller flag
    mac_address  = string           # MAC address (leave empty for auto-generation)
    schematic_id = string           # Talos schematic ID from https://factory.talos.dev/
    cpu_cores    = number           # Number of CPU cores
    memory_mb    = number           # Memory in MB
    disk_size_gb = number           # Disk size in GB
    mtu          = number           # Network MTU (typically 1500)
    vm_id        = optional(number) # Proxmox VM ID (auto-assigned if omitted)
    proxmox_node = optional(string) # Proxmox node name for VM placement (for multi-host distribution)
    subnet_mask  = optional(number) # Subnet mask for static IP (defaults to cidr_prefix if not specified)
  }))

  validation {
    condition = alltrue([
      for node in var.nodes : can(regex("^[a-z0-9-]+$", node.name))
    ])
    error_message = "Node names must contain only lowercase letters, numbers, and hyphens."
  }
}

# Network gateway IP address (e.g., "192.168.1.1")
variable "gateway" {
  description = "Network gateway for the nodes"
  type        = string
}

# CIDR prefix length for the network (e.g., 24 for a /24 network)
variable "cidr_prefix" {
  description = "CIDR prefix length for the network"
  type        = number

  validation {
    condition     = var.cidr_prefix >= 8 && var.cidr_prefix <= 32
    error_message = "CIDR prefix must be between 8 and 32."
  }
}

# Cluster name for Talos
variable "cluster_name" {
  description = "Name of the Talos cluster"
  type        = string
  default     = "talos-cluster"
}

# Talos version
# IMPORTANT: This must match your talosctl version!
# If you have talosctl v1.7.x, use v1.7.x images
# If you have talosctl v1.8.x, use v1.8.x images
# Mismatched versions will cause configuration apply failures
variable "talos_version" {
  description = "Talos version to deploy (must match talosctl version)"
  type        = string
  default     = "v1.12.0"

  validation {
    condition     = can(regex("^v1\\.[0-9]+\\.[0-9]+$", var.talos_version))
    error_message = "Talos version must be in format v1.X.Y (e.g., v1.7.7)"
  }
}

# Kubernetes version
variable "kubernetes_version" {
  description = "Kubernetes version to deploy"
  type        = string
  default     = "v1.35.0"
}

# Cluster API address (VIP or first control plane IP)
variable "cluster_api_addr" {
  description = "Kubernetes API endpoint address"
  type        = string
}

# DNS servers for nodes
variable "dns_servers" {
  description = "DNS servers for the nodes"
  type        = list(string)
  default     = ["1.1.1.1", "1.0.0.1"]
}

# NTP servers for nodes
variable "ntp_servers" {
  description = "NTP servers for the nodes"
  type        = list(string)
  default     = ["time.cloudflare.com"]
}

# Talos image type (metal or nocloud)
variable "talos_image_type" {
  description = "Type of Talos image to use (metal or nocloud)"
  type        = string
  default     = "metal"

  validation {
    condition     = contains(["metal", "nocloud"], var.talos_image_type)
    error_message = "talos_image_type must be either 'metal' or 'nocloud'"
  }
}

# Proxmox storage pool for VM disks
variable "storage_pool" {
  description = "Proxmox storage pool for VM disks"
  type        = string
  default     = "local"
}

# Ceph network configuration (for storage traffic)
variable "ceph_network" {
  description = "Ceph network configuration for storage access"
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
