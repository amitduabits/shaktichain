#!/bin/bash
# SHAKTI-CHAIN ML Monitoring Stack Setup Script

set -e

echo "=========================================="
echo "SHAKTI-CHAIN ML Monitoring Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running from correct directory
if [ ! -f "ml-service/docker-compose.yml" ]; then
    echo -e "${RED}Error: Please run this script from the ml/ directory${NC}"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."
echo ""

if ! command_exists docker; then
    echo -e "${RED}✗ Docker not found. Please install Docker first.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Docker installed${NC}"
fi

if ! command_exists docker-compose; then
    echo -e "${RED}✗ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Docker Compose installed${NC}"
fi

echo ""

# Setup .env file
echo "Setting up environment configuration..."
if [ ! -f "ml-service/.env" ]; then
    cp ml-service/.env.example ml-service/.env
    echo -e "${YELLOW}⚠ Created .env file from template${NC}"
    echo -e "${YELLOW}⚠ Please edit ml-service/.env to configure notification channels${NC}"
    echo ""
    echo "Required configurations:"
    echo "  - SLACK_WEBHOOK_URL: For Slack notifications"
    echo "  - PAGERDUTY_ROUTING_KEY: For PagerDuty alerts"
    echo "  - EMAIL settings: For email notifications"
    echo ""

    read -p "Press Enter to continue or Ctrl+C to exit and configure now..."
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p ml-service/prometheus/alerts
mkdir -p ml-service/alertmanager
mkdir -p monitoring/grafana/dashboards
mkdir -p docs/runbooks
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Start monitoring stack
echo "Starting monitoring stack..."
cd ml-service

# Pull images first
echo "Pulling Docker images..."
docker-compose pull prometheus alertmanager grafana mlflow redis

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to be ready
echo ""
echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo ""
echo "Checking service health..."

services=("ml-service:8000" "prometheus:9090" "alertmanager:9093" "grafana:3000" "mlflow:5000")
all_healthy=true

for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if curl -s -f "http://localhost:${port}" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ ${name} is running on port ${port}${NC}"
    else
        echo -e "${RED}✗ ${name} failed to start on port ${port}${NC}"
        all_healthy=false
    fi
done

echo ""

if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}=========================================="
    echo "✓ Monitoring stack is ready!"
    echo "==========================================${NC}"
    echo ""
    echo "Access points:"
    echo "  📊 Grafana:       http://localhost:3000 (admin/shakti123)"
    echo "  📈 Prometheus:    http://localhost:9090"
    echo "  🔔 AlertManager:  http://localhost:9093"
    echo "  🧪 MLflow:        http://localhost:5000"
    echo "  🤖 ML Service:    http://localhost:8000"
    echo "  📊 Metrics:       http://localhost:8000/metrics"
    echo ""
    echo "Next steps:"
    echo "  1. Configure notification channels in ml-service/.env"
    echo "  2. Restart AlertManager: docker-compose restart alertmanager"
    echo "  3. Open Grafana and explore dashboards"
    echo "  4. Review alert rules in prometheus/alerts/"
    echo "  5. Read documentation in docs/MONITORING.md"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f ml-service prometheus alertmanager grafana"
    echo ""
    echo "To stop services:"
    echo "  docker-compose down"
    echo ""
else
    echo -e "${YELLOW}=========================================="
    echo "⚠ Some services failed to start"
    echo "==========================================${NC}"
    echo ""
    echo "Check logs with:"
    echo "  docker-compose logs ml-service prometheus alertmanager grafana"
    echo ""
    echo "Try restarting:"
    echo "  docker-compose restart"
    echo ""
fi

# Test Prometheus targets
echo "Testing Prometheus configuration..."
sleep 5
targets=$(curl -s http://localhost:9090/api/v1/targets | grep -o '"health":"[^"]*"' | head -n 5)
if [ -n "$targets" ]; then
    echo -e "${GREEN}✓ Prometheus is scraping targets${NC}"
else
    echo -e "${YELLOW}⚠ Prometheus targets may not be configured correctly${NC}"
fi

echo ""

# Check if alerts are loaded
echo "Checking alert rules..."
alerts=$(curl -s http://localhost:9090/api/v1/rules | grep -o '"type":"alerting"' | wc -l)
if [ "$alerts" -gt 0 ]; then
    echo -e "${GREEN}✓ ${alerts} alert rules loaded${NC}"
else
    echo -e "${YELLOW}⚠ No alert rules found${NC}"
fi

echo ""
echo -e "${GREEN}Setup complete!${NC}"
