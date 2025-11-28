#!/bin/bash
# Run V2G Marketplace Docker containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
RUN_MODE="production"
DETACHED="-d"
BUILD=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            RUN_MODE="development"
            shift
            ;;
        --foreground|-f)
            DETACHED=""
            shift
            ;;
        --build)
            BUILD="--build"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev         Run in development mode with hot reload"
            echo "  --foreground  Run in foreground (default: detached)"
            echo "  -f            Alias for --foreground"
            echo "  --build       Build images before starting"
            echo "  --help        Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Create data directory if it doesn't exist
mkdir -p "$PROJECT_DIR/data"

echo -e "${GREEN}Starting V2G Marketplace...${NC}"

if [ "$RUN_MODE" = "development" ]; then
    echo -e "${YELLOW}Running in development mode with hot reload...${NC}"
    docker-compose -f docker-compose.dev.yml up $DETACHED $BUILD

    if [ -n "$DETACHED" ]; then
        echo ""
        echo -e "${GREEN}V2G Marketplace is running in development mode!${NC}"
        echo -e "${BLUE}Frontend:${NC} http://localhost:3000"
        echo -e "${BLUE}Backend API:${NC} http://localhost:8000"
        echo -e "${BLUE}API Docs:${NC} http://localhost:8000/docs"
        echo ""
        echo "View logs: docker-compose -f docker-compose.dev.yml logs -f"
        echo "Stop: ./scripts/docker-stop.sh --dev"
    fi
else
    echo -e "${YELLOW}Running in production mode...${NC}"
    docker-compose up $DETACHED $BUILD

    if [ -n "$DETACHED" ]; then
        echo ""
        echo -e "${GREEN}V2G Marketplace is running!${NC}"
        echo -e "${BLUE}Application:${NC} http://localhost"
        echo -e "${BLUE}Backend API:${NC} http://localhost:8000"
        echo -e "${BLUE}API Docs:${NC} http://localhost:8000/docs"
        echo ""
        echo "View logs: docker-compose logs -f"
        echo "Stop: ./scripts/docker-stop.sh"
    fi
fi
