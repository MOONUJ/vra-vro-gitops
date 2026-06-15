resource "vra_storage_profile_vsphere" "storage_profile" {
  name              = "storage-profile-gvp"
  description       = "vSphere Storage Profile managed by Terraform"
  region_id         = data.vra_region.vsphere_region.id
  default_item      = false
  provisioning_type = "thin"
  disk_type         = "firstClass"

  tags {
    key   = "env"
    value = var.environment_tag
  }
}
