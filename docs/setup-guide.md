
# Before you begin

## Install dependencies

Make sure to install Ansible and Terraform before starting.

## PVE configuration

Please follow these required steps in your Proxmox Virtual Environment host before you use Proxmox Commissioner.

## Create a cloud-init template

A convenience script is provided for this under `scripts/vm-templates/debian.sh`
Either copy the file or its contents to your PVE host and run in. 
This can also be achieved on the shell or with ssh:

``` bash
# Manually creating a template vm in PVE shell
# Download the Debian cloud image
cd /tmp
wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2

# Import it as a VM template (creates VM ID 9000)
qm create 9000 --name debian-13-cloud --memory 1024 --cores 1 --net0 virtio,bridge=vmbr0
qm importdisk 9000 debian-13-generic-amd64.qcow2 local-lvm
qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
qm set 9000 --ide2 local:cloudinit
qm set 9000 --boot c --bootdisk scsi0
qm set 9000 --agent enabled=1
qm set 9000 --vga qxl 

# Convert to template
qm template 9000

# Clean up
rm debian-13-generic-amd64.qcow2
```

Note VM IDs must be unique both in a single node and across a cluster.
Debian is the OS I genereally use for servers, but the ansible Ansible automation in this repo will probably work for any Debian base distros.

Terraform can probably deal with other distros as long as templates and defaults are adjusted.

## Proxmox credentials

You will need to create a proxmox API key. 

Get a simple (and accteptably unsafe) one from PVE WebUI:
1. Datacenter
2. Permissions -> API Tokens -> Add
3. Select User: root@pam 
   3.1. Add a Token ID (any string will do) 
   3.2. Uncheck `Privilege Separation`

This creats an insecure but workable key which is fine for homelabs but not fine for production. 
I recommend creating a separate user for terraform and using a terraform dedicated role with minimal permissions. 
Enabling QEMU Agent requires SSH login, so the user should be @PAM, not @PVE.

For details on how to achieve more secure authentication, refer to [BPG documentation](https://registry.terraform.io/providers/bpg/proxmox/0.37.1/docs).

## Known setup pitfalls

Some fiddling might be needed to get cloud-init available in proxmox. Storage (local or local-lvm) might not be configured for snippet storage.

Check if snippets storage is configured on the Proxmox host with

```bash
pvesm status --content snippets 
```

If no storage is configured, run

```bash
pvesm set local --content vztmpl,iso,backup,snippets
```
