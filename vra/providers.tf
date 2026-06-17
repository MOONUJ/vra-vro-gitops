terraform {
  required_version = ">= 1.0"
  required_providers {
    vra = {
      source  = "vmware/vra"
      version = ">= 0.17.2"
    }
  }
}

provider "vra" {
  url           = var.vra_url
  refresh_token = var.vra_refresh_token
  insecure      = var.vra_insecure
  organization  = var.vra_organization
}
