module "vm" {
  # Symlink proxmox-vm-module → commissioner terraform/modules/proxmox-vm (refreshed by scripts).
  source = "./proxmox-vm-module"

  proxmox_node = var.proxmox_node

  vm_name      = var.vm_name
  vm_id        = var.vm_id
  vm_cores     = var.vm_cores
  vm_sockets   = var.vm_sockets
  vm_memory    = var.vm_memory
  vm_disk_size = var.vm_disk_size

  template_id = var.template_id
  clone_full  = var.clone_full

  datastore_disk      = var.datastore_disk
  datastore_snippets  = var.datastore_snippets
  datastore_cloudinit = var.datastore_cloudinit
  disk_interface      = var.disk_interface
  disk_discard        = var.disk_discard
  disk_format         = var.disk_format

  network_bridge  = var.network_bridge
  network_model   = var.network_model
  network_vlan_id = var.network_vlan_id
  network_mode    = var.network_mode
  network_ip      = var.network_ip
  network_gateway = var.network_gateway

  enable_qemu_agent = var.enable_qemu_agent
  package_update    = var.package_update
  package_upgrade   = var.package_upgrade
  ssh_pwauth        = var.ssh_pwauth
  disable_root               = var.disable_root
  root_password              = var.root_password
  ssh_public_key             = var.ssh_public_key
  remove_distro_cloud_user   = var.remove_distro_cloud_user
}
