#!/bin/bash
# Build Docker images for V2G Marketplace

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building V2G Marketplace Docker images...${NC}"

# Parse arguments
BUILD_MODE="production"
NO_CACHE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            BUILD_MODE="development"
            shift
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev       Build for development (uses docker-compose.dev.yml)"
            echo "  --no-cache  Build without using cache"
            echo "  --help      Show this help message"
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

if [ "$BUILD_MODE" = "development" ]; then
    echo -e "${YELLOW}Building in development mode...${NC}"
    docker-compose -f docker-compose.dev.yml build $NO_CACHE
else
    echo -e "${YELLOW}Building in production mode...${NC}"
    docker-compose build $NO_CACHE
fi

echo -e "${GREEN}Build complete!${NC}"
echo ""
echo "To run the application:"
if [ "$BUILD_MODE" = "development" ]; then
    echo "  ./scripts/docker-run.sh --dev"
else
    echo "  ./scripts/docker-run.sh"
fi
