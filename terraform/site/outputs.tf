output "images" {
  description = "node/image => volume id"
  value       = { for key, file in proxmox_download_file.image : key => file.id }
}

output "pci_mappings" {
  description = "mapping name => id"
  value       = { for name, mapping in proxmox_hardware_mapping_pci.this : name => mapping.id }
}
