resource "vra_image_profile" "image_profile" {
  name        = var.image_profile_name
  description = var.image_profile_description
  region_id   = data.vra_region.vsphere_region.id

  dynamic "image_mapping" {
    for_each = var.image_mappings
    content {
      name     = image_mapping.value.name
      image_id = image_mapping.value.image_id
    }
  }
}
