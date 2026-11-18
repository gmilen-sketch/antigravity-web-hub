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

variable "disk_type" {
  type        = string
  default     = "hyperdisk-balanced"
  description = "Disk type for boot and data disks (hyperdisk-balanced for N4/C3/C4, or pd-balanced for E2/N2)."
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
  description = "OAuth2 Client ID for Classic LB IAP. If empty, uses GCP auto-provisioned brand/client."
}

variable "iap_client_secret" {
  type        = string
  default     = ""
  sensitive   = true
  description = "OAuth2 Client Secret for Classic LB IAP. Required if iap_client_id is provided."
}

variable "ingress_mode" {
  type        = string
  default     = "classic_lb"
  description = "Ingress mode: 'classic_lb' (86400s streaming timeout) or 'cloud_run_direct_iap' (zero Custom OAuth Client / Error 604 bypass, 3600s timeout)."
  validation {
    condition     = contains(["classic_lb", "cloud_run_direct_iap"], var.ingress_mode)
    error_message = "ingress_mode must be 'classic_lb' or 'cloud_run_direct_iap'."
  }
}

variable "cloudrun_proxy_image" {
  type        = string
  default     = ""
  description = "Artifact Registry image URI for src/cloudrun_iap_proxy when ingress_mode = 'cloud_run_direct_iap'."
}

variable "enable_pga_private_dns" {
  type        = bool
  default     = true
  description = "Create a private googleapis.com DNS zone routing traffic to Private Google Access (199.36.153.8/30)."
}

variable "enable_fqdn_egress_policy" {
  type        = bool
  default     = false
  description = "Attach a global Network Firewall Policy enforcing default-deny egress with allowlisted FQDNs for the runtime SA."
}

variable "egress_fqdn_allowlist" {
  type = list(string)
  default = [
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "packages.cloud.google.com",
    "dl.google.com",
    "antigravity.google",
    "antigravity.static.usercontent.goog",
    "antigravity-hub-auto-updater-974169037036.us-central1.run.app",
    "antigravity-cli-auto-updater-974169037036.us-central1.run.app",
    "deb.debian.org",
    "security.debian.org",
    "cdn-fastly.deb.debian.org",
    "pypi.org",
    "files.pythonhosted.org",
    "registry.npmjs.org",
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
  ]
  description = "Allowlisted destination FQDNs when enable_fqdn_egress_policy = true."
}

variable "enable_instance_schedule" {
  type        = bool
  default     = false
  description = "Attach a GCE vm_start_stop_schedule resource policy to automatically stop idle demo/PoC VMs."
}

variable "vm_stop_schedule" {
  type        = string
  default     = "0 22 * * *"
  description = "Cron schedule for automated VM stop when enable_instance_schedule = true."
}

variable "vm_schedule_time_zone" {
  type        = string
  default     = "UTC"
  description = "IANA timezone for vm_stop_schedule."
}
