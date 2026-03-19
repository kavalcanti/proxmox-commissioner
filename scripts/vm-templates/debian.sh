#!/bin/bash

# Create a Debian cloud image template

# User input for the template name
echo "Enter the desired template name and ID"
read -p "Enter base image full URL (default: debian-13-generic-amd64.qcow2): " base_image_url
    if [ -z "$base_image_url" ]; then
        base_image_url="https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2"
    fi
read -p "Enter the name of the template: " template_name
read -p "Enter the template ID: " template_id

# Manual configuration workflow:

manual_configuration_basic() {
    read -p "Enter storage volume name: " storage_volume_name
    read -p "Enter cloud-init storage volume name: " cloudinit_storage_volume_name
    read -p "Enter the memory size in MB: " memory_size
    read -p "Enter the number of cores: " cores
}

manual_configuration_advanced() {
    read -p "Enter the network bridge: " network_bridge
    read -p "Enter the disk interface: " disk_interface
    read -p "Enter the disk discard: " disk_discard
    read -p "Enter the disk format: " disk_format
}

read -p "Would you like to configure the template manually? (y/n): " configure_manual
if [ "$configure_manual" == "y" ]; then
    manual_configuration_basic
    read -p "Would you like to proceed with advanced configuration? (y/n): " configure_advanced
    if [ "$configure_advanced" == "y" ]; then
        manual_configuration_advanced
    else
        network_bridge="vmbr0"
        disk_interface="scsi0"
        disk_discard="on"
        disk_format="qcow2"
        echo "Proceeding with modified configuration..."
        echo "Storage volume name: ${storage_volume_name}"
        echo "Cloud-init storage volume name: ${cloudinit_storage_volume_name}"
        echo "Memory size: ${memory_size}"
        echo "Cores: ${cores}"
        echo "Network bridge: ${network_bridge}"
        echo "Disk interface: ${disk_interface}"
        echo "Disk discard: ${disk_discard}"
        echo "Disk format: ${disk_format}"
    fi
else
    storage_volume_name="local-lvm"
    cloudinit_storage_volume_name="local"
    memory_size=1024
    cores=1
    network_bridge="vmbr0"
    disk_interface="scsi0"
    disk_discard="on"
    disk_format="qcow2"

    echo "Proceeding with default configuration..."
    echo "Storage volume name: ${storage_volume_name}"
    echo "Cloud-init storage volume name: ${cloudinit_storage_volume_name}"
    echo "Memory size: ${memory_size}"
    echo "Cores: ${cores}"
    echo "Network bridge: ${network_bridge}"
    echo "Disk interface: ${disk_interface}"
    echo "Disk discard: ${disk_discard}"
    echo "Disk format: ${disk_format}"
fi

# Download the Debian cloud image
cd /tmp
wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2

# Import it as a VM template (creates VM ID 9000)
qm create ${template_id} --name ${template_name} --memory ${memory_size} --cores ${cores} --net0 virtio,bridge=${network_bridge}
qm importdisk ${template_id} debian-13-generic-amd64.qcow2 ${storage_volume_name}
qm set ${template_id} --scsihw virtio-scsi-pci --scsi0 ${storage_volume_name}:vm-${template_id}-disk-0
qm set ${template_id} --ide2 ${cloudinit_storage_volume_name}:cloudinit
qm set ${template_id} --boot c --bootdisk ${disk_interface}
qm set ${template_id} --agent enabled=1
qm set ${template_id} --vga qxl 
# Convert to template
qm template ${template_id}

# Clean up
rm debian-13-generic-amd64.qcow2