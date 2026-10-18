# Cloud images are shared by every service, so they live in their own state.
# Destroying a service can never remove an image another service boots from.

locals {
  downloads = {
    for pair in setproduct(keys(var.nodes), keys(var.images)) :
    "${pair[0]}/${pair[1]}" => {
      node  = pair[0]
      image = pair[1]
    }
  }
}

resource "proxmox_download_file" "image" {
  for_each = local.downloads

  node_name    = each.value.node
  content_type = "iso"
  datastore_id = var.images_datastore
  url          = var.images[each.value.image]

  # Proxmox only accepts .iso and .img for the iso content type.
  file_name = "${each.value.image}.img"

  overwrite_unmanaged = true
}

# PCI passthrough devices are cluster-wide objects too. API tokens can only attach a
# device to a VM through a mapping, so hosts reference these by name.
resource "proxmox_hardware_mapping_pci" "this" {
  for_each = var.pci_mappings

  name    = each.key
  comment = each.value.comment == "" ? null : each.value.comment

  map = [
    for node, device in each.value.nodes : {
      node         = node
      path         = device.path
      id           = device.id
      subsystem_id = device.subsystem_id == "" ? null : device.subsystem_id
      iommu_group  = device.iommu_group < 0 ? null : device.iommu_group
    }
  ]
}
