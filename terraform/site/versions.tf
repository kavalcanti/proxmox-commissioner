terraform {
  required_version = ">= 1.5"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.116"
    }
  }

  # Partial configuration: pvc passes the state path (.pvc/site/terraform.tfstate).
  backend "local" {}
}
