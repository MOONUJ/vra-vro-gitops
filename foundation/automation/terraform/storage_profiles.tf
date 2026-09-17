resource "vra_storage_profile_vsphere" "storage_profile" {
  name              = var.storage_profile_name
  description       = var.storage_profile_description
  region_id         = data.vra_region.vsphere_region.id
  default_item      = var.storage_profile_default_item
  provisioning_type = var.storage_profile_provisioning_type

  tags {
    key   = "env"
    value = var.environment_tag
  }
}
