locals {
  agent_ips = flatten([
    for interface in proxmox_virtual_environment_vm.this.ipv4_addresses : [
      for ip in interface : ip if !startswith(ip, "127.")
    ]
  ])
}

output "vm_id" {
  value = proxmox_virtual_environment_vm.this.vm_id
}

output "vm_name" {
  value = proxmox_virtual_environment_vm.this.name
}

output "vm_node" {
  value = proxmox_virtual_environment_vm.this.node_name
}

output "vm_ip" {
  description = "Static address, or the first address reported by the guest agent"
  value       = local.static_ip != "" ? local.static_ip : try(local.agent_ips[0], "")
}

output "vm_mac_address" {
  value = try(proxmox_virtual_environment_vm.this.mac_addresses[0], "")
}
