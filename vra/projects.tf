resource "vra_project" "project" {
  name        = "admin"
  description = "Initial Infrastructure Project managed by Terraform"

  zone_assignments {
    zone_id       = vra_zone.vsphere_zone.id
    priority      = 1
    max_instances = 100
  }
}
