resource "vra_cloud_account_vsphere" "vsphere" {
  name                         = coalesce(var.vsphere_cloud_account_name, var.vsphere_endpoint)
  description                  = var.vsphere_cloud_account_description
  hostname                     = var.vsphere_endpoint
  username                     = var.vsphere_username
  password                     = var.vsphere_password
  accept_self_signed_cert      = var.vra_insecure
  associated_cloud_account_ids = [vra_cloud_account_nsxt.nsxt.id]

  enabled_regions {
    external_region_id = var.vsphere_dc
    name               = coalesce(var.vsphere_region_name, var.vsphere_dc)
  }

  timeouts {
    create = "5m"
    update = "5m"
    delete = "5m"
  }
}

resource "vra_cloud_account_nsxt" "nsxt" {
  name                    = coalesce(var.nsxt_cloud_account_name, var.nsxt_endpoint)
  description             = var.nsxt_cloud_account_description
  hostname                = var.nsxt_endpoint
  username                = var.nsxt_username
  password                = var.nsxt_password
  accept_self_signed_cert = var.vra_insecure
}
