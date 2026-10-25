variable "project_name" {
  description = "Project identifier written into the connection files."
  type        = string
  default     = "payment-engine"
}

variable "environment" {
  description = "Deployment environment label."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, test, staging, prod."
  }
}

variable "app_version" {
  description = "Application release version."
  type        = string
  default     = "1.0.0"

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.app_version))
    error_message = "app_version must be semantic (e.g. 1.0.0)."
  }
}

variable "host_address" {
  description = "Address where Docker Desktop publishes ports / NodePorts."
  type        = string
  default     = "localhost"
}

variable "k8s_namespace" {
  description = "Kubernetes namespace of the stack (must match k8s/00-namespace.yaml)."
  type        = string
  default     = "payment-engine"
}

variable "backend_service_port" {
  description = "Backend container/service port."
  type        = number
  default     = 5000
}

variable "frontend_service_port" {
  description = "Frontend container/service port."
  type        = number
  default     = 80
}

variable "backend_nodeport" {
  description = "Backend NodePort (must match k8s/10-backend.yaml)."
  type        = number
  default     = 30500

  validation {
    condition     = var.backend_nodeport >= 30000 && var.backend_nodeport <= 32767
    error_message = "NodePort must be within 30000-32767."
  }
}

variable "frontend_nodeport" {
  description = "Frontend NodePort (must match k8s/20-frontend.yaml)."
  type        = number
  default     = 30080

  validation {
    condition     = var.frontend_nodeport >= 30000 && var.frontend_nodeport <= 32767
    error_message = "NodePort must be within 30000-32767."
  }
}

variable "docker_backend_host_port" {
  description = "Host port used by `docker run -p` for the backend container."
  type        = number
  default     = 5000
}

variable "docker_frontend_host_port" {
  description = "Host port used by `docker run -p` for the frontend container (8080 is Jenkins)."
  type        = number
  default     = 8081
}
