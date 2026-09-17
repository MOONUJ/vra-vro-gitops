resource "vra_project" "project" {
  name        = var.project_name
  description = var.project_description

  zone_assignments {
    zone_id       = vra_zone.vsphere_zone.id
    priority      = var.project_zone_priority
    max_instances = var.project_max_instances
  }
}
