# ═══════════════════════════════════════════════════════════════════════════
# Terraform — Input Variables
# ═══════════════════════════════════════════════════════════════════════════

variable "aws_region" {
  description = "AWS region where resources are created."
  type        = string
  default     = "ap-south-1"
}

variable "aws_profile" {
  description = "AWS CLI named profile to use. Leave empty to use default credential chain."
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "EC2 instance type. t2.micro is within the Free Tier."
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = <<-EOT
    Amazon Machine Image ID.
    Leave empty to auto-resolve the latest Ubuntu 22.04 LTS AMI in the chosen region.
    Example (ap-south-1): ami-0f58b397bc5c1f2e8
  EOT
  type        = string
  default     = ""
}

variable "key_name" {
  description = "Name of an existing EC2 Key Pair for SSH access."
  type        = string
}

variable "ssh_allowed_cidr" {
  description = <<-EOT
    CIDR block allowed to reach port 22 (SSH).
    Use your public IP in x.x.x.x/32 format.
    Do NOT use 0.0.0.0/0 in production.
  EOT
  type        = string

  validation {
    condition     = can(cidrhost(var.ssh_allowed_cidr, 0))
    error_message = "ssh_allowed_cidr must be a valid CIDR block (e.g. 203.0.113.10/32)."
  }
}

variable "app_port" {
  description = "TCP port the application listens on inside the container (mapped from host port 80)."
  type        = number
  default     = 80
}

variable "project_name" {
  description = "Short tag applied to all resources for identification."
  type        = string
  default     = "cloud-todo"
}
