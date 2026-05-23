variable "management_vm_enabled" {
  description = "Whether to create the standalone management VM"
  type        = bool
  default     = false
}

variable "management_vm_name" {
  description = "Management VM name"
  type        = string
  default     = "deep-thought-01"
}

variable "management_vm_description" {
  description = "Management VM description"
  type        = string
  default     = "Terraform managed management VM"
}

variable "management_vm_target_node" {
  description = "Proxmox node where the management VM should run"
  type        = string
  default     = "pve-2"
}

variable "management_vm_id" {
  description = "Proxmox VM ID for the management VM"
  type        = number
  default     = 4100
}

variable "management_vm_template_id" {
  description = "Proxmox template VM ID used to clone the management VM"
  type        = number
  default     = 9008
}

variable "management_vm_ipv4_address" {
  description = "Static IPv4 address for the management VM"
  type        = string
  default     = "10.0.40.100"
}

variable "management_vm_cidr_prefix" {
  description = "CIDR prefix length for the management VM IP"
  type        = number
  default     = 24
}

variable "management_vm_cpu_cores" {
  description = "CPU cores assigned to the management VM"
  type        = number
  default     = 4
}

variable "management_vm_memory_mb" {
  description = "Dedicated memory assigned to the management VM in MB"
  type        = number
  default     = 8192
}

variable "management_vm_disk_size_gb" {
  description = "Primary disk size for the management VM in GB"
  type        = number
  default     = 80
}

variable "management_vm_bridge" {
  description = "Primary network bridge for the management VM"
  type        = string
  default     = "vmbr0"
}

variable "management_vm_username" {
  description = "Primary operating system user for the management VM"
  type        = string
  default     = "fs"
}

variable "management_vm_dns_servers" {
  description = "DNS servers configured via cloud-init for the management VM"
  type        = list(string)
  default     = ["1.1.1.1", "1.0.0.1"]
}

variable "management_vm_authorized_key_paths" {
  description = "Local public key paths to authorize for the management VM user"
  type        = list(string)
  default = [
    "~/.ssh/id_macbook_fs.pub",
    "~/.ssh/fs_home_rsa.pub",
  ]
}
