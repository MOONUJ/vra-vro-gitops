variable "vra_url" {
  type        = string
  description = "VMware Aria Automation server URL (e.g., https://automation.example.com)"
}

variable "vra_refresh_token" {
  type        = string
  sensitive   = true
  description = "Aria Automation API Refresh Token"
}

variable "vra_insecure" {
  type        = bool
  default     = true
  description = "Allow insecure connections (disable SSL validation)"
}

variable "vra_organization" {
  type        = string
  default     = "default"
  description = "Organization name for VCF Automation"
}

# vCenter / Cloud Account variables
variable "vsphere_endpoint" {
  type        = string
  description = "FQDN or IP address of the vCenter Server"
}

variable "vsphere_cloud_account_name" {
  type        = string
  default     = null
  description = "vSphere Cloud Account name; defaults to vsphere_endpoint"
}

variable "vsphere_cloud_account_description" {
  type        = string
  default     = "vSphere Cloud Account managed by Terraform"
  description = "vSphere Cloud Account description"
}

variable "vsphere_username" {
  type        = string
  description = "vCenter username"
}

variable "vsphere_password" {
  type        = string
  sensitive   = true
  description = "vCenter password"
}

variable "vsphere_dc" {
  type        = string
  description = "vSphere Datacenter name"
}

variable "vsphere_region_name" {
  type        = string
  default     = null
  description = "Display name for the enabled vSphere region; defaults to vsphere_dc"
}

# NSX-T / Network variables
variable "nsxt_endpoint" {
  type        = string
  description = "FQDN or IP address of the NSX Manager"
}

variable "nsxt_cloud_account_name" {
  type        = string
  default     = null
  description = "NSX-T Cloud Account name; defaults to nsxt_endpoint"
}

variable "nsxt_cloud_account_description" {
  type        = string
  default     = "NSX-T Cloud Account managed by Terraform"
  description = "NSX-T Cloud Account description"
}

variable "nsxt_username" {
  type        = string
  description = "NSX username"
}

variable "nsxt_password" {
  type        = string
  sensitive   = true
  description = "NSX password"
}

# Environment profile names
variable "environment_tag" {
  type        = string
  default     = "example"
  description = "Environment tag for profile mappings (e.g., dev)"
}

variable "cloud_zone_name" {
  type        = string
  default     = "example-cloud-zone"
  description = "Cloud Zone name"
}

variable "cloud_zone_description" {
  type        = string
  default     = "vSphere Cloud Zone managed by Terraform"
  description = "Cloud Zone description"
}

variable "cloud_zone_placement_policy" {
  type        = string
  default     = "DEFAULT"
  description = "Cloud Zone placement policy"
}

variable "network_profile_name" {
  type        = string
  default     = "example-network-profile"
  description = "Network Profile name"
}

variable "network_profile_description" {
  type        = string
  default     = "Network Profile managed by Terraform"
  description = "Network Profile description"
}

variable "network_profile_isolation_type" {
  type        = string
  default     = "NONE"
  description = "Network Profile isolation type"
}

variable "network_profile_fabric_network_ids" {
  type        = list(string)
  default     = []
  description = "Fabric network IDs assigned to the Network Profile"
}

variable "storage_profile_name" {
  type        = string
  default     = "example-storage-profile"
  description = "Storage Profile name"
}

variable "storage_profile_description" {
  type        = string
  default     = "vSphere Storage Profile managed by Terraform"
  description = "Storage Profile description"
}

variable "storage_profile_default_item" {
  type        = bool
  default     = false
  description = "Whether the Storage Profile is the default item"
}

variable "storage_profile_provisioning_type" {
  type        = string
  default     = "thin"
  description = "Storage provisioning type"
}

variable "image_profile_name" {
  type        = string
  default     = "example-image-profile"
  description = "Image Profile name"
}

variable "image_profile_description" {
  type        = string
  default     = "Image Profile managed by Terraform"
  description = "Image Profile description"
}

variable "image_mappings" {
  type = list(object({
    name     = string
    image_id = string
  }))
  default = [
    {
      name     = "ubuntu"
      image_id = "ubuntu-template-id-placeholder"
    },
    {
      name     = "centos"
      image_id = "centos-template-id-placeholder"
    }
  ]
  description = "Image name to template ID mappings"
}

variable "project_name" {
  type        = string
  default     = "example-project"
  description = "Automation Project name"
}

variable "project_description" {
  type        = string
  default     = "Initial Infrastructure Project managed by Terraform"
  description = "Automation Project description"
}

variable "project_zone_priority" {
  type        = number
  default     = 1
  description = "Project Cloud Zone assignment priority"
}

variable "project_max_instances" {
  type        = number
  default     = 100
  description = "Maximum instances allowed for the Project Cloud Zone assignment"
}
