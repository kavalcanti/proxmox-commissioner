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
