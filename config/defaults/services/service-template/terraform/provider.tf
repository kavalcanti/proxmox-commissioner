provider "proxmox" {
  endpoint  = var.proxmox_endpoint
  api_token = var.proxmox_api_token
  insecure  = true

  ssh {
    agent    = true
    username = var.proxmox_ssh_user
    node {
      name    = var.proxmox_node
      address = var.proxmox_node_ip
    }
  }
}
