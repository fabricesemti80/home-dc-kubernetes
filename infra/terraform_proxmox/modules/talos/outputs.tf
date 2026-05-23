# Talos module outputs

output "nodes" {
  description = "Details of all provisioned nodes with current DHCP status"
  value = {
    for node in proxmox_virtual_environment_vm.talos_node :
    node.name => {
      vm_id                 = node.vm_id
      vm_name               = node.name
      dhcp_ipv4_address     = local.vm_ips[node.name]
      node_name             = node.node_name
      mac_address           = length(node.mac_addresses) > 0 ? node.mac_addresses[0] : null
      mac_address_secondary = length(node.mac_addresses) > 1 ? node.mac_addresses[1] : null
      network_details       = local.vm_network_details[node.name]
    }
  }
}

output "control_plane_nodes" {
  description = "Control plane node details with DHCP IPs"
  value = {
    for node in proxmox_virtual_environment_vm.talos_node :
    node.name => {
      vm_id                 = node.vm_id
      vm_name               = node.name
      dhcp_ipv4_address     = local.vm_ips[node.name]
      node_name             = node.node_name
      is_controller         = true
      mac_address           = length(node.mac_addresses) > 0 ? node.mac_addresses[0] : null
      mac_address_secondary = length(node.mac_addresses) > 1 ? node.mac_addresses[1] : null
      network_details       = local.vm_network_details[node.name]
    }
    if[for n in var.nodes : n.controller if n.name == node.name][0] == true
  }
}

output "worker_nodes" {
  description = "Worker node details with DHCP IPs"
  value = {
    for node in proxmox_virtual_environment_vm.talos_node :
    node.name => {
      vm_id                 = node.vm_id
      vm_name               = node.name
      dhcp_ipv4_address     = local.vm_ips[node.name]
      node_name             = node.node_name
      is_controller         = false
      mac_address           = length(node.mac_addresses) > 0 ? node.mac_addresses[0] : null
      mac_address_secondary = length(node.mac_addresses) > 1 ? node.mac_addresses[1] : null
      network_details       = local.vm_network_details[node.name]
    }
    if[for n in var.nodes : n.controller if n.name == node.name][0] == false
  }
}

output "vm_dhcp_ipv4_addresses" {
  description = "Current DHCP-assigned IPv4 addresses for all VMs (may be empty if VMs are still booting)"
  value       = local.vm_ips
}

output "ready_nodes_with_ips" {
  description = "Nodes that have successfully obtained DHCP addresses (ready for Talos configuration)"
  value       = local.ready_nodes
}

output "vm_network_details" {
  description = "Detailed network information for debugging DHCP assignment"
  value       = local.vm_network_details
}

output "cluster_node_ips_summary" {
  description = "Summary of node DHCP IPs for cluster configuration (empty if VMs still booting)"
  value = {
    control_plane_ips = [
      for node in proxmox_virtual_environment_vm.talos_node :
      local.vm_ips[node.name]
      if[for n in var.nodes : n.controller if n.name == node.name][0] == true &&
      local.vm_ips[node.name] != null
    ]
    worker_ips = [
      for node in proxmox_virtual_environment_vm.talos_node :
      local.vm_ips[node.name]
      if[for n in var.nodes : n.controller if n.name == node.name][0] == false &&
      local.vm_ips[node.name] != null
    ]
    all_ips = [
      for node in proxmox_virtual_environment_vm.talos_node :
      local.vm_ips[node.name]
      if local.vm_ips[node.name] != null
    ]
    total_nodes        = length(proxmox_virtual_environment_vm.talos_node)
    nodes_with_ips     = length([for ip in local.vm_ips : ip if ip != null])
    nodes_pending_dhcp = length(proxmox_virtual_environment_vm.talos_node) - length([for ip in local.vm_ips : ip if ip != null])
  }
}

output "next_steps_for_cluster_config" {
  description = "Instructions for getting DHCP IPs after VMs have booted"
  value = {
    current_status = "VMs created but may still be booting. DHCP IPs will appear once VMs are fully started."
    steps = [
      "1. Wait 2-3 minutes for VMs to fully boot and obtain DHCP addresses",
      "2. Run: tofu refresh",
      "3. Run: tofu output ready_nodes_with_ips",
      "4. Or run: tofu output cluster_node_ips_summary",
      "5. Use the obtained IPs in your Talos machine configuration"
    ]
    quick_commands = {
      get_all_ips        = "tofu output vm_dhcp_ipv4_addresses"
      get_ready_nodes    = "tofu output ready_nodes_with_ips"
      get_summary        = "tofu output cluster_node_ips_summary"
      get_control_planes = "tofu output control_plane_nodes"
    }
  }
}
