# Variables for the proxmox-vm module
# Provider-level variables (endpoint, api_token, ssh_user, node_ip) are NOT
# declared here; they belong in the service root that configures the provider.

# ==============================================================================
# PROXMOX NODE
# ==============================================================================

variable "proxmox_node" {
  description = "Proxmox node name to create VM on"
  type        = string
}

# ==============================================================================
# VM SPECIFICATIONS
# ==============================================================================

variable "vm_name" {
  description = "Name of the virtual machine"
  type        = string
}

variable "vm_id" {
  description = "Unique numeric identifier for the VM"
  type        = number
}

variable "vm_cores" {
  description = "Number of CPU cores"
  type        = number
  default     = 2
  validation {
    condition     = var.vm_cores >= 1
    error_message = "vm_cores must be at least 1"
  }
}

variable "vm_sockets" {
  description = "Number of CPU sockets"
  type        = number
  default     = 1
}

variable "vm_memory" {
  description = "Amount of memory in MB"
  type        = number
  default     = 2048
  validation {
    condition     = var.vm_memory >= 512
    error_message = "vm_memory must be at least 512 MB"
  }
}

variable "vm_disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 32
  validation {
    condition     = var.vm_disk_size >= 10
    error_message = "vm_disk_size must be at least 10 GB"
  }
}

# ==============================================================================
# TEMPLATE CONFIGURATION
# ==============================================================================

variable "template_id" {
  description = "ID of the template VM to clone from"
  type        = number
}

variable "clone_full" {
  description = "Whether to create a full clone (true) or linked clone (false)"
  type        = bool
  default     = true
}

# ==============================================================================
# STORAGE CONFIGURATION
# ==============================================================================

variable "datastore_disk" {
  description = "Datastore for VM disk"
  type        = string
  default     = "local-lvm"
}

variable "datastore_snippets" {
  description = "Datastore for cloud-init snippets"
  type        = string
  default     = "local"
}

variable "datastore_cloudinit" {
  description = "Datastore for cloud-init drive"
  type        = string
  default     = "local-lvm"
}

variable "disk_interface" {
  description = "Disk controller interface (scsi0, sata0, etc)"
  type        = string
  default     = "scsi0"
}

variable "disk_discard" {
  description = "Enable TRIM/discard for SSD"
  type        = string
  default     = "on"
}

variable "disk_format" {
  description = "Disk file format (qcow2, raw)"
  type        = string
  default     = "qcow2"
}

# ==============================================================================
# NETWORK CONFIGURATION
# ==============================================================================

variable "network_bridge" {
  description = "Network bridge to connect to"
  type        = string
  default     = "vmbr0"
}

variable "network_model" {
  description = "Network interface model (virtio, e1000, etc)"
  type        = string
  default     = "virtio"
}

variable "network_vlan_id" {
  description = "VLAN tag for the VM network interface (0 or null = untagged)"
  type        = number
  default     = 0
}

variable "network_mode" {
  description = "Network IP assignment mode: 'dhcp' or 'static'"
  type        = string
  default     = "dhcp"
  validation {
    condition     = contains(["dhcp", "static"], var.network_mode)
    error_message = "network_mode must be either 'dhcp' or 'static'"
  }
}

variable "network_ip" {
  description = "Static IP address with CIDR (e.g., 172.20.0.230/24). Required if network_mode is 'static'"
  type        = string
  default     = ""
}

variable "network_gateway" {
  description = "Gateway IP address (e.g., 172.20.0.1). Required if network_mode is 'static'"
  type        = string
  default     = ""
}

# ==============================================================================
# CLOUD-INIT CONFIGURATION
# ==============================================================================

variable "enable_qemu_agent" {
  description = "Enable QEMU guest agent"
  type        = bool
  default     = true
}

variable "package_update" {
  description = "Run package update on first boot"
  type        = bool
  default     = true
}

variable "package_upgrade" {
  description = "Run package upgrade on first boot (slow)"
  type        = bool
  default     = false
}

variable "ssh_pwauth" {
  description = "Allow SSH password authentication"
  type        = bool
  default     = true
}

variable "disable_root" {
  description = "Disable root SSH login"
  type        = bool
  default     = false
}

variable "root_password" {
  description = "Root password for the VM"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key to add to authorized_keys"
  type        = string
  default     = ""
}

variable "remove_distro_cloud_user" {
  description = "If non-empty, cloud-init runcmd removes this account after first boot (Debian cloud images create 'debian' as UID 1000; removing it leaves 1000 for the next user, e.g. devops). Set to \"\" to keep the distro default user."
  type        = string
  default     = "debian"
}
