terraform {
  required_providers {
    talos = {
      source  = "siderolabs/talos"
      version = "~> 0.11"
    }
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.40"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}
