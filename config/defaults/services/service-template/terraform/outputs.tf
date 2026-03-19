output "vm_id" {
  description = "The ID of the created VM"
  value       = module.vm.vm_id
}

output "vm_name" {
  description = "The name of the created VM"
  value       = module.vm.vm_name
}

output "vm_ip" {
  description = "The primary IP address of the VM"
  value       = module.vm.vm_ip
}

output "vm_node" {
  description = "The Proxmox node the VM is running on"
  value       = module.vm.vm_node
}

output "vm_mac_address" {
  description = "The MAC address of the VM's primary network interface"
  value       = module.vm.vm_mac_address
}

output "vm_status" {
  description = "The current status of the VM"
  value       = module.vm.vm_status
}

output "ansible_connection_info" {
  description = "Connection information for Ansible inventory"
  value       = module.vm.ansible_connection_info
}
