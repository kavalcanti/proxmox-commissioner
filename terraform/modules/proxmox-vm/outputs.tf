output "vm_id" {
  description = "The ID of the created VM"
  value       = proxmox_virtual_environment_vm.debian_vm.vm_id
}

output "vm_name" {
  description = "The name of the created VM"
  value       = proxmox_virtual_environment_vm.debian_vm.name
}

output "vm_ip" {
  description = "The primary IP address of the VM"
  value = try(
    [for ip in proxmox_virtual_environment_vm.debian_vm.ipv4_addresses[1] : ip if ip != "127.0.0.1"][0],
    "waiting for IP..."
  )
}

output "vm_node" {
  description = "The Proxmox node the VM is running on"
  value       = proxmox_virtual_environment_vm.debian_vm.node_name
}

output "vm_mac_address" {
  description = "The MAC address of the VM's primary network interface"
  value       = proxmox_virtual_environment_vm.debian_vm.mac_addresses[0]
}

output "vm_status" {
  description = "The current status of the VM"
  value       = proxmox_virtual_environment_vm.debian_vm.started ? "running" : "stopped"
}

output "ansible_connection_info" {
  description = "Connection information for Ansible inventory"
  value = {
    ansible_host = try(proxmox_virtual_environment_vm.debian_vm.ipv4_addresses[1][0], "")
    ansible_user = "root"
    ansible_port = 22
    sys_hostname = var.vm_name
  }
  sensitive = false
}
