resource "vra_network_profile" "net_profile" {
  name               = "network-profile-gvp"
  description        = "Network Profile managed by Terraform"
  region_id          = data.vra_region.vsphere_region.id
  isolation_type     = "NONE"
  fabric_network_ids = []

  tags {
    key   = "env"
    value = var.environment_tag
  }
}
