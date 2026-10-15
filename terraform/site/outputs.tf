output "images" {
  description = "node/image => volume id"
  value       = { for key, file in proxmox_download_file.image : key => file.id }
}
