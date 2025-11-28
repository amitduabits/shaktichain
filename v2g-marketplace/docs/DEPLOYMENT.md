# Deployment Guide

Complete guide for deploying V2G Marketplace in development, staging, and production environments.

---

## Table of Contents

- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
  - [AWS](#aws-deployment)
  - [Google Cloud Platform](#gcp-deployment)
  - [Microsoft Azure](#azure-deployment)
- [Environment Variables](#environment-variables)
- [SSL/HTTPS Setup](#sslhttps-setup)
- [Monitoring & Logging](#monitoring--logging)
- [Backup & Recovery](#backup--recovery)

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### Backend Setup

```bash
# Navigate to backend directory
cd v2g-marketplace/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`

### Frontend Setup

```bash
# Navigate to frontend directory
cd v2g-marketplace/frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/ -v --cov=api --cov=core

# Frontend tests
cd frontend
npm test

# E2E tests
npm run test:e2e
```

---

## Docker Deployment

### Quick Start

```bash
# Clone repository
git clone https://github.com/amitduabits/shaktichain.git
cd shaktichain/v2g-marketplace

# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Production Mode

```bash
# Using helper scripts
./scripts/docker-build.sh
./scripts/docker-run.sh

# Or using docker-compose directly
docker-compose -f docker-compose.yml up -d
```

**Access:**
- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Development Mode (Hot Reload)

```bash
# Using helper scripts
./scripts/docker-build.sh --dev
./scripts/docker-run.sh --dev

# Or using docker-compose directly
docker-compose -f docker-compose.dev.yml up -d
```

**Access:**
- Frontend: http://localhost:3000 (with hot reload)
- Backend API: http://localhost:8000 (with auto-reload)

### Docker Commands Reference

| Command | Description |
|---------|-------------|
| `./scripts/docker-build.sh` | Build production images |
| `./scripts/docker-build.sh --dev` | Build development images |
| `./scripts/docker-build.sh --no-cache` | Build without cache |
| `./scripts/docker-run.sh` | Run production containers |
| `./scripts/docker-run.sh --dev` | Run development containers |
| `./scripts/docker-run.sh --foreground` | Run in foreground |
| `./scripts/docker-stop.sh` | Stop production containers |
| `./scripts/docker-stop.sh --dev` | Stop development containers |
| `./scripts/docker-stop.sh --volumes` | Stop and remove volumes |

### Docker Compose Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Production deployment |
| `docker-compose.dev.yml` | Development with hot reload |

### Container Health Checks

Both containers include health checks:

```yaml
# Backend health check
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s

# Frontend health check
healthcheck:
  test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

## Cloud Deployment

### AWS Deployment

#### Option 1: EC2 with Docker

```bash
# 1. Launch EC2 instance (Ubuntu 22.04, t3.medium recommended)
# 2. SSH into instance
ssh -i your-key.pem ubuntu@your-instance-ip

# 3. Install Docker
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu
newgrp docker

# 4. Clone and deploy
git clone https://github.com/amitduabits/shaktichain.git
cd shaktichain/v2g-marketplace
docker-compose up -d

# 5. Configure security group
# - Allow inbound: 80 (HTTP), 443 (HTTPS), 22 (SSH)
```

#### Option 2: ECS with Fargate

```bash
# 1. Create ECR repositories
aws ecr create-repository --repository-name v2g-backend
aws ecr create-repository --repository-name v2g-frontend

# 2. Build and push images
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

docker build -t v2g-backend ./backend
docker tag v2g-backend:latest $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/v2g-backend:latest
docker push $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/v2g-backend:latest

docker build -t v2g-frontend ./frontend
docker tag v2g-frontend:latest $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/v2g-frontend:latest
docker push $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/v2g-frontend:latest

# 3. Create ECS cluster, task definitions, and services via AWS Console or Terraform
```

#### Option 3: Elastic Beanstalk

```bash
# 1. Install EB CLI
pip install awsebcli

# 2. Initialize Elastic Beanstalk
eb init -p docker v2g-marketplace

# 3. Create environment
eb create v2g-production

# 4. Deploy
eb deploy
```

#### AWS Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Cloud                             │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Route 53  │───▶│ CloudFront  │───▶│     ALB     │      │
│  │   (DNS)     │    │   (CDN)     │    │             │      │
│  └─────────────┘    └─────────────┘    └──────┬──────┘      │
│                                               │              │
│                     ┌─────────────────────────┼─────┐       │
│                     │        VPC              │     │       │
│                     │  ┌──────────────────────┴──┐  │       │
│                     │  │      ECS Cluster        │  │       │
│                     │  │  ┌────────┐ ┌────────┐  │  │       │
│                     │  │  │Backend │ │Frontend│  │  │       │
│                     │  │  │Fargate │ │Fargate │  │  │       │
│                     │  │  └───┬────┘ └────────┘  │  │       │
│                     │  └──────┼──────────────────┘  │       │
│                     │         │                     │       │
│                     │  ┌──────▼──────┐              │       │
│                     │  │    RDS      │              │       │
│                     │  │  (Optional) │              │       │
│                     │  └─────────────┘              │       │
│                     └───────────────────────────────┘       │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │     S3      │    │ CloudWatch  │    │   Secrets   │      │
│  │  (Storage)  │    │  (Logging)  │    │   Manager   │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

### GCP Deployment

#### Option 1: Compute Engine with Docker

```bash
# 1. Create VM instance
gcloud compute instances create v2g-marketplace \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=http-server,https-server

# 2. SSH into instance
gcloud compute ssh v2g-marketplace

# 3. Install Docker
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
newgrp docker

# 4. Deploy
git clone https://github.com/amitduabits/shaktichain.git
cd shaktichain/v2g-marketplace
docker-compose up -d

# 5. Create firewall rules
gcloud compute firewall-rules create allow-http \
  --allow tcp:80 --target-tags http-server
gcloud compute firewall-rules create allow-https \
  --allow tcp:443 --target-tags https-server
```

#### Option 2: Cloud Run

```bash
# 1. Build and push to Container Registry
gcloud builds submit --tag gcr.io/$PROJECT_ID/v2g-backend ./backend
gcloud builds submit --tag gcr.io/$PROJECT_ID/v2g-frontend ./frontend

# 2. Deploy backend
gcloud run deploy v2g-backend \
  --image gcr.io/$PROJECT_ID/v2g-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

# 3. Deploy frontend
gcloud run deploy v2g-frontend \
  --image gcr.io/$PROJECT_ID/v2g-frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

#### Option 3: Google Kubernetes Engine (GKE)

```bash
# 1. Create GKE cluster
gcloud container clusters create v2g-cluster \
  --zone us-central1-a \
  --num-nodes 3

# 2. Get credentials
gcloud container clusters get-credentials v2g-cluster

# 3. Apply Kubernetes manifests
kubectl apply -f k8s/
```

---

### Azure Deployment

#### Option 1: Azure VM with Docker

```bash
# 1. Create resource group
az group create --name v2g-rg --location eastus

# 2. Create VM
az vm create \
  --resource-group v2g-rg \
  --name v2g-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys

# 3. Open ports
az vm open-port --port 80 --resource-group v2g-rg --name v2g-vm
az vm open-port --port 443 --resource-group v2g-rg --name v2g-vm

# 4. SSH and deploy
ssh azureuser@<public-ip>
# Follow Docker installation steps from AWS section
```

#### Option 2: Azure Container Instances

```bash
# 1. Create Azure Container Registry
az acr create --resource-group v2g-rg --name v2gacr --sku Basic

# 2. Build and push images
az acr build --registry v2gacr --image v2g-backend:latest ./backend
az acr build --registry v2gacr --image v2g-frontend:latest ./frontend

# 3. Deploy container group
az container create \
  --resource-group v2g-rg \
  --name v2g-containers \
  --image v2gacr.azurecr.io/v2g-backend:latest \
  --dns-name-label v2g-marketplace \
  --ports 80 8000
```

#### Option 3: Azure Kubernetes Service (AKS)

```bash
# 1. Create AKS cluster
az aks create \
  --resource-group v2g-rg \
  --name v2g-aks \
  --node-count 2 \
  --generate-ssh-keys

# 2. Get credentials
az aks get-credentials --resource-group v2g-rg --name v2g-aks

# 3. Deploy with kubectl
kubectl apply -f k8s/
```

---

## Environment Variables

### Backend Environment Variables

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `JWT_SECRET` | `v2g-marketplace-secret-key-change-in-production` | JWT signing key | **Yes (production)** |
| `DATABASE_URL` | `sqlite:///data/v2g.db` | Database connection string | No |
| `DEBUG` | `0` | Enable debug mode | No |
| `PYTHONUNBUFFERED` | `1` | Disable Python output buffering | No |
| `CORS_ORIGINS` | `*` | Allowed CORS origins | No |
| `LOG_LEVEL` | `INFO` | Logging level | No |

### Frontend Environment Variables

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `VITE_API_URL` | `/api` | Backend API URL | No |

### Setting Environment Variables

#### Docker Compose

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - JWT_SECRET=your-super-secret-key-here
      - DATABASE_URL=sqlite:///data/v2g.db
      - LOG_LEVEL=INFO
```

#### .env File

```bash
# .env
JWT_SECRET=your-super-secret-key-here
DATABASE_URL=sqlite:///data/v2g.db
DEBUG=0
```

#### Cloud Providers

**AWS (Secrets Manager):**
```bash
aws secretsmanager create-secret \
  --name v2g/jwt-secret \
  --secret-string "your-super-secret-key"
```

**GCP (Secret Manager):**
```bash
echo -n "your-super-secret-key" | \
  gcloud secrets create jwt-secret --data-file=-
```

**Azure (Key Vault):**
```bash
az keyvault secret set \
  --vault-name v2g-vault \
  --name jwt-secret \
  --value "your-super-secret-key"
```

---

## SSL/HTTPS Setup

### Option 1: Let's Encrypt with Certbot (Recommended)

```bash
# 1. Install Certbot
sudo apt install certbot python3-certbot-nginx

# 2. Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# 3. Auto-renewal is configured automatically
# Test with:
sudo certbot renew --dry-run
```

### Option 2: Nginx with SSL

Create `nginx-ssl.conf`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;

    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Option 3: Cloud Load Balancer SSL

**AWS ALB:**
```bash
# Upload certificate to ACM
aws acm import-certificate \
  --certificate fileb://cert.pem \
  --private-key fileb://privkey.pem \
  --certificate-chain fileb://chain.pem

# Configure ALB listener for HTTPS
```

**GCP:**
```bash
# Create managed SSL certificate
gcloud compute ssl-certificates create v2g-cert \
  --domains yourdomain.com
```

---

## Monitoring & Logging

### Docker Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend

# View last 100 lines
docker-compose logs --tail=100
```

### Prometheus + Grafana Setup

```yaml
# Add to docker-compose.yml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### Cloud Monitoring

**AWS CloudWatch:**
```bash
# Install CloudWatch agent
sudo yum install amazon-cloudwatch-agent

# Configure and start
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -c file:config.json -s
```

**GCP Cloud Logging:**
```bash
# Logs are automatically collected from GKE/Cloud Run
# View logs:
gcloud logging read "resource.type=cloud_run_revision"
```

---

## Backup & Recovery

### SQLite Database Backup

```bash
# Manual backup
cp data/v2g.db data/v2g.db.backup.$(date +%Y%m%d)

# Automated daily backup (cron)
0 2 * * * cp /path/to/data/v2g.db /path/to/backups/v2g.db.$(date +\%Y\%m\%d)

# Restore from backup
cp data/v2g.db.backup.20240115 data/v2g.db
```

### Docker Volume Backup

```bash
# Backup volume
docker run --rm \
  -v v2g-marketplace_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/data-backup.tar.gz /data

# Restore volume
docker run --rm \
  -v v2g-marketplace_data:/data \
  -v $(pwd)/backups:/backup \
  alpine sh -c "cd /data && tar xzf /backup/data-backup.tar.gz --strip 1"
```

### Cloud Backup

**AWS S3:**
```bash
# Upload backup to S3
aws s3 cp data/v2g.db s3://your-bucket/backups/v2g.db.$(date +%Y%m%d)

# Sync backups directory
aws s3 sync ./backups s3://your-bucket/backups/
```

**GCP Cloud Storage:**
```bash
gsutil cp data/v2g.db gs://your-bucket/backups/v2g.db.$(date +%Y%m%d)
```

---

## Production Checklist

Before deploying to production, ensure:

- [ ] `JWT_SECRET` is set to a secure, unique value
- [ ] SSL/HTTPS is configured
- [ ] Database backups are scheduled
- [ ] Monitoring and alerting is configured
- [ ] Rate limiting is enabled
- [ ] CORS is properly configured
- [ ] Firewall rules restrict unnecessary access
- [ ] Logs are being collected and retained
- [ ] Health checks are passing
- [ ] Load testing has been performed

See [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) for a complete pre-launch checklist.
