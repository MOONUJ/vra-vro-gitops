resource "vra_image_profile" "image_profile" {
  name        = "image-profile-gvp"
  description = "Image Profile managed by Terraform"
  region_id   = data.vra_region.vsphere_region.id

  # Example mapping - update the filter or image_id as needed for your templates
  image_mapping {
    name     = "ubuntu"
    image_id = "ubuntu-template-id-placeholder"
  }

  image_mapping {
    name     = "centos"
    image_id = "centos-template-id-placeholder"
  }
}
