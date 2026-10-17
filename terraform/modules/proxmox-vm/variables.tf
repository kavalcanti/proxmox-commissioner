# Variables for the proxmox-vm module.
# Provider settings (endpoint, token, SSH) belong to the calling root module.

variable "proxmox_node" {
  description = "Proxmox node the VM runs on"
  type        = string
}

variable "vm_name" {
  description = "VM name, also used as its hostname"
  type        = string
}

variable "vm_id" {
  description = "Unique numeric VM id"
  type        = number
}

variable "tags" {
  description = "Proxmox tags for the VM"
  type        = list(string)
  default     = []
}

# ------------------------------------------------------------------------------
# Hardware
# ------------------------------------------------------------------------------

variable "vm_cores" {
  type    = number
  default = 1
  validation {
    condition     = var.vm_cores >= 1
    error_message = "vm_cores must be at least 1"
  }
}

variable "vm_sockets" {
  type    = number
  default = 1
}

variable "vm_memory" {
  description = "Memory in MB"
  type        = number
  default     = 1024
  validation {
    condition     = var.vm_memory >= 512
    error_message = "vm_memory must be at least 512 MB"
  }
}

variable "vm_disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 16
  validation {
    condition     = var.vm_disk_size >= 8
    error_message = "vm_disk_size must be at least 8 GB"
  }
}

# ------------------------------------------------------------------------------
# Image and storage
# ------------------------------------------------------------------------------

variable "image_file_id" {
  description = "Proxmox volume id of the cloud image, e.g. local:iso/debian-13.img"
  type        = string
}

variable "datastore_disk" {
  type    = string
  default = "local-lvm"
}

variable "datastore_snippets" {
  description = "Datastore with the snippets content type enabled"
  type        = string
  default     = "local"
}

variable "datastore_cloudinit" {
  type    = string
  default = "local-lvm"
}

variable "disk_interface" {
  type    = string
  default = "scsi0"
}

variable "disk_discard" {
  type    = string
  default = "on"
}

variable "disk_format" {
  description = "raw works everywhere; qcow2 needs file based storage"
  type        = string
  default     = "raw"
}

# ------------------------------------------------------------------------------
# Network
# ------------------------------------------------------------------------------

variable "network_bridge" {
  type    = string
  default = "vmbr0"
}

variable "network_model" {
  type    = string
  default = "virtio"
}

variable "network_mac" {
  description = "Fixed MAC address. Null lets Proxmox generate one."
  type        = string
  default     = null
}

variable "network_vlan_id" {
  description = "VLAN tag (0 = untagged)"
  type        = number
  default     = 0
}

variable "network_ip" {
  description = "Static IPv4 in CIDR form. Empty means DHCP."
  type        = string
  default     = ""
}

variable "network_gateway" {
  description = "Gateway for a static IP"
  type        = string
  default     = null
}

variable "nameservers" {
  type    = list(string)
  default = []
}

# ------------------------------------------------------------------------------
# Cloud-init
# ------------------------------------------------------------------------------

variable "enable_qemu_agent" {
  type    = bool
  default = true
}

variable "package_update" {
  type    = bool
  default = true
}

variable "package_upgrade" {
  type    = bool
  default = false
}

variable "devops_user" {
  description = "Sudo user created for Ansible"
  type        = string
  default     = "devops"
}

variable "devops_password_hash" {
  description = "SHA-512 crypt hash of the sudo password"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "Public key authorised for the devops user"
  type        = string
}

variable "ssh_port" {
  description = "Final SSH port"
  type        = number
  default     = 22
}

variable "remove_distro_cloud_user" {
  description = "Distro default account to delete after first boot (Debian cloud images ship 'debian'). Empty keeps it."
  type        = string
  default     = "debian"
}
