locals {
  management_vm_authorized_keys = [
    for key_path in var.management_vm_authorized_key_paths :
    trimspace(file(pathexpand(key_path)))
  ]
}

resource "proxmox_virtual_environment_vm" "management_vm" {
  count = var.management_vm_enabled ? 1 : 0

  name        = var.management_vm_name
  description = var.management_vm_description
  node_name   = var.management_vm_target_node
  vm_id       = var.management_vm_id

  clone {
    vm_id = var.management_vm_template_id
    full  = true
  }

  agent {
    enabled = false
    timeout = "5m"
  }

  cpu {
    cores   = var.management_vm_cpu_cores
    sockets = 1
    type    = "host"
  }

  memory {
    dedicated = var.management_vm_memory_mb
  }

  disk {
    datastore_id = var.storage_pool
    interface    = "virtio0"
    size         = var.management_vm_disk_size_gb
    iothread     = true
  }

  network_device {
    bridge = var.management_vm_bridge
    model  = "virtio"
  }

  initialization {
    datastore_id = var.storage_pool

    ip_config {
      ipv4 {
        address = "${var.management_vm_ipv4_address}/${var.management_vm_cidr_prefix}"
        gateway = var.gateway
      }
    }

    dns {
      servers = var.management_vm_dns_servers
    }

    user_account {
      username = var.management_vm_username
      keys     = local.management_vm_authorized_keys
    }
  }

  started = true
}
