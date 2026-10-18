#!/bin/bash
# Cloud To-Do — EC2 Deployment Script (runs via AWS SSM)
# This script installs the app on a fresh EC2 instance that already has Docker
# installed via user-data.

set -euo pipefail

APP_DIR="/opt/cloud-todo"
DATA_DIR="/opt/cloud-todo/data"
COMPOSE_URL="https://raw.githubusercontent.com/docker/compose/master/README.md"

echo "=== Cloud To-Do EC2 Deployment ==="
echo "Timestamp: $(date -u)"

# 1. Verify Docker is available (user-data installs it)
echo "--- Checking Docker..."
for i in {1..10}; do
    if docker --version &>/dev/null; then
        echo "✓ Docker ready: $(docker --version)"
        break
    fi
    echo "Waiting for Docker... attempt $i/10"
    sleep 10
done

# 2. Create app directories
echo "--- Creating directories..."
mkdir -p "$APP_DIR" "$DATA_DIR"
chown -R ubuntu:ubuntu "$APP_DIR"
chmod 755 "$DATA_DIR"

# 3. Write docker-compose.yml directly
echo "--- Writing docker-compose.yml..."
cat > "$APP_DIR/docker-compose.yml" << 'COMPOSE_EOF'
services:
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
COMPOSE_EOF

echo "✓ docker-compose.yml written"

# 4. Pull the Docker image from Docker Hub (cloud-todo built and pushed)
# OR load from tar if present
echo "--- Loading Docker image..."
if [ -f "$APP_DIR/cloud-todo-image.tar.gz" ]; then
    echo "Loading from tar file..."
    docker load < "$APP_DIR/cloud-todo-image.tar.gz"
fi

# 5. Start the application
echo "--- Starting application..."
cd "$APP_DIR"
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d

# 6. Wait and health check
echo "--- Waiting for health check..."
sleep 15
for i in {1..6}; do
    if curl -sf http://localhost:80/api/health; then
        echo ""
        echo "✅ Application is healthy!"
        break
    fi
    echo "Health check attempt $i/6..."
    sleep 10
done

echo "=== Deployment Complete ==="
echo "Application URL: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):80"
