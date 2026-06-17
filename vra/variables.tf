variable "vra_url" {
  type        = string
  description = "VMware Aria Automation server URL (e.g., https://poscodx-auto.gooddi.lab)"
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
  default     = "poscodx"
  description = "Organization name for VCF Automation"
}

# vCenter / Cloud Account variables
variable "vsphere_endpoint" {
  type        = string
  description = "FQDN or IP address of the vCenter Server"
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

# NSX-T / Network variables
variable "nsxt_endpoint" {
  type        = string
  description = "FQDN or IP address of the NSX Manager"
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
  default     = "gvp"
  description = "Environment tag for profile mappings (e.g., gvp)"
}
