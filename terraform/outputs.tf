output "public_ip" {
  value       = google_compute_global_address.static_ip.address
  description = "Reserved global public IP address of the HTTPS Load Balancer."
}

output "public_url" {
  value       = "https://${local.domain_name}/"
  description = "The HTTPS entry point URL for Antigravity Web Hub."
}

output "vm_name" {
  value       = google_compute_instance.hub_vm.name
  description = "GCE instance name."
}

output "iap_ssh_command" {
  value       = "gcloud compute ssh ${google_compute_instance.hub_vm.name} --project=${var.project_id} --zone=${var.zone} --tunnel-through-iap"
  description = "Command to SSH into the VM securely via IAP."
}
