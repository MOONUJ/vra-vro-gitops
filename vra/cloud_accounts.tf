resource "vra_cloud_account_vsphere" "vsphere" {
  name                    = "vsphere-cloud-account"
  description             = "vSphere Cloud Account managed by Terraform"
  hostname                = var.vsphere_endpoint
  username                = var.vsphere_username
  password                = var.vsphere_password
  accept_self_signed_cert = var.vra_insecure

  regions = [var.vsphere_dc]

  tags {
    key   = "env"
    value = var.environment_tag
  }
}

resource "vra_cloud_account_nsxt" "nsxt" {
  name                    = "nsxt-cloud-account"
  description             = "NSX-T Cloud Account managed by Terraform"
  hostname                = var.nsxt_endpoint
  username                = var.nsxt_username
  password                = var.nsxt_password
  accept_self_signed_cert = var.vra_insecure

  tags {
    key   = "env"
    value = var.environment_tag
  }
}
