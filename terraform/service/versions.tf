terraform {
  required_version = ">= 1.5"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.116"
    }
  }

  # Partial configuration: pvc passes `-backend-config=path=services/<svc>/.pvc/terraform.tfstate`
  # so every service keeps its own state while sharing this root module.
  backend "local" {}
}
