# Talos module - creates VMs on Proxmox
# IMPORTANT: Talos image version must match talosctl version
# If talosctl is v1.7.x, use v1.7.x images
# If talosctl is v1.8.x, use v1.8.x images
# Mismatched versions will cause configuration apply failures
#
# Image Types:
# - metal: Standard Talos metal image (default)
# - nocloud: Talos nocloud image for cloud-like environments
# Set talos_image_type variable to switch between image types

terraform {
  required_version = ">= 1.6"
}

# Configure Proxmox provider
provider "proxmox" {
  endpoint  = var.proxmox_endpoint
  insecure  = var.proxmox_insecure
  api_token = "${var.proxmox_token_id}=${var.proxmox_token_secret}"
}

# Download Talos ISO for each unique schematic on each Proxmox node
resource "proxmox_download_file" "talos_iso" {
  for_each = {
    for combo in flatten([
      for node in var.nodes : [
        for schematic in [node.schematic_id] : {
          schematic_id = schematic
          proxmox_node = node.proxmox_node
        }
      ]
    ]) : "${combo.proxmox_node}-${combo.schematic_id}" => combo...
  }

  content_type = "iso"
  datastore_id = "local"
  node_name    = each.value[0].proxmox_node

  url = "https://factory.talos.dev/image/${each.value[0].schematic_id}/${var.talos_version}/${var.talos_image_type}-amd64.iso"

  file_name           = "talos-${each.value[0].schematic_id}.img"
  overwrite           = false
  overwrite_unmanaged = true
}

# Create VMs for each node
resource "proxmox_virtual_environment_vm" "talos_node" {
  for_each = { for node in var.nodes : node.name => node }

  name        = each.value.name
  description = "Talos ${each.value.controller ? "Control Plane" : "Worker"} Node"
  node_name   = each.value.proxmox_node
  vm_id       = each.value.vm_id
  on_boot     = coalesce(each.value.on_boot, each.value.controller)

  cpu {
    cores = each.value.cpu_cores
    type  = "host"
  }

  memory {
    dedicated = each.value.memory_mb
  }

  disk {
    datastore_id = var.storage_pool
    interface    = "scsi0"
    size         = each.value.disk_size_gb
  }

  cdrom {
    file_id   = proxmox_download_file.talos_iso["${each.value.proxmox_node}-${each.value.schematic_id}"].id
    interface = "ide3"
  }

  network_device {
    bridge      = "vmbr0"
    mac_address = each.value.mac_address != "" ? each.value.mac_address : null
    mtu         = each.value.mtu
  }

  network_device {
    bridge  = var.ceph_network.bridge
    vlan_id = var.ceph_network.vlan_id
  }

  boot_order = ["ide3", "scsi0"]

  agent {
    enabled = false
  }

  started = try(each.value.started, true)

  # Cloud-init configuration for static IP
  initialization {
    datastore_id = "local"

    ip_config {
      ipv4 {
        address = "${each.value.address}/${each.value.subnet_mask}"
        gateway = var.gateway
      }
    }

    ip_config {
      ipv4 {
        address = "10.0.${var.ceph_network.vlan_id}.${split(".", each.value.address)[3]}/24"
      }
    }

    dns {
      servers = var.dns_servers
    }

    # Disable cloud-init user creation (Talos manages this)
    user_account {
      username = "talos"
      password = "disabled"
    }
  }

  lifecycle {
    ignore_changes = [disk[0].file_id, cdrom[0].file_id]
  }

  depends_on = [proxmox_download_file.talos_iso]
}

moved {
  from = proxmox_virtual_environment_download_file.talos_iso
  to   = proxmox_download_file.talos_iso
}

# Extract DHCP-assigned IPs directly from VM resources with improved error handling
# The bpg/proxmox provider returns ipv4_addresses as a list of lists
# ipv4_addresses[0] = first network interface, ipv4_addresses[0][0] = first IP on that interface
locals {
  vm_ips = {
    for vm_name, vm in proxmox_virtual_environment_vm.talos_node :
    vm_name => (
      # Check if ipv4_addresses exists and has content
      vm.ipv4_addresses != null &&
      length(vm.ipv4_addresses) > 0 &&
      length(vm.ipv4_addresses[0]) > 0 &&
      vm.ipv4_addresses[0][0] != null &&
      vm.ipv4_addresses[0][0] != ""
      ? vm.ipv4_addresses[0][0]
      : null
    )
  }

  # Additional network interface details for debugging
  vm_network_details = {
    for vm_name, vm in proxmox_virtual_environment_vm.talos_node :
    vm_name => {
      ipv4_addresses       = vm.ipv4_addresses
      ipv6_addresses       = vm.ipv6_addresses
      mac_addresses        = vm.mac_addresses
      network_device_names = vm.network_interface_names
      vm_id                = vm.vm_id
      node_name            = vm.node_name
      # Extract first MAC address if available
      primary_mac = length(vm.mac_addresses) > 0 ? vm.mac_addresses[0] : null
      # Extract first IP if available
      primary_ipv4 = (
        vm.ipv4_addresses != null &&
        length(vm.ipv4_addresses) > 0 &&
        length(vm.ipv4_addresses[0]) > 0
        ? vm.ipv4_addresses[0][0]
        : null
      )
      # Status of DHCP assignment
      dhcp_status = (
        (vm.ipv4_addresses != null && length(vm.ipv4_addresses) > 0 && length(vm.ipv4_addresses[0]) > 0)
        ? "assigned"
        : "pending"
      )
    }
  }

  # Summary for easy access
  ready_nodes = {
    for vm_name, details in local.vm_network_details :
    vm_name => details.primary_ipv4
    if details.primary_ipv4 != null
  }
}
