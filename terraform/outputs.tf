output "generated_files" {
  description = "Connection files written for Ansible."
  value = {
    connection_json = abspath(local_file.connection_json.filename)
    app_env         = abspath(local_file.app_env.filename)
    inventory       = abspath(local_file.ansible_inventory.filename)
  }
}

output "frontend_url" {
  description = "Frontend NodePort URL."
  value       = local.frontend_k8s_url
}

output "backend_url" {
  description = "Backend NodePort URL."
  value       = local.backend_k8s_url
}
