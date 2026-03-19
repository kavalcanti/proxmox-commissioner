# Variables for the arr service root
# Provider connection + all module variables are declared here.
# Values come from TF_VAR_* environment variables sourced by scripts.

# ==============================================================================
# PROXMOX CONNECTION (provider-level)
# ==============================================================================

variable "proxmox_endpoint" {
  description = "Proxmox VE API endpoint URL"
  type        = string
}

variable "proxmox_api_token" {
  description = "Proxmox VE API token for authentication"
  type        = string
  sensitive   = true
}

variable "proxmox_node" {
  description = "Proxmox node name to create VM on"
  type        = string
}

variable "proxmox_node_ip" {
  description = "Proxmox node IP address for SSH connection"
  type        = string
}

variable "proxmox_ssh_user" {
  description = "SSH user for Proxmox node"
  type        = string
  default     = "root"
}

variable "proxmox_destination_node" {
  description = "Proxmox node to migrate the VM to after cloning (leave empty to skip migration)"
  type        = string
  default     = ""
}

variable "proxmox_destination_node_ip" {
  description = "IP address of the destination Proxmox node (for future use / documentation)"
  type        = string
  default     = ""
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
}

variable "vm_disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 32
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
  description = "VLAN tag for the VM network interface (0 = untagged)"
  type        = number
  default     = 0
}

variable "network_mode" {
  description = "Network IP assignment mode: 'dhcp' or 'static'"
  type        = string
  default     = "dhcp"
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
