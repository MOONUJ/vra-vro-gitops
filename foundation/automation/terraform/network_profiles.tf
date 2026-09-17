resource "vra_network_profile" "net_profile" {
  name               = var.network_profile_name
  description        = var.network_profile_description
  region_id          = data.vra_region.vsphere_region.id
  isolation_type     = var.network_profile_isolation_type
  fabric_network_ids = var.network_profile_fabric_network_ids

  tags {
    key   = "env"
    value = var.environment_tag
  }
}
