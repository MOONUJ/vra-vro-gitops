data "vra_region" "vsphere_region" {
  cloud_account_id = vra_cloud_account_vsphere.vsphere.id
  region           = var.vsphere_dc
}

resource "vra_zone" "vsphere_zone" {
  name             = var.cloud_zone_name
  description      = var.cloud_zone_description
  region_id        = data.vra_region.vsphere_region.id
  placement_policy = var.cloud_zone_placement_policy

  tags {
    key   = "env"
    value = var.environment_tag
  }
}
