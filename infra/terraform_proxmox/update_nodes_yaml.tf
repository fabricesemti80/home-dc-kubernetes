resource "null_resource" "update_nodes_yaml" {
  triggers = {
    # Re-run if any node IP or MAC changes
    nodes_info = jsonencode({
      for name, details in module.talos.nodes : name => {
        ip          = [for n in var.nodes : n.address if n.name == name][0]
        mac_address = details.mac_address
      }
    })
  }

  provisioner "local-exec" {
    command = "${path.module}/update_nodes.sh"
    environment = {
      NODES_JSON = jsonencode({
        for name, details in module.talos.nodes : name => {
          ip          = [for n in var.nodes : n.address if n.name == name][0]
          mac_address = details.mac_address
        }
      })
      NODES_YAML = abspath("${path.root}/../../nodes.yaml")
    }
    interpreter = ["/bin/bash", "-c"]
  }

  depends_on = [module.talos]
}
