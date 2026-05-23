# OpenTofu outputs for Talos VM deployment.

output "node_ips" {
  description = "Static IP addresses assigned to each node"
  value = {
    for node in var.nodes : node.name => node.address
  }
}

output "nodes_info" {
  description = "Node information including IPs and MAC addresses"
  value = {
    for name, details in module.talos.nodes : name => {
      ip                    = [for n in var.nodes : n.address if n.name == name][0]
      mac_address           = details.mac_address
      mac_address_secondary = details.mac_address_secondary
    }
  }
}
