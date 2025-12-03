# Deployment Guide

Complete guide for deploying the V2G Marketplace in development, staging, and production environments.

## Table of Contents

- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Environment Variables](#environment-variables)
- [SSL/HTTPS Setup](#ssl-https-setup)
- [Database Management](#database-management)
- [Monitoring & Logging](#monitoring--logging)
- [Troubleshooting](#troubleshooting)

---

## Local Development

### Prerequisites

- **Python**: 3.9 or higher
- **Node.js**: 18 or higher
- **npm**: 9 or higher
- **Git**: Latest version
- **Optional**: Docker & Docker Compose

### Backend Setup

```bash
# Clone repository
git clone <repository-url>
cd v2g-marketplace

# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python -c "from core.database import init_db; init_db()"

# Run tests
pytest tests/ -v --cov

# Start development server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Backend will be available at**: http://localhost:8000

### Frontend Setup

```bash
# Navigate to frontend (in new terminal)
cd frontend

# Install dependencies
npm install

# Create environment file
cp .env.example .env.development
# Edit with backend URL: VITE_API_URL=http://localhost:8000

# Start development server with hot reload
npm run dev
```

**Frontend will be available at**: http://localhost:5173

### Blockchain Setup (Local)

```bash
# In separate terminal, start Hardhat node
cd ../shakti-contracts
npx hardhat node

# Deploy contracts (in another terminal)
npx hardhat run scripts/deploy.js --network localhost

# Update backend .env with contract addresses
```

---

## Docker Deployment

Docker provides isolated, reproducible environments for all deployment scenarios.

### Production Deployment

**1. Build and Start**:
```bash
# Build images
docker-compose build

# Start containers in detached mode
docker-compose up -d

# Check logs
docker-compose logs -f
```

**2. Verify Deployment**:
```bash
# Check container status
docker-compose ps

# Test frontend
curl http://localhost

# Test backend
curl http://localhost:8000/health

# Test API docs
open http://localhost:8000/docs
```

**3. Stop and Clean**:
```bash
# Stop containers
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Development Deployment (Hot Reload)

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Watch logs
docker-compose -f docker-compose.dev.yml logs -f

# Access points:
# - Frontend: http://localhost:3000
# - Backend: http://localhost:8000
```

### Docker Compose Configuration

**Production** (`docker-compose.yml`):
```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///data/v2g.db
      - PYTHONUNBUFFERED=1
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  data:
```

**Development** (`docker-compose.dev.yml`):
```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - ./data:/app/data
    environment:
      - DEBUG=1
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://localhost:8000
    command: npm run dev -- --host 0.0.0.0
```

---

## Cloud Deployment

### AWS Deployment

#### Option 1: ECS (Elastic Container Service)

**Architecture**:
```
Internet -> ALB -> ECS Tasks (Backend + Frontend) -> RDS/SQLite
                                   |
                                   v
                            Blockchain Node
```

**Setup Steps**:

1. **Prepare ECR (Elastic Container Registry)**:
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Create repositories
aws ecr create-repository --repository-name v2g-backend
aws ecr create-repository --repository-name v2g-frontend

# Build and push images
docker build -t v2g-backend ./backend
docker tag v2g-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/v2g-backend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/v2g-backend:latest

docker build -t v2g-frontend ./frontend
docker tag v2g-frontend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/v2g-frontend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/v2g-frontend:latest
```

2. **Create ECS Cluster**:
```bash
aws ecs create-cluster --cluster-name v2g-marketplace
```

3. **Create Task Definition** (`task-definition.json`):
```json
{
  "family": "v2g-marketplace",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/v2g-backend:latest",
      "portMappings": [{"containerPort": 8000}],
      "environment": [
        {"name": "DATABASE_URL", "value": "sqlite:///data/v2g.db"},
        {"name": "JWT_SECRET_KEY", "value": "${JWT_SECRET}"}
      ]
    },
    {
      "name": "frontend",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/v2g-frontend:latest",
      "portMappings": [{"containerPort": 80}],
      "dependsOn": [{"containerName": "backend", "condition": "START"}]
    }
  ]
}
```

4. **Create Service**:
```bash
aws ecs create-service \
  --cluster v2g-marketplace \
  --service-name v2g-service \
  --task-definition v2g-marketplace \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

#### Option 2: EC2 with Docker

```bash
# Launch EC2 instance (Amazon Linux 2)
# Install Docker
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repository
git clone <repository-url>
cd v2g-marketplace

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env

# Deploy
docker-compose up -d

# Configure reverse proxy (Nginx)
sudo yum install -y nginx
sudo cp nginx.conf /etc/nginx/nginx.conf
sudo service nginx start
```

### GCP Deployment (Google Cloud Platform)

**Using Cloud Run**:

```bash
# Setup gcloud CLI
gcloud auth login
gcloud config set project v2g-marketplace

# Build and push to GCR
gcloud builds submit --tag gcr.io/v2g-marketplace/backend ./backend
gcloud builds submit --tag gcr.io/v2g-marketplace/frontend ./frontend

# Deploy to Cloud Run
gcloud run deploy v2g-backend \
  --image gcr.io/v2g-marketplace/backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=sqlite:///data/v2g.db

gcloud run deploy v2g-frontend \
  --image gcr.io/v2g-marketplace/frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Azure Deployment

**Using Azure Container Instances**:

```bash
# Login to Azure
az login

# Create resource group
az group create --name v2g-marketplace --location eastus

# Create container registry
az acr create --resource-group v2g-marketplace \
  --name v2gmarketplace --sku Basic

# Build and push images
az acr build --registry v2gmarketplace --image backend:latest ./backend
az acr build --registry v2gmarketplace --image frontend:latest ./frontend

# Deploy container group
az container create \
  --resource-group v2g-marketplace \
  --name v2g-containers \
  --image v2gmarketplace.azurecr.io/backend:latest \
  --dns-name-label v2g-marketplace \
  --ports 8000 80
```

---

## Environment Variables

### Backend Configuration

Create `backend/.env` file:

```env
# Application
ENV=production  # development, staging, production
DEBUG=0
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=sqlite:///./data/v2g.db
# For PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/v2g_marketplace

# JWT Authentication
JWT_SECRET_KEY=your-256-bit-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# Blockchain
BLOCKCHAIN_NETWORK=polygon  # hardhat, polygon_amoy, polygon
HARDHAT_RPC_URL=http://127.0.0.1:8545
POLYGON_RPC_URL=https://polygon-rpc.com
POLYGON_AMOY_RPC_URL=https://rpc-amoy.polygon.technology/
PRIVATE_KEY=0xYourPrivateKeyHere

# Contract Addresses (after deployment)
SHAKTI_TOKEN_ADDRESS=0x...
ENERGY_AUCTION_ADDRESS=0x...
STAKING_POOL_ADDRESS=0x...
REPUTATION_SYSTEM_ADDRESS=0x...

# Blockchain Sync
SYNC_POLL_INTERVAL=12  # seconds
SYNC_BATCH_SIZE=1000
SYNC_START_BLOCK=0

# CORS
CORS_ORIGINS=http://localhost,http://localhost:3000,https://yourdomain.com

# Rate Limiting
RATE_LIMIT_ENABLED=1
RATE_LIMIT_PER_MINUTE=100

# Monitoring
PROMETHEUS_ENABLED=1
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

### Frontend Configuration

Create `frontend/.env.production`:

```env
# API Configuration
VITE_API_URL=https://api.yourdomain.com
VITE_WS_URL=wss://api.yourdomain.com/ws

# Blockchain
VITE_CHAIN_ID=137  # Polygon Mainnet
VITE_CHAIN_NAME=Polygon
VITE_RPC_URL=https://polygon-rpc.com

# Contract Addresses
VITE_SHAKTI_TOKEN_ADDRESS=0x...
VITE_ENERGY_AUCTION_ADDRESS=0x...
VITE_STAKING_POOL_ADDRESS=0x...

# Features
VITE_ENABLE_BLOCKCHAIN=true
VITE_ENABLE_ANALYTICS=true

# Analytics
VITE_GA_TRACKING_ID=G-XXXXXXXXXX
```

### Generating Secure Keys

```bash
# Generate JWT secret key (256-bit)
openssl rand -hex 32

# Generate Ethereum private key
# Use a wallet like MetaMask or hardware wallet
# NEVER commit private keys to version control
```

---

## SSL/HTTPS Setup

### Using Let's Encrypt with Nginx

**1. Install Certbot**:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Amazon Linux
sudo yum install -y certbot python3-certbot-nginx
```

**2. Obtain Certificate**:
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

**3. Nginx Configuration** (`/etc/nginx/nginx.conf`):
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
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://localhost:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**4. Auto-renewal**:
```bash
# Test renewal
sudo certbot renew --dry-run

# Setup cron job
sudo crontab -e
# Add: 0 3 * * * certbot renew --quiet
```

---

## Database Management

### SQLite (Default)

**Backup**:
```bash
# Backup database
sqlite3 data/v2g.db ".backup 'backup/v2g_$(date +%Y%m%d_%H%M%S).db'"

# Automate backups (cron)
0 2 * * * /path/to/backup_script.sh
```

**Restore**:
```bash
sqlite3 data/v2g.db < backup/v2g_20251203_020000.db
```

### Migrating to PostgreSQL

**1. Install PostgreSQL**:
```bash
sudo apt-get install postgresql postgresql-contrib
```

**2. Create Database**:
```bash
sudo -u postgres psql
CREATE DATABASE v2g_marketplace;
CREATE USER v2g_user WITH PASSWORD 'securepassword';
GRANT ALL PRIVILEGES ON DATABASE v2g_marketplace TO v2g_user;
\q
```

**3. Update Backend .env**:
```env
DATABASE_URL=postgresql://v2g_user:securepassword@localhost:5432/v2g_marketplace
```

**4. Migrate Data**:
```bash
# Export from SQLite
sqlite3 data/v2g.db .dump > export.sql

# Import to PostgreSQL (after conversion)
psql -U v2g_user -d v2g_marketplace -f export_postgres.sql
```

---

## Monitoring & Logging

### Prometheus + Grafana

**1. Setup Prometheus** (`prometheus.yml`):
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'v2g-backend'
    static_configs:
      - targets: ['localhost:8000']
```

**2. Run Prometheus**:
```bash
docker run -d -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

**3. Setup Grafana**:
```bash
docker run -d -p 3001:3000 grafana/grafana
```

Access Grafana at http://localhost:3001, add Prometheus data source.

### Centralized Logging (ELK Stack)

```bash
# docker-compose-logging.yml
version: '3.8'
services:
  elasticsearch:
    image: elasticsearch:8.5.0
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node

  logstash:
    image: logstash:8.5.0
    ports:
      - "5000:5000"
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: kibana:8.5.0
    ports:
      - "5601:5601"
```

### Sentry Error Tracking

```bash
# Install Sentry SDK
pip install sentry-sdk[fastapi]

# Configure in backend/api/main.py
import sentry_sdk
sentry_sdk.init(
    dsn="https://your-dsn@sentry.io/project-id",
    environment="production"
)
```

---

## Troubleshooting

### Common Issues

**1. Backend Won't Start**:
```bash
# Check logs
docker-compose logs backend

# Common causes:
# - Port 8000 already in use
# - Database connection failed
# - Missing environment variables
```

**2. Frontend Can't Reach Backend**:
```bash
# Check CORS configuration
# Verify VITE_API_URL in frontend/.env
# Test backend directly:
curl http://localhost:8000/health
```

**3. Database Locked**:
```bash
# SQLite only allows one writer at a time
# Check for hung processes:
ps aux | grep python
# Kill if necessary:
kill -9 <PID>
```

**4. Blockchain Connection Failed**:
```bash
# Verify RPC URL is accessible
curl -X POST $POLYGON_RPC_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Check contract addresses are correct
```

**5. Memory Issues**:
```bash
# Increase Docker memory limit
# In Docker Desktop: Settings > Resources > Memory

# Monitor memory usage
docker stats
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/health/ready

# Metrics
curl http://localhost:8000/metrics
```

### Log Analysis

```bash
# View live logs
docker-compose logs -f --tail=100

# Search for errors
docker-compose logs | grep ERROR

# Filter by service
docker-compose logs backend | grep "simulation"
```

---

## Production Checklist

Before going live:

- [ ] All tests passing
- [ ] Environment variables configured
- [ ] SSL/HTTPS enabled
- [ ] Database backups configured
- [ ] Rate limiting enabled
- [ ] Monitoring configured (Prometheus/Grafana)
- [ ] Error tracking configured (Sentry)
- [ ] Logging centralized (ELK/CloudWatch)
- [ ] Domain configured with DNS
- [ ] Firewall rules configured
- [ ] Regular security updates scheduled
- [ ] Backup/restore procedures documented
- [ ] Load testing completed
- [ ] Disaster recovery plan documented

---

**For deployment support, contact: devops@v2g-marketplace.com**
