# Keep Talos VMs in home-dc-kubernetes.

moved {
  from = proxmox_virtual_environment_container.proxmox_pbs_0
  to   = module.proxmox_pbs_0.proxmox_virtual_environment_container.this
}

module "proxmox_pbs_0" {
  source = "./modules/lxc_guest"

  name             = "proxmox-pbs-0"
  node_name        = "pve-0"
  vm_id            = 4016
  description      = "Proxmox Backup Server candidate. Managed by Terraform."
  tags             = ["dns", "pbs", "terraform"]
  root_ssh_keys    = var.root_ssh_public_keys
  template_file_id = "local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst"
  unprivileged     = false
  mount_types      = ["nfs"]

  cpu_cores   = 2
  memory_mb   = 2048
  swap_mb     = 512
  disk_gb     = 16
  ipv4        = "10.0.40.16/24"
  gateway     = "10.0.40.1"
  dns_servers = ["10.0.40.1"]
}
