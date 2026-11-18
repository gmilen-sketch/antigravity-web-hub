output "public_ip" {
  value       = var.ingress_mode == "classic_lb" ? google_compute_global_address.static_ip[0].address : null
  description = "Reserved global public IP address of the Classic HTTPS Load Balancer (null when using cloud_run_direct_iap)."
}

output "public_url" {
  value = (
    var.ingress_mode == "cloud_run_direct_iap"
    ? "${google_cloud_run_v2_service.iap_proxy[0].uri}/"
    : "https://${local.domain_name}/"
  )
  description = "The HTTPS entry point URL for Antigravity Web Hub."
}

output "vm_name" {
  value       = google_compute_instance.hub_vm.name
  description = "GCE instance name."
}

output "runtime_service_account_email" {
  value       = google_service_account.hub_runtime.email
  description = "Dedicated least-privilege runtime service account attached to the hub VM."
}

output "iap_ssh_command" {
  value       = "gcloud compute ssh ${google_compute_instance.hub_vm.name} --project=${var.project_id} --zone=${var.zone} --tunnel-through-iap"
  description = "Command to SSH into the VM securely via IAP."
}
