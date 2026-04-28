terraform {
  required_providers {
    talos = {
      source  = "siderolabs/talos"
      version = "~> 0.7"
    }
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.104"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}
