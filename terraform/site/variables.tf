variable "proxmox_endpoint" {
  type = string
}

variable "proxmox_api_token" {
  type      = string
  sensitive = true
}

variable "proxmox_insecure" {
  type    = bool
  default = true
}

variable "proxmox_ssh_user" {
  type    = string
  default = "root"
}

variable "nodes" {
  description = "Proxmox node name => address"
  type        = map(string)
}

variable "images_datastore" {
  description = "Datastore with the iso content type enabled"
  type        = string
}

variable "images" {
  description = "Image name => download URL"
  type        = map(string)
}

variable "pci_mappings" {
  description = "Datacenter PCI resource mappings: name => per-node device. Empty string / -1 mean unset."
  type = map(object({
    comment = string
    nodes = map(object({
      path         = string
      id           = string
      subsystem_id = string
      iommu_group  = number
    }))
  }))
  default = {}
}
