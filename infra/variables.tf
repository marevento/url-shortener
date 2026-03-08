variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-central-1" # Frankfurt - closest to Berlin
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "url-shortener"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch retention value."
  }
}

variable "custom_domain" {
  description = "Custom domain for the URL shortener (subdomain delegated to Route 53)"
  type        = string
}

variable "api_key" {
  description = "API key required for POST /shorten (leave empty to disable auth)"
  type        = string
  default     = ""
  sensitive   = true
}
