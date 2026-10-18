// ════════════════════════════════════════════════════════════════════════════
// Cloud To-Do — Jenkins Declarative Pipeline
//
// Prerequisites in Jenkins Credentials store:
//   - EC2_SSH_KEY   (type: SSH Username with private key)
//                   username = ubuntu, private key = your .pem content
//   - EC2_HOST      (type: Secret text) = public IP of the EC2 instance
//
// If your GitHub repo is private, also add:
//   - GITHUB_CREDS  (type: Username with password or SSH key)
//
// Agent requirements on the Jenkins controller / agent:
//   - Python 3 (with pip) accessible as 'python3' or 'python'
//   - Docker CLI accessible (Docker Desktop on Windows; socket on Linux)
//   - ssh and scp available (OpenSSH or PuTTY tools on Windows)
//
// SCM trigger: configure a GitHub webhook pointing to
//   http://<jenkins-url>/github-webhook/
// OR use the poll trigger below as a fallback.
// ════════════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    // Poll SCM every 2 minutes as a fallback when a webhook is not configured.
    // Delete this block once the GitHub webhook is working.
    triggers {
        pollSCM('H/2 * * * *')
    }

    environment {
        // Image name — no registry prefix (local build + SSH transfer)
        IMAGE_NAME    = "cloud-todo"
        // Tag = short Git commit SHA, set in a stage below
        IMAGE_TAG     = ""
        APP_PORT_HOST = "80"
        APP_PORT_CTR  = "5000"
        CONTAINER_NAME = "cloud-todo-app"
        REMOTE_APP_DIR = "/opt/cloud-todo"
        DEPLOY_USER   = "ubuntu"
    }

    stages {

        // ── Stage 1: Checkout ──────────────────────────────────────────────
        stage('Checkout') {
            steps {
                echo '📥 Checking out source code…'
                checkout scm
                script {
                    // Build a safe image tag from the short commit SHA
                    def sha = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = sha
                    echo "Commit SHA: ${env.IMAGE_TAG}"
                }
            }
        }

        // ── Stage 2: Test ──────────────────────────────────────────────────
        stage('Test') {
            steps {
                echo '🧪 Installing test dependencies and running Pytest…'
                script {
                    // Detect python3 or python
                    def py = sh(script: 'which python3 || which python', returnStdout: true).trim()
                    echo "Using Python: ${py}"

                    sh """
                        ${py} -m pip install --quiet -r requirements.txt
                        ${py} -m pytest tests/ -v --tb=short
                    """
                }
            }
            post {
                failure {
                    echo '❌ Tests failed — aborting pipeline.'
                }
                success {
                    echo '✅ All tests passed.'
                }
            }
        }

        // ── Stage 3: Build Docker image ────────────────────────────────────
        stage('Build') {
            steps {
                echo "🐳 Building Docker image ${env.IMAGE_NAME}:${env.IMAGE_TAG}…"
                sh """
                    docker build \
                        -t ${env.IMAGE_NAME}:${env.IMAGE_TAG} \
                        -t ${env.IMAGE_NAME}:latest \
                        .
                """
                echo "✅ Docker image built: ${env.IMAGE_NAME}:${env.IMAGE_TAG}"
            }
        }

        // ── Stage 4: Deployment readiness check ───────────────────────────
        stage('Deployment Readiness') {
            steps {
                echo '🔍 Verifying deployment prerequisites…'
                script {
                    // Verify the image exists locally
                    def imageCheck = sh(
                        script: "docker image inspect ${env.IMAGE_NAME}:${env.IMAGE_TAG} > /dev/null 2>&1 && echo OK || echo MISSING",
                        returnStdout: true
                    ).trim()

                    if (imageCheck != 'OK') {
                        error("Docker image ${env.IMAGE_NAME}:${env.IMAGE_TAG} not found — build may have failed.")
                    }

                    // Verify required files exist
                    if (!fileExists('docker-compose.yml')) {
                        error('docker-compose.yml is missing from the workspace.')
                    }

                    echo '✅ Deployment readiness checks passed.'
                }
            }
        }

        // ── Stage 5: Deploy ────────────────────────────────────────────────
        stage('Deploy') {
            steps {
                echo "🚀 Deploying ${env.IMAGE_NAME}:${env.IMAGE_TAG} to EC2…"

                // Retrieve the EC2 host from Jenkins Credentials
                withCredentials([
                    string(credentialsId: 'EC2_HOST', variable: 'EC2_IP'),
                    sshUserPrivateKey(
                        credentialsId:  'EC2_SSH_KEY',
                        keyFileVariable: 'SSH_KEY_FILE',
                        usernameVariable: 'SSH_USER'
                    )
                ]) {
                    script {
                        def sshOpts = "-o StrictHostKeyChecking=no -o BatchMode=yes -i ${SSH_KEY_FILE}"
                        def remote   = "${SSH_USER}@${EC2_IP}"

                        // 1. Save the Docker image as a tar archive
                        sh "docker save ${env.IMAGE_NAME}:${env.IMAGE_TAG} | gzip > cloud-todo-image.tar.gz"

                        // 2. Transfer the image to EC2
                        sh "scp ${sshOpts} cloud-todo-image.tar.gz ${remote}:${env.REMOTE_APP_DIR}/"

                        // 3. Transfer docker-compose.yml
                        sh "scp ${sshOpts} docker-compose.yml ${remote}:${env.REMOTE_APP_DIR}/"

                        // 4. Load the image and start the container on EC2
                        sh """
                            ssh ${sshOpts} ${remote} '
                                set -e

                                # Load the new image
                                docker load < ${env.REMOTE_APP_DIR}/cloud-todo-image.tar.gz

                                # Tag the loaded image so compose can find it
                                docker tag ${env.IMAGE_NAME}:${env.IMAGE_TAG} ${env.IMAGE_NAME}:latest

                                # Stop and replace the container (volume is preserved)
                                cd ${env.REMOTE_APP_DIR}
                                HOST_PORT=${env.APP_PORT_HOST} docker compose down --remove-orphans || true
                                HOST_PORT=${env.APP_PORT_HOST} docker compose up -d

                                # Clean up the tar file
                                rm -f ${env.REMOTE_APP_DIR}/cloud-todo-image.tar.gz
                            '
                        """
                    }
                }
            }
            post {
                // Clean up the local tar file regardless of success/failure
                always {
                    sh 'rm -f cloud-todo-image.tar.gz || true'
                }
            }
        }

        // ── Stage 6: Verify deployment ─────────────────────────────────────
        stage('Verify Deployment') {
            steps {
                echo '🏥 Verifying deployed application health…'
                withCredentials([string(credentialsId: 'EC2_HOST', variable: 'EC2_IP')]) {
                    script {
                        def appUrl  = "http://${EC2_IP}:${env.APP_PORT_HOST}"
                        def healthUrl = "${appUrl}/api/health"

                        // Retry health check for up to 60 seconds (container may still be starting)
                        def healthy = false
                        for (int attempt = 1; attempt <= 6; attempt++) {
                            echo "Health check attempt ${attempt}/6 → ${healthUrl}"
                            def rc = sh(
                                script: "curl -sf --max-time 10 ${healthUrl} > /dev/null",
                                returnStatus: true
                            )
                            if (rc == 0) {
                                healthy = true
                                break
                            }
                            if (attempt < 6) sleep(10)
                        }

                        if (!healthy) {
                            error("❌ Health check failed after 6 attempts. The application did not start correctly.")
                        }

                        echo """
╔══════════════════════════════════════════════════════╗
║           ✅  DEPLOYMENT SUCCESSFUL                  ║
╠══════════════════════════════════════════════════════╣
║  Application URL : ${appUrl}
║  Commit SHA      : ${env.IMAGE_TAG}
║  Image           : ${env.IMAGE_NAME}:${env.IMAGE_TAG}
╚══════════════════════════════════════════════════════╝
"""
                    }
                }
            }
        }

    } // end stages

    post {
        success {
            echo '🎉 Pipeline completed successfully!'
        }
        failure {
            echo '💥 Pipeline failed. Check the stage logs above.'
        }
        always {
            // Remove dangling Docker images to keep disk clean
            sh 'docker image prune -f || true'
        }
    }
}
