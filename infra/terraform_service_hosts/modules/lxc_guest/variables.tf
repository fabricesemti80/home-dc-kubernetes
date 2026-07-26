variable "name" {
  type = string
}

variable "node_name" {
  type = string
}

variable "vm_id" {
  type = number
}

variable "description" {
  type    = string
  default = "Managed by Terraform."
}

variable "tags" {
  type    = list(string)
  default = ["terraform"]
}

variable "started" {
  type    = bool
  default = true
}

variable "unprivileged" {
  type    = bool
  default = true
}

variable "cpu_cores" {
  type    = number
  default = 1
}

variable "memory_mb" {
  type    = number
  default = 512
}

variable "swap_mb" {
  type    = number
  default = 0
}

variable "disk_datastore_id" {
  type    = string
  default = "local"
}

variable "disk_gb" {
  type    = number
  default = 8
}

variable "nesting" {
  type    = bool
  default = true
}

variable "mount_types" {
  type    = list(string)
  default = []
}

variable "mount_points" {
  type = list(object({
    volume = string
    path   = string
  }))
  default = []
}

variable "dns_servers" {
  type    = list(string)
  default = []
}

variable "ipv4" {
  type = string
}

variable "gateway" {
  type = string
}

variable "root_ssh_keys" {
  type    = list(string)
  default = []
}

variable "bridge" {
  type    = string
  default = "vmbr0"
}

variable "vlan_id" {
  type    = number
  default = null
}

variable "template_file_id" {
  type = string
}

variable "os_type" {
  type    = string
  default = "debian"
}

variable "startup_order" {
  type    = string
  default = "2"
}

variable "startup_up_delay" {
  type    = string
  default = "30"
}

variable "startup_down_delay" {
  type    = string
  default = "30"
}
