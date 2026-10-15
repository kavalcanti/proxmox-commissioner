provider "proxmox" {
  endpoint  = var.proxmox_endpoint
  api_token = var.proxmox_api_token
  insecure  = var.proxmox_insecure

  ssh {
    agent    = true
    username = var.proxmox_ssh_user

    dynamic "node" {
      for_each = var.nodes
      content {
        name    = node.key
        address = node.value
      }
    }
  }
}
