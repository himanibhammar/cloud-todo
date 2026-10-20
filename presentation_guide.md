# Cloud To-Do App — AWS EC2 Deployment & Presentation Guide

> [!IMPORTANT]
> **EC2 Instance is Active and Running**: Your instance is intentionally kept **RUNNING** so it is live and ready for your presentation tomorrow. It will not be stopped.

---

## 1. Quick Access Links

| Resource | URL | Description |
|---|---|---|
| **Live Web Application** | [http://52.66.250.18](http://52.66.250.18) | Full interactive To-Do web app (accessible from any device/browser) |
| **Health Check API** | [http://52.66.250.18/api/health](http://52.66.250.18/api/health) | Returns `{"database": true, "status": "healthy"}` |
| **Tasks REST API** | [http://52.66.250.18/api/tasks](http://52.66.250.18/api/tasks) | JSON list of tasks |
| **GitHub Repository** | [https://github.com/himanibhammar/cloud-todo](https://github.com/himanibhammar/cloud-todo) | Full source code with Dockerfile, Terraform, and Jenkinsfile |
| **Jenkins Dashboard** | [http://localhost:8080](http://localhost:8080) | Local Jenkins CI/CD controller |

---

## 2. Infrastructure Details

- **Cloud Provider:** Amazon Web Services (AWS)
- **Region:** `ap-south-1` (Mumbai)
- **Instance ID:** `i-0b8e69504db4888f5`
- **Instance Type:** `t3.micro` (AWS Free Tier eligible)
- **OS:** Ubuntu 22.04 LTS
- **Public IPv4:** `52.66.250.18`
- **Security Group:** `cloud-todo-sg` (`sg-0d6652cee7aebc5e9`)
  - Port 80 (HTTP) open to `0.0.0.0/0` (worldwide web access)
  - Port 22 (SSH) restricted to authorized operator IP
- **Management:** AWS Systems Manager (SSM) with IAM Role `cloud-todo-ssm-role`
- **Container Engine:** Docker `29.9.1` + Docker Compose `v5.6.0`
- **Restart Policy:** `unless-stopped` (auto-recovers if instance is rebooted)

---

## 3. Architecture Overview

```mermaid
graph TD
    Client["Browser / Evaluator / Ma'am"] -->|HTTP Port 80| IGW["AWS Internet Gateway"]
    IGW --> VPC["VPC: vpc-0b72ce45e85be014d"]
    VPC --> SG["Security Group: cloud-todo-sg"]
    SG --> EC2["EC2 Instance (t3.micro, Ubuntu 22.04)"]
    
    subgraph EC2["EC2 Instance: 52.66.250.18"]
        Docker["Docker Engine & Compose"]
        subgraph Container["Docker Container: cloud-todo-app"]
            Gunicorn["Gunicorn WSGI Server"]
            Flask["Flask Web Application"]
            Gunicorn --> Flask
        end
        Volume[("Docker Volume: todo-data (/data/tasks.db)")]
        Container --> Volume
    end

    Admin["DevOps Admin / Script"] -->|AWS SSM Agent (Encrypted)| EC2
```

---

## 4. Key Talking Points for Your Presentation

When presenting to your evaluator or professor:

1. **Infrastructure as Code (IaC):**
   - The infrastructure was provisioned using **Terraform**, managing the EC2 instance, security groups, and ingress/egress rules deterministically.

2. **Containerization & Reproducibility:**
   - The Flask app and its dependencies are packaged into a lightweight, multi-stage Docker image (`python:3.12-slim`).
   - Runs with an unprivileged non-root user (`appuser:1001`) following Docker security best practices.

3. **High Availability & Health Probes:**
   - Built-in `/api/health` probe checks database read/write connectivity.
   - Docker Compose manages automatic container restart policies (`unless-stopped`) and health monitoring.

4. **Persistent Data Storage:**
   - Tasks are stored in SQLite mounted via a named Docker volume (`todo-data`), ensuring no data loss when containers restart or update.

5. **Security & Management:**
   - Zero-trust remote management via **AWS Systems Manager (SSM)**, removing reliance on open SSH ports or circulating private keys.

---

## 5. Live Demo Steps to Show

1. **Open the Web UI:**
   Navigate to [http://52.66.250.18](http://52.66.250.18) in your browser.
2. **Add a Task:**
   Type a new task (e.g., *"Complete cloud project review"*) and click **Add**.
3. **Mark Complete / Filter:**
   Click the checkbox to mark the task complete. Switch between **All**, **Active**, and **Completed** filters.
4. **Show API Response:**
   Open a new tab at [http://52.66.250.18/api/tasks](http://52.66.250.18/api/tasks) and show the live JSON data structure.
5. **Show Health Endpoint:**
   Open [http://52.66.250.18/api/health](http://52.66.250.18/api/health) to show live system status (`status: healthy`).
