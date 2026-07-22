variable "project_id" {
  type        = string
  description = "The GCP project ID to deploy Antigravity Web Hub into."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "The GCP region for subnets and resources."
}

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "The GCP zone for the GCE instance and disk."
}

variable "instance_name" {
  type        = string
  default     = "antigravity-web-hub"
  description = "Name of the GCE instance."
}

variable "machine_type" {
  type        = string
  default     = "n4-standard-2"
  description = "Machine type for the GCE instance."
}

variable "data_disk_size_gb" {
  type        = number
  default     = 100
  description = "Size of the attached data disk in GB."
}

variable "name_prefix" {
  type        = string
  default     = "antigravity-web"
  description = "Prefix for network, load balancer, and security resources."
}

variable "public_domain" {
  type        = string
  default     = ""
  description = "Optional custom domain (e.g. antigravity.example.com). If empty, defaults to <static_ip>.nip.io."
}

variable "iap_members" {
  type        = list(string)
  description = "List of user email addresses or groups allowed to access the hub via IAP (e.g. [\"user:alice@example.com\"])."
}

variable "iap_client_id" {
  type        = string
  default     = ""
  description = "OAuth2 Client ID for IAP. If empty, uses GCP auto-provisioned brand/client."
}

variable "iap_client_secret" {
  type        = string
  default     = ""
  sensitive   = true
  description = "OAuth2 Client Secret for IAP. Required if iap_client_id is provided."
}
