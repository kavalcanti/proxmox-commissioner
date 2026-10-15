locals {
  use_dhcp  = var.network_ip == ""
  static_ip = local.use_dhcp ? "" : split("/", var.network_ip)[0]
}

resource "proxmox_virtual_environment_vm" "this" {
  name        = var.vm_name
  description = "Managed by proxmox-commissioner"
  tags        = sort(var.tags)
  node_name   = var.proxmox_node
  vm_id       = var.vm_id

  # Changing node_name live-migrates the VM instead of recreating it.
  migrate = true

  started = true

  agent {
    enabled = var.enable_qemu_agent

    # With DHCP the address is only known once the guest agent reports it.
    dynamic "wait_for_ip" {
      for_each = var.enable_qemu_agent && local.use_dhcp ? [1] : []
      content {
        ipv4 = true
      }
    }
  }

  cpu {
    cores   = var.vm_cores
    sockets = var.vm_sockets
    type    = "host"
  }

  memory {
    dedicated = var.vm_memory
  }

  # The disk is imported straight from the cloud image downloaded by terraform/site,
  # so no template VM has to exist on the node.
  disk {
    datastore_id = var.datastore_disk
    file_id      = var.image_file_id
    interface    = var.disk_interface
    size         = var.vm_disk_size
    discard      = var.disk_discard
    file_format  = var.disk_format
  }

  initialization {
    datastore_id = var.datastore_cloudinit

    ip_config {
      ipv4 {
        address = local.use_dhcp ? "dhcp" : var.network_ip
        gateway = local.use_dhcp ? null : var.network_gateway
      }
    }

    dynamic "dns" {
      for_each = length(var.nameservers) > 0 ? [1] : []
      content {
        servers = var.nameservers
      }
    }

    user_data_file_id = proxmox_virtual_environment_file.cloud_config.id
  }

  network_device {
    bridge  = var.network_bridge
    model   = var.network_model
    vlan_id = var.network_vlan_id > 0 ? var.network_vlan_id : null
  }

  operating_system {
    type = "l26"
  }

  boot_order = [var.disk_interface]

  serial_device {}
}

# Cloud-init makes the VM boot already hardened: key-only SSH on the final port,
# root locked, and a sudo user for Ansible. There is no insecure bootstrap phase.
resource "proxmox_virtual_environment_file" "cloud_config" {
  node_name    = var.proxmox_node
  content_type = "snippets"
  datastore_id = var.datastore_snippets

  source_raw {
    data = templatefile("${path.module}/templates/user_data.yaml.tftpl", {
      hostname             = var.vm_name
      devops_user          = var.devops_user
      devops_password_hash = var.devops_password_hash
      ssh_public_key       = var.ssh_public_key
      ssh_port             = var.ssh_port
      package_update       = var.package_update
      package_upgrade      = var.package_upgrade
      remove_distro_user   = var.remove_distro_cloud_user
    })

    file_name = "cloud-init-${var.vm_name}.yaml"
  }
}
