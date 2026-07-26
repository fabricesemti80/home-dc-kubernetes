resource "proxmox_virtual_environment_container" "this" {
  node_name   = var.node_name
  vm_id       = var.vm_id
  description = var.description
  tags        = var.tags

  started      = var.started
  unprivileged = var.unprivileged

  cpu {
    cores = var.cpu_cores
  }

  memory {
    dedicated = var.memory_mb
    swap      = var.swap_mb
  }

  disk {
    datastore_id = var.disk_datastore_id
    size         = var.disk_gb
  }

  dynamic "mount_point" {
    for_each = var.mount_points
    content {
      volume = mount_point.value.volume
      path   = mount_point.value.path
    }
  }

  features {
    nesting = var.nesting
    mount   = var.mount_types
  }

  initialization {
    hostname = var.name

    dns {
      servers = var.dns_servers
    }

    ip_config {
      ipv4 {
        address = var.ipv4
        gateway = var.gateway
      }
    }

    user_account {
      keys = var.root_ssh_keys
    }
  }

  network_interface {
    name    = "eth0"
    bridge  = var.bridge
    vlan_id = var.vlan_id
  }

  operating_system {
    template_file_id = var.template_file_id
    type             = var.os_type
  }

  startup {
    order      = var.startup_order
    up_delay   = var.startup_up_delay
    down_delay = var.startup_down_delay
  }

  lifecycle {
    ignore_changes = [
      description,
      tags,
      started,
      initialization,
      network_interface,
      mount_point,
      operating_system,
    ]
  }
}
