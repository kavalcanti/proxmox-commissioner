resource "proxmox_virtual_environment_vm" "debian_vm" {
  name      = var.vm_name
  node_name = var.proxmox_node
  vm_id     = var.vm_id

  clone {
    vm_id = var.template_id
    full  = var.clone_full
  }

  started = true

  agent {
    enabled = var.enable_qemu_agent
  }

  cpu {
    cores   = var.vm_cores
    sockets = var.vm_sockets
  }

  memory {
    dedicated = var.vm_memory
  }

  disk {
    datastore_id = var.datastore_disk
    interface    = var.disk_interface
    size         = var.vm_disk_size
    discard      = var.disk_discard
    file_format  = var.disk_format
  }

  initialization {
    datastore_id = var.datastore_cloudinit

    ip_config {
      ipv4 {
        address = var.network_mode == "dhcp" ? "dhcp" : var.network_ip
        gateway = var.network_mode == "static" ? var.network_gateway : null
      }
    }

    user_data_file_id = proxmox_virtual_environment_file.cloud_config.id
  }

  network_device {
    bridge  = var.network_bridge
    model   = var.network_model
    vlan_id = var.network_vlan_id > 0 ? var.network_vlan_id : null
  }

  boot_order = [var.disk_interface]

  serial_device {}
}

resource "proxmox_virtual_environment_file" "cloud_config" {
  node_name    = var.proxmox_node
  content_type = "snippets"
  datastore_id = var.datastore_snippets

  source_raw {
    data = templatefile("${path.module}/templates/user_data.yaml.tftpl", {
      root_password   = var.root_password
      ssh_pwauth      = var.ssh_pwauth
      disable_root    = var.disable_root
      package_update  = var.package_update
      package_upgrade = var.package_upgrade
    })

    file_name = "cloud-init-${var.vm_name}.yaml"
  }
}
