# ═══════════════════════════════════════════════════════════════════════════
# Terraform — Main infrastructure
# Resources: Security Group, EC2 instance
# ═══════════════════════════════════════════════════════════════════════════

# ── Resolve Ubuntu 22.04 LTS AMI (used when var.ami_id is empty) ─────────────
data "aws_ami" "ubuntu_22" {
  most_recent = true
  owners      = ["099720109477"] # Canonical (official Ubuntu publisher)

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  resolved_ami = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu_22.id
}

# ── Security Group ────────────────────────────────────────────────────────────
resource "aws_security_group" "todo_sg" {
  name        = "${var.project_name}-sg"
  description = "Allow SSH from trusted IP and HTTP from anywhere"

  # SSH — restricted to operator-supplied CIDR
  ingress {
    description = "SSH from operator"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  # HTTP — open to the internet (educational MVP)
  ingress {
    description = "HTTP from anywhere"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound traffic allowed (needed for apt, Docker Hub, etc.)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-sg"
    Project = var.project_name
  }
}

# ── EC2 Instance ──────────────────────────────────────────────────────────────
resource "aws_instance" "todo_server" {
  ami                    = local.resolved_ami
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.todo_sg.id]

  # Root volume — 20 GB is enough for Docker images and SQLite data
  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  # User-data bootstrap: update packages and install Docker
  user_data = <<-USERDATA
    #!/bin/bash
    set -euo pipefail
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg lsb-release

    # Docker official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Docker apt repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
      | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Add ubuntu user to docker group (avoids sudo for docker commands)
    usermod -aG docker ubuntu

    systemctl enable docker
    systemctl start docker
  USERDATA

  tags = {
    Name    = "${var.project_name}-server"
    Project = var.project_name
  }
}
