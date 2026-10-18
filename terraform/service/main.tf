module "vm" {
  source   = "../modules/proxmox-vm"
  for_each = var.hosts

  proxmox_node = each.value.node
  vm_name      = each.value.name
  vm_id        = each.value.vm_id
  tags         = concat(["pvc", var.service_name], each.value.roles)

  vm_cores     = each.value.cores
  vm_sockets   = each.value.sockets
  vm_memory    = each.value.memory
  vm_disk_size = each.value.disk
  vm_machine   = each.value.machine == "" ? null : each.value.machine
  pci_devices  = each.value.pci_devices

  image_file_id       = each.value.image_file_id
  datastore_disk      = var.storage.disk
  datastore_snippets  = var.storage.snippets
  datastore_cloudinit = var.storage.cloudinit
  disk_interface      = var.vm_options.disk_interface
  disk_discard        = var.vm_options.disk_discard
  disk_format         = var.vm_options.disk_format

  network_bridge  = each.value.bridge
  network_model   = each.value.model
  network_mac     = each.value.mac == "" ? null : each.value.mac
  network_vlan_id = each.value.vlan
  network_ip      = each.value.ip
  network_gateway = each.value.gateway == "" ? null : each.value.gateway
  nameservers     = each.value.nameservers

  enable_qemu_agent = var.vm_options.qemu_agent
  package_update    = var.vm_options.package_update
  package_upgrade   = var.vm_options.package_upgrade

  devops_user          = var.devops_user
  devops_password_hash = var.devops_password_hash
  ssh_public_key       = var.ssh_public_key
  ssh_port             = var.ssh_port
}
