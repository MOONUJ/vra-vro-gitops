data "vra_region" "vsphere_region" {
  cloud_account_id = vra_cloud_account_vsphere.vsphere.id
  region           = var.vsphere_dc
}

resource "vra_zone" "vsphere_zone" {
  name             = "vsphere-cloud-zone"
  description      = "vSphere Cloud Zone managed by Terraform"
  region_id        = data.vra_region.vsphere_region.id
  placement_policy = "DEFAULT"

  tags {
    key   = "env"
    value = var.environment_tag
  }
}
