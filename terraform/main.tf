terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ------------------------------------------------------------------------------
# 0. Enable Required Google Cloud APIs
# ------------------------------------------------------------------------------
locals {
  required_services = [
    "compute.googleapis.com",
    "iap.googleapis.com",
    "aiplatform.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com"
  ]
}

resource "google_project_service" "services" {
  for_each           = toset(local.required_services)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ------------------------------------------------------------------------------
# 1. Custom VPC & Subnetwork (Argolis skips default network creation)
# ------------------------------------------------------------------------------
resource "google_compute_network" "vpc" {
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.services]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.name_prefix}-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
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


# ------------------------------------------------------------------------------
# 2. Firewall Rules (IAP Tunneling & LB Health Checks)
# ------------------------------------------------------------------------------
# Allow IAP SSH Tunneling (35.235.240.0/20)
resource "google_compute_firewall" "allow_iap_ssh" {
  name    = "${var.name_prefix}-allow-iap-ssh"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = [var.name_prefix]
}

# Allow GCP Classic Load Balancer Health Checks & Proxies
resource "google_compute_firewall" "allow_lb_hc" {
  name    = "${var.name_prefix}-allow-lb-hc"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
  target_tags   = [var.name_prefix]
}

# ------------------------------------------------------------------------------
# 3. Disks & Compute VM (Argolis Shielded VM & OS Login Compliant)
# ------------------------------------------------------------------------------
resource "google_compute_disk" "data_disk" {
  name = "${var.instance_name}-data"
  type = var.disk_type
  zone = var.zone
  size = var.data_disk_size_gb

  lifecycle {
    prevent_destroy = false
  }
}

resource "google_compute_instance" "hub_vm" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
      type  = var.disk_type
    }
  }

  attached_disk {
    source      = google_compute_disk.data_disk.id
    device_name = "data-disk"
  }

  # Argolis Mandatory Shielded VM Configuration
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  # Internal Network Only (No public IP - complies with Argolis vmExternalIpAccess restriction)
  network_interface {
    network    = google_compute_network.vpc.id
    subnetwork = google_compute_subnetwork.subnet.id
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  tags = [var.name_prefix]

  service_account {
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -euo pipefail
    # Format and mount data disk if unformatted
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
# 4. Unmanaged Instance Group & Health Check
# ------------------------------------------------------------------------------
resource "google_compute_instance_group" "unmanaged_ig" {
  name        = "${var.name_prefix}-ig"
  zone        = var.zone
  instances   = [google_compute_instance.hub_vm.self_link]


  named_port {
    name = "http"
    port = 8080
  }
}

resource "google_compute_health_check" "hc" {
  name = "${var.name_prefix}-hc"

  tcp_health_check {
    port = 8080
  }
}

# ------------------------------------------------------------------------------
# 5. Reserved Global IP & SSL Certificate
# ------------------------------------------------------------------------------
resource "google_compute_global_address" "static_ip" {
  name = "${var.name_prefix}-ip"
}

locals {
  domain_name = var.public_domain != "" ? var.public_domain : "${google_compute_global_address.static_ip.address}.nip.io"
  cert_slug   = replace(replace(lower(local.domain_name), ".", "-"), "/", "-")
}

resource "google_compute_managed_ssl_certificate" "ssl_cert" {
  name = substr("${var.name_prefix}-cert-${local.cert_slug}", 0, 63)

  managed {
    domains = [local.domain_name]
  }
}

# ------------------------------------------------------------------------------
# 6. Global Backend Service with IAP & HTTPS Load Balancer
# ------------------------------------------------------------------------------
resource "google_compute_backend_service" "backend" {
  name                  = "${var.name_prefix}-bs"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 86400
  health_checks         = [google_compute_health_check.hc.id]
  load_balancing_scheme = "EXTERNAL"

  backend {
    group = google_compute_instance_group.unmanaged_ig.id
  }

  iap {
    oauth2_client_id     = var.iap_client_id
    oauth2_client_secret = var.iap_client_secret
  }
}

resource "google_compute_url_map" "url_map" {
  name            = "${var.name_prefix}-um"
  default_service = google_compute_backend_service.backend.id
}

resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "${var.name_prefix}-tp"
  url_map          = google_compute_url_map.url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.ssl_cert.id]
}

resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  name       = "${var.name_prefix}-fr"
  target     = google_compute_target_https_proxy.https_proxy.id
  port_range = "443"
  ip_address = google_compute_global_address.static_ip.address
}

# ------------------------------------------------------------------------------
# 7. IAM Access Bindings for IAP Access
# ------------------------------------------------------------------------------
resource "google_iap_web_backend_service_iam_binding" "iap_binding" {
  project             = var.project_id
  web_backend_service = google_compute_backend_service.backend.name
  role                = "roles/iap.httpsResourceAccessor"
  members             = var.iap_members
  depends_on          = [google_project_service.services]
}

# ------------------------------------------------------------------------------
# 8. Project IAM Role for Vertex AI Access
# ------------------------------------------------------------------------------
data "google_compute_default_service_account" "default" {
  project    = var.project_id
  depends_on = [google_project_service.services]
}

resource "google_project_iam_member" "compute_sa_vertex_ai_user" {
  project    = var.project_id
  role       = "roles/aiplatform.user"
  member     = "serviceAccount:${data.google_compute_default_service_account.default.email}"
  depends_on = [google_project_service.services]
}


