terraform {
  required_providers {
    talos = {
      source  = "siderolabs/talos"
      version = "~> 0.12"
    }
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.115"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}
