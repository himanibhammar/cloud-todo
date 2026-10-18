"""
Deploy the Cloud To-Do application to EC2 via AWS SSM Run Command.
No SSH or .pem key required - uses the AWS SSM agent on the instance.

Run: python deploy_ssm.py
"""

import boto3
import base64
import time
import sys

INSTANCE_ID = "i-0b8e69504db4888f5"
REGION = "ap-south-1"
PROFILE = "cloud-todo"

DOCKER_COMPOSE = """services:
  todo-app:
    image: cloud-todo:latest
    container_name: cloud-todo-app
    restart: unless-stopped
    ports:
      - "80:5000"
    environment:
      DATABASE_PATH: /data/tasks.db
      ENABLE_CORS: "false"
    volumes:
      - todo-data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      start_period: 20s
      retries: 3
volumes:
  todo-data:
    driver: local
"""

DOCKERFILE = """FROM python:3.12-slim

RUN apt-get update \\
    && apt-get install -y --no-install-recommends curl \\
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appgroup \\
 && useradd  --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/     ./app/
COPY wsgi.py  .

RUN mkdir -p /data && chown appuser:appgroup /data

USER appuser

ENV DATABASE_PATH=/data/tasks.db \\
    PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \\
  CMD curl -f http://localhost:5000/api/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"]
"""

def send_command(ssm, commands, comment=""):
    """Send SSM run command and wait for result."""
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
        Comment=comment or commands[0][:40],
        TimeoutSeconds=300,
    )
    cmd_id = resp["Command"]["CommandId"]
    print(f"  Command ID: {cmd_id}")
    
    # Wait for completion
    for attempt in range(30):
        time.sleep(5)
        try:
            inv = ssm.get_command_invocation(
                CommandId=cmd_id,
                InstanceId=INSTANCE_ID,
            )
            status = inv["Status"]
            if status in ("Success", "Failed", "TimedOut", "Cancelled"):
                stdout = inv.get("StandardOutputContent", "").strip()
                stderr = inv.get("StandardErrorContent", "").strip()
                print(f"  Status: {status}")
                if stdout:
                    print(f"  Output:\n{stdout}")
                if stderr and status != "Success":
                    print(f"  Errors:\n{stderr}")
                return status == "Success", stdout, stderr
        except ssm.exceptions.InvocationDoesNotExist:
            pass
    
    return False, "", "Timed out waiting for command"


def b64(text):
    return base64.b64encode(text.encode()).decode()


def main():
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    ssm = session.client("ssm")
    
    print("\n" + "="*60)
    print("  Cloud To-Do — EC2 Deployment via AWS SSM")
    print("="*60)
    
    # Step 1: Verify Docker
    print("\n[1/6] Verifying Docker on EC2...")
    ok, out, _ = send_command(ssm, [
        "docker --version",
        "docker compose version",
        "echo DOCKER_OK"
    ], "Verify Docker")
    if not ok or "DOCKER_OK" not in out:
        print("ERROR: Docker not ready. Aborting.")
        sys.exit(1)
    
    # Step 2: Create directories
    print("\n[2/6] Setting up application directories...")
    ok, _, _ = send_command(ssm, [
        "mkdir -p /opt/cloud-todo/data /opt/cloud-todo/app/static",
        "chown -R ubuntu:ubuntu /opt/cloud-todo",
        "echo DIRS_OK"
    ], "Create directories")
    
    # Step 3: Write docker-compose.yml
    print("\n[3/6] Writing docker-compose.yml...")
    compose_b64 = b64(DOCKER_COMPOSE)
    ok, out, _ = send_command(ssm, [
        f"echo '{compose_b64}' | base64 -d > /opt/cloud-todo/docker-compose.yml",
        "echo COMPOSE_OK",
    ], "Write docker-compose")
    if not ok:
        print("ERROR: Failed to write compose file")
        sys.exit(1)
    
    # Step 4: Clone/write the full app on EC2
    # We'll create a minimal Dockerfile + requirements + app directly on EC2
    print("\n[4/6] Writing application files to EC2...")
    
    # Write requirements.txt
    reqs = "Flask==3.0.3\nFlask-CORS==4.0.1\ngunicorn==22.0.0\npytest==8.2.2\npytest-cov==5.0.0\n"
    ok, _, _ = send_command(ssm, [
        f"echo '{b64(reqs)}' | base64 -d > /opt/cloud-todo/requirements.txt",
        "echo REQS_OK"
    ], "Write requirements")
    
    # Write Dockerfile
    ok, _, _ = send_command(ssm, [
        f"echo '{b64(DOCKERFILE)}' | base64 -d > /opt/cloud-todo/Dockerfile",
        "echo DOCKERFILE_OK"
    ], "Write Dockerfile")
    
    # Step 5: Read and upload each Python/frontend source file
    import os
    src_files = [
        ("wsgi.py", "wsgi.py"),
        ("app/__init__.py", "app/__init__.py"),
        ("app/database.py", "app/database.py"),
        ("app/routes.py", "app/routes.py"),
        ("app/static/index.html", "app/static/index.html"),
        ("app/static/style.css", "app/static/style.css"),
        ("app/static/app.js", "app/static/app.js"),
    ]
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    for local_path, remote_name in src_files:
        full_path = os.path.join(script_dir, local_path)
        if not os.path.exists(full_path):
            print(f"  WARNING: {local_path} not found, skipping")
            continue
        
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        content_b64 = b64(content)
        remote_full = f"/opt/cloud-todo/{remote_name}"
        remote_dir = os.path.dirname(remote_full)
        
        print(f"  Uploading {local_path} ({len(content)} bytes)...")
        ok, _, err = send_command(ssm, [
            f"mkdir -p {remote_dir}",
            f"echo '{content_b64}' | base64 -d > {remote_full}",
            f"echo FILE_OK_{remote_name.replace('/', '_')}"
        ], f"Upload {remote_name}")
        
        if not ok:
            print(f"  ERROR uploading {local_path}: {err}")
    
    # Step 6: Build Docker image on EC2 and start
    print("\n[5/6] Building Docker image on EC2 (takes 1-2 min)...")
    ok, out, err = send_command(ssm, [
        "cd /opt/cloud-todo",
        "docker build -t cloud-todo:latest . 2>&1 | tail -5",
        "echo BUILD_OK"
    ], "Docker build")
    
    if not ok or "BUILD_OK" not in out:
        print(f"ERROR: Docker build failed\n{err}")
        sys.exit(1)
    
    # Step 7: Start with Docker Compose
    print("\n[6/6] Starting application with Docker Compose...")
    ok, out, _ = send_command(ssm, [
        "cd /opt/cloud-todo",
        "docker compose down --remove-orphans 2>/dev/null || true",
        "docker compose up -d",
        "sleep 20",
        "curl -sf http://localhost:80/api/health && echo HEALTH_OK || echo HEALTH_FAIL",
        "docker ps"
    ], "Start app")
    
    print("\n" + "="*60)
    if "HEALTH_OK" in out:
        print("  [SUCCESS] DEPLOYMENT SUCCESSFUL!")
        print(f"  Live URL:      http://52.66.250.18")
        print(f"  Health check:  http://52.66.250.18/api/health")
    else:
        print("  [FAILED] Health check failed. Check container logs on EC2.")
        print("  Run: aws ssm start-session --target i-0b8e69504db4888f5")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
