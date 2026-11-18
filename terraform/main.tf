terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.30.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.30.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ------------------------------------------------------------------------------
# 0. Enable Required Google Cloud APIs
# ------------------------------------------------------------------------------
locals {
  required_services = distinct(concat(
    [
      "compute.googleapis.com",
      "iap.googleapis.com",
      "aiplatform.googleapis.com",
      "iam.googleapis.com",
      "dns.googleapis.com",
      "cloudresourcemanager.googleapis.com",
      "serviceusage.googleapis.com",
    ],
    var.ingress_mode == "cloud_run_direct_iap" ? ["run.googleapis.com", "artifactregistry.googleapis.com"] : []
  ))
  disk_type      = startswith(var.machine_type, "n4") || startswith(var.machine_type, "c3") || startswith(var.machine_type, "c4") ? "hyperdisk-balanced" : "pd-balanced"
  use_classic_lb = var.ingress_mode == "classic_lb"
  use_cloud_run  = var.ingress_mode == "cloud_run_direct_iap"
}

resource "google_project_service" "services" {
  for_each           = toset(local.required_services)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ------------------------------------------------------------------------------
# 0b. Dedicated Least-Privilege Runtime Service Account (ACE-WS-02)
# ------------------------------------------------------------------------------
resource "google_service_account" "hub_runtime" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-runtime"
  display_name = "Antigravity Web Hub Runtime SA (${var.name_prefix})"
  depends_on   = [google_project_service.services]
}

resource "google_project_iam_member" "hub_runtime_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/bigquery.jobUser",
  ])
  project    = var.project_id
  role       = each.value
  member     = "serviceAccount:${google_service_account.hub_runtime.email}"
  depends_on = [google_service_account.hub_runtime]
}

# ------------------------------------------------------------------------------
# 1. Custom VPC, PGA Subnet & Cloud NAT (Enterprise GCP Sandbox Compliant)
# ------------------------------------------------------------------------------
resource "google_compute_network" "vpc" {
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.services]
}

resource "google_compute_subnetwork" "subnet" {
  name                     = "${var.name_prefix}-subnet"
  ip_cidr_range            = "10.0.1.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true
}

resource "google_compute_router" "router" {
  name    = "${var.name_prefix}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.name_prefix}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# Private Google Access Private DNS Zone (199.36.153.8/30) (ACE-WS-02)
resource "google_dns_managed_zone" "pga_googleapis" {
  count       = var.enable_pga_private_dns ? 1 : 0
  name        = "${var.name_prefix}-pga-googleapis"
  dns_name    = "googleapis.com."
  description = "Private Google Access routing for ${var.name_prefix}"
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.vpc.id
    }
  }
  depends_on = [google_project_service.services]
}

resource "google_dns_record_set" "pga_googleapis_a" {
  count        = var.enable_pga_private_dns ? 1 : 0
  name         = "private.googleapis.com."
  managed_zone = google_dns_managed_zone.pga_googleapis[0].name
  type         = "A"
  ttl          = 300
  rrdatas      = ["199.36.153.8", "199.36.153.9", "199.36.153.10", "199.36.153.11"]
}

resource "google_dns_record_set" "pga_googleapis_cname" {
  count        = var.enable_pga_private_dns ? 1 : 0
  name         = "*.googleapis.com."
  managed_zone = google_dns_managed_zone.pga_googleapis[0].name
  type         = "CNAME"
  ttl          = 300
  rrdatas      = ["private.googleapis.com."]
}

# ------------------------------------------------------------------------------
# 2. Firewall Rules & Opt-In FQDN Egress Policy (ACE-WS-02)
# ------------------------------------------------------------------------------
resource "google_compute_firewall" "deny_lateral" {
  name          = "${var.name_prefix}-deny-lateral"
  network       = google_compute_network.vpc.name
  direction     = "INGRESS"
  priority      = 1000
  source_ranges = ["10.0.1.0/24"]

  deny {
    protocol = "all"
  }
}

resource "google_compute_firewall" "allow_iap_ssh" {
  name          = "${var.name_prefix}-allow-iap-ssh"
  network       = google_compute_network.vpc.name
  priority      = 900
  source_ranges = ["35.235.240.0/20"]
  target_tags   = [var.name_prefix]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_firewall" "allow_lb_hc" {
  count         = local.use_classic_lb ? 1 : 0
  name          = "${var.name_prefix}-allow-lb-hc"
  network       = google_compute_network.vpc.name
  priority      = 900
  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
  target_tags   = [var.name_prefix]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}

resource "google_compute_firewall" "allow_cloudrun_egress" {
  count         = local.use_cloud_run ? 1 : 0
  name          = "${var.name_prefix}-allow-cloudrun-egress"
  network       = google_compute_network.vpc.name
  priority      = 900
  source_ranges = ["10.0.1.0/24"]
  target_tags   = [var.name_prefix]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}

resource "google_compute_network_firewall_policy" "egress_allowlist" {
  count       = var.enable_fqdn_egress_policy ? 1 : 0
  name        = "${var.name_prefix}-egress-policy"
  description = "Opt-in FQDN egress allowlist for ${var.name_prefix}"
  depends_on  = [google_project_service.services]
}

resource "google_compute_network_firewall_policy_rule" "allow_pga_egress" {
  count                   = var.enable_fqdn_egress_policy ? 1 : 0
  firewall_policy         = google_compute_network_firewall_policy.egress_allowlist[0].name
  priority                = 1000
  direction               = "EGRESS"
  action                  = "allow"
  enable_logging          = true
  target_service_accounts = [google_service_account.hub_runtime.email]
  match {
    dest_ip_ranges = ["199.36.153.8/30"]
    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["443"]
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "allow_fqdn_egress" {
  count                   = var.enable_fqdn_egress_policy ? 1 : 0
  firewall_policy         = google_compute_network_firewall_policy.egress_allowlist[0].name
  priority                = 1100
  direction               = "EGRESS"
  action                  = "allow"
  enable_logging          = true
  target_service_accounts = [google_service_account.hub_runtime.email]
  match {
    dest_fqdns = var.egress_fqdn_allowlist
    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["443", "80"]
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "default_deny_egress" {
  count                   = var.enable_fqdn_egress_policy ? 1 : 0
  firewall_policy         = google_compute_network_firewall_policy.egress_allowlist[0].name
  priority                = 65000
  direction               = "EGRESS"
  action                  = "deny"
  enable_logging          = true
  target_service_accounts = [google_service_account.hub_runtime.email]
  match {
    dest_ip_ranges = ["0.0.0.0/0"]
    layer4_configs {
      ip_protocol = "all"
    }
  }
}

resource "google_compute_network_firewall_policy_association" "egress_assoc" {
  count             = var.enable_fqdn_egress_policy ? 1 : 0
  name              = "${var.name_prefix}-egress-policy-assoc"
  firewall_policy   = google_compute_network_firewall_policy.egress_allowlist[0].name
  attachment_target = google_compute_network.vpc.id
}

# ------------------------------------------------------------------------------
# 3. Disks, Idle Schedule & Shielded Compute VM (ACE-WS-02 & ACE-WS-06)
# ------------------------------------------------------------------------------
resource "google_compute_resource_policy" "idle_schedule" {
  count       = var.enable_instance_schedule ? 1 : 0
  name        = "${var.name_prefix}-idle-schedule"
  region      = var.region
  description = "Automated off-hours stop schedule for ${var.name_prefix}"
  depends_on  = [google_project_service.services]

  instance_schedule_policy {
    vm_stop_schedule {
      schedule = var.vm_stop_schedule
    }
    time_zone = var.vm_schedule_time_zone
  }
}

resource "google_compute_disk" "data_disk" {
  name       = "${var.instance_name}-data"
  type       = local.disk_type
  zone       = var.zone
  size       = var.data_disk_size_gb
  depends_on = [google_project_service.services]

  lifecycle {
    prevent_destroy = false
  }
}

resource "google_compute_instance" "hub_vm" {
  name              = var.instance_name
  machine_type      = var.machine_type
  zone              = var.zone
  resource_policies = var.enable_instance_schedule ? [google_compute_resource_policy.idle_schedule[0].id] : []
  depends_on        = [google_project_service.services, google_project_iam_member.hub_runtime_roles]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
      type  = local.disk_type
    }
  }

  attached_disk {
    source      = google_compute_disk.data_disk.id
    device_name = "data-disk"
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  network_interface {
    network    = google_compute_network.vpc.id
    subnetwork = google_compute_subnetwork.subnet.id
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  tags = [var.name_prefix]

  service_account {
    email = google_service_account.hub_runtime.email
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
      "https://www.googleapis.com/auth/userinfo.email",
      "https://www.googleapis.com/auth/userinfo.profile",
      "openid"
    ]
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -euo pipefail
    DISK_DEV="/dev/disk/by-id/google-data-disk"
    MOUNT_POINT="/mnt/data"

    if [ -b "$DISK_DEV" ]; then
      if ! blkid "$DISK_DEV" >/dev/null 2>&1; then
        mkfs.ext4 -m 0 -F "$DISK_DEV"
      fi
      mkdir -p "$MOUNT_POINT"
      mount -o discard,defaults "$DISK_DEV" "$MOUNT_POINT" || true
      grep -q "$MOUNT_POINT" /etc/fstab || echo "$DISK_DEV $MOUNT_POINT ext4 discard,defaults 0 2" >> /etc/fstab
    fi
  EOF
}

# ------------------------------------------------------------------------------
# 4a. Classic HTTPS Load Balancer + IAP Mode (default, 86400s streaming timeout)
# ------------------------------------------------------------------------------
resource "google_compute_instance_group" "unmanaged_ig" {
  count     = local.use_classic_lb ? 1 : 0
  name      = "${var.name_prefix}-ig"
  zone      = var.zone
  instances = [google_compute_instance.hub_vm.self_link]

  named_port {
    name = "http"
    port = 8080
  }
}

resource "google_compute_health_check" "hc" {
  count      = local.use_classic_lb ? 1 : 0
  name       = "${var.name_prefix}-hc"
  depends_on = [google_project_service.services]

  tcp_health_check {
    port = 8080
  }
}

resource "google_compute_global_address" "static_ip" {
  count      = local.use_classic_lb ? 1 : 0
  name       = "${var.name_prefix}-ip"
  depends_on = [google_project_service.services]
}

locals {
  domain_name = local.use_classic_lb ? (var.public_domain != "" ? var.public_domain : "${google_compute_global_address.static_ip[0].address}.nip.io") : ""
  cert_slug   = replace(replace(lower(local.domain_name), ".", "-"), "/", "-")
}

resource "google_compute_managed_ssl_certificate" "ssl_cert" {
  count = local.use_classic_lb ? 1 : 0
  name  = substr("${var.name_prefix}-cert-${local.cert_slug}", 0, 63)

  managed {
    domains = [local.domain_name]
  }
}

resource "google_compute_backend_service" "backend" {
  count                   = local.use_classic_lb ? 1 : 0
  name                    = "${var.name_prefix}-bs"
  protocol                = "HTTP"
  port_name               = "http"
  timeout_sec             = 86400
  session_affinity        = "GENERATED_COOKIE"
  affinity_cookie_ttl_sec = 86400
  health_checks           = [google_compute_health_check.hc[0].id]
  load_balancing_scheme   = "EXTERNAL"

  backend {
    group = google_compute_instance_group.unmanaged_ig[0].id
  }

  iap {
    oauth2_client_id     = var.iap_client_id
    oauth2_client_secret = var.iap_client_secret
  }
}

resource "google_compute_url_map" "url_map" {
  count           = local.use_classic_lb ? 1 : 0
  name            = "${var.name_prefix}-um"
  default_service = google_compute_backend_service.backend[0].id
}

resource "google_compute_target_https_proxy" "https_proxy" {
  count            = local.use_classic_lb ? 1 : 0
  name             = "${var.name_prefix}-tp"
  url_map          = google_compute_url_map.url_map[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.ssl_cert[0].id]
}

resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  count      = local.use_classic_lb ? 1 : 0
  name       = "${var.name_prefix}-fr"
  target     = google_compute_target_https_proxy.https_proxy[0].id
  port_range = "443"
  ip_address = google_compute_global_address.static_ip[0].address
}

resource "google_iap_web_backend_service_iam_binding" "iap_binding" {
  count               = local.use_classic_lb ? 1 : 0
  project             = var.project_id
  web_backend_service = google_compute_backend_service.backend[0].name
  role                = "roles/iap.httpsResourceAccessor"
  members             = var.iap_members
  depends_on          = [google_project_service.services]
}

# ------------------------------------------------------------------------------
# 4b. Opt-In Cloud Run v2 Direct IAP Mode (ACE-WS-04 — Zero Custom OAuth / Error 604)
# ------------------------------------------------------------------------------
resource "google_project_service_identity" "iap_sa" {
  count      = local.use_cloud_run ? 1 : 0
  provider   = google-beta
  project    = var.project_id
  service    = "iap.googleapis.com"
  depends_on = [google_project_service.services]
}

resource "google_cloud_run_v2_service" "iap_proxy" {
  count        = local.use_cloud_run ? 1 : 0
  provider     = google-beta
  project      = var.project_id
  name         = "${var.name_prefix}-proxy"
  location     = var.region
  launch_stage = "BETA"
  iap_enabled  = true
  depends_on   = [google_project_service.services, google_compute_instance.hub_vm]

  template {
    timeout         = "3600s"
    service_account = google_service_account.hub_runtime.email
    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.vpc.name
        subnetwork = google_compute_subnetwork.subnet.name
      }
    }
    containers {
      image = var.cloudrun_proxy_image
      ports {
        container_port = 8080
      }
      env {
        name  = "UPSTREAM_HOST"
        value = google_compute_instance.hub_vm.network_interface[0].network_ip
      }
      env {
        name  = "UPSTREAM_PORT"
        value = "8080"
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "iap_proxy_invoker" {
  count    = local.use_cloud_run ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.iap_proxy[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap_sa[0].email}"
}

resource "google_iap_web_cloud_run_service_iam_member" "iap_proxy_users" {
  for_each               = local.use_cloud_run ? toset(var.iap_members) : toset([])
  provider               = google-beta
  project                = var.project_id
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.iap_proxy[0].name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
}
