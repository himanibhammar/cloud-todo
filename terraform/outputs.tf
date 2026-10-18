# ═══════════════════════════════════════════════════════════════════════════
# Terraform — Outputs
# ═══════════════════════════════════════════════════════════════════════════

output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.todo_server.id
}

output "public_ip" {
  description = "Public IPv4 address of the EC2 instance."
  value       = aws_instance.todo_server.public_ip
}

output "application_url" {
  description = "URL to reach the deployed application."
  value       = "http://${aws_instance.todo_server.public_ip}:${var.app_port}"
}

output "ssh_command" {
  description = "SSH command to connect to the server. Replace <key-file> with your private key path."
  value       = "ssh -i <key-file>.pem ubuntu@${aws_instance.todo_server.public_ip}"
  sensitive   = false
}

output "ami_used" {
  description = "AMI ID that was used to create the instance."
  value       = local.resolved_ami
}
