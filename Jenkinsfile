// ════════════════════════════════════════════════════════════════════════════
// Cloud To-Do — Jenkins Declarative Pipeline (Windows & Cross-Platform)
// ════════════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 15, unit: 'MINUTES')
    }

    environment {
        IMAGE_NAME     = "cloud-todo"
        EC2_PUBLIC_IP  = "52.66.250.18"
        AWS_DEFAULT_REGION = "ap-south-1"
        PYTHONIOENCODING = "utf-8"
    }

    stages {

        // ── Stage 1: Checkout ──────────────────────────────────────────────
        stage('Checkout') {
            steps {
                echo '📥 Checking out source code from GitHub…'
                checkout scm
                bat 'git log -1 --oneline'
            }
        }

        // ── Stage 2: Automated Tests ───────────────────────────────────────
        stage('Test') {
            steps {
                echo '🧪 Installing dependencies and running Pytest test suite…'
                bat '''
                    python -m pip install --quiet -r requirements.txt
                    python -m pytest tests/ -v --tb=short
                '''
            }
            post {
                failure {
                    echo '❌ Tests failed — aborting pipeline.'
                }
                success {
                    echo '✅ All 38 pytest tests passed successfully.'
                }
            }
        }

        // ── Stage 3: Docker Build ──────────────────────────────────────────
        stage('Docker Build') {
            steps {
                echo "🐳 Building Docker container image ${env.IMAGE_NAME}:latest…"
                bat """
                    docker build -t ${env.IMAGE_NAME}:latest .
                """
                echo '✅ Docker image built successfully.'
            }
        }

        // ── Stage 4: Deploy to AWS EC2 ─────────────────────────────────────
        stage('Deploy to EC2') {
            steps {
                echo "🚀 Deploying to AWS EC2 (${env.EC2_PUBLIC_IP}) via AWS SSM…"
                bat 'python deploy_ssm.py'
            }
            post {
                failure {
                    echo '❌ Deployment step failed.'
                }
                success {
                    echo '✅ Deployed to EC2.'
                }
            }
        }

        // ── Stage 5: Health Check & Verification ───────────────────────────
        stage('Verify Deployment') {
            steps {
                echo "🏥 Verifying live application health at http://${env.EC2_PUBLIC_IP}/api/health…"
                bat """
                    curl -s http://${env.EC2_PUBLIC_IP}/api/health
                """
                echo """
╔══════════════════════════════════════════════════════╗
║           ✅  PIPELINE EXECUTION SUCCESSFUL         ║
╠══════════════════════════════════════════════════════╣
║  Application URL : http://${env.EC2_PUBLIC_IP}
║  Health Check    : http://${env.EC2_PUBLIC_IP}/api/health
╚══════════════════════════════════════════════════════╝
"""
            }
        }

    } // end stages

    post {
        success {
            echo '🎉 All stages completed successfully!'
        }
        failure {
            echo '💥 Pipeline execution failed. Please check the logs above.'
        }
    }
}
