# Everything except the two secrets is written by `pvc` to
# services/<svc>/.pvc/terraform.tfvars.json from site.yml and service.yml.
# Secrets arrive as TF_VAR_proxmox_api_token and TF_VAR_devops_password_hash.

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
  description = "Proxmox node name => address, used for the provider SSH connection"
  type        = map(string)
}

variable "service_name" {
  type = string
}

variable "hosts" {
  description = "Fully resolved hosts, keyed by the manifest host name"
  type = map(object({
    name          = string
    node          = string
    vm_id         = number
    ip            = string
    gateway       = string
    cores         = number
    sockets       = number
    memory        = number
    disk          = number
    vlan          = number
    bridge        = string
    image_file_id = string
    roles         = list(string)
  }))
}

variable "storage" {
  type = object({
    disk      = string
    snippets  = string
    cloudinit = string
  })
}

variable "network_model" {
  type    = string
  default = "virtio"
}

variable "nameservers" {
  type    = list(string)
  default = []
}

variable "vm_options" {
  type = object({
    qemu_agent      = bool
    package_update  = bool
    package_upgrade = bool
    disk_interface  = string
    disk_discard    = string
    disk_format     = string
  })
}

variable "devops_user" {
  type    = string
  default = "devops"
}

variable "devops_password_hash" {
  type      = string
  sensitive = true
}

variable "ssh_public_key" {
  type = string
}

variable "ssh_port" {
  type = number
}
