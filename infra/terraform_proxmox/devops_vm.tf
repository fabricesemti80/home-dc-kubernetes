# locals {
#   # SSH Keys from reference configuration
#   ssh_public_key_rsa     = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCpjSKK4qiMx4vIOvX7PHBOOctpYQ/XQQKWinw+v8oIQoI3GWkdRTwZpXJ2QSor/10zk5TZphP6XpfXxJj3caPwZPnu/ZFci/Iy40T6O2PDUFBjzaBLoIRci4lkRgjyEITKt9K1gIiqO8CnrMNBQTYj8gt7pHa3jIv102M1JIVqq4IU6tDTnf6Nku20jQcvxQCuJT0AszLZwMsD8IMOPkOfztnYOeJTXKOvcT+Vff3+ORXtXbVXNvAhobiSdK1MH5dAMsDZs9QcAazJGMfp50BcBUiHCRUo2XRk+IjMt7Tj6EjI+IMy+QOQWvTM016X9xTiLrPEJMU2RatfeG9VvcCPeQxPCbQE7uuYvCa3SAeJ3CTSL6kTE/4gp4uIq/XZEgZZO/4vuWF+1cNRYhePyJm9tlIU1o5AHHL2I8FJUlQJAe/+gRd/irfzRGDhiYw3fa02nFXsPY4mlEjIdjAd7JYRv1D3X2LBS+62PjqRC3NoNLodfywd3pVsiO3l3QsQKMRGxbyA9jSelSORNftGNeIQJWgJXW0ws42aCYmdcarCpLIil5QfV3WSfXz+a+wd5y7OCW19+sl3j1RHJhIuttsAZQOIGisCfDgstxhY08yuqA2DcZCdNL50JJzN2AQyeVzGRNEhFFEELBdRMAOf7L61Qie3Y+s9aN0do0xDInOkYQ== fs@home"
#   ssh_public_key_ed25519 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDZNMQ9ZBT1pxZCjNHGI9fE3MaFJPy8gOfOjrA+PclVk fs@Fabrices-MBP"
# }

# resource "proxmox_virtual_environment_vm" "devops_srv_0" {
#   name        = "devops-srv-0"
#   description = "Terraform Managed DevOps VM"
#   node_name   = "pve-0"
#   vm_id       = 4020

#   clone {
#     vm_id = 9008
#     full  = true
#   }

#   agent {
#     enabled = true
#     timeout = "5m"
#   }

#   cpu {
#     cores   = 4
#     sockets = 1
#     type    = "host"
#   }

#   memory {
#     dedicated = 16384
#   }

#   disk {
#     datastore_id = "ceph-proxmox-rbd"
#     interface    = "virtio0"
#     size         = 60
#     iothread     = true
#   }

#   network_device {
#     bridge = "vmbr0"
#     model  = "virtio"
#   }

#   initialization {
#     datastore_id = "ceph-proxmox-rbd"

#     ip_config {
#       ipv4 {
#         address = "10.0.40.20/24"
#         gateway = "10.0.40.1"
#       }
#     }

#     dns {
#       servers = ["9.9.9.9", "149.112.112.112"]
#     }

#     user_account {
#       username = "fs"
#       keys = [
#         local.ssh_public_key_rsa,
#         local.ssh_public_key_ed25519
#       ]
#     }
#   }

#   started = true

#   # Enabled based on reference config (efi_disk_enabled = true, tpm_state_enabled = true)
#   efi_disk {
#     datastore_id = "ceph-proxmox-rbd"
#     type         = "4m"
#   }

#   tpm_state {
#     datastore_id = "ceph-proxmox-rbd"
#     version      = "v2.0"
#   }
# }
