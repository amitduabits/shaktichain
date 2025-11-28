#!/bin/bash
# Stop V2G Marketplace Docker containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
STOP_MODE="production"
REMOVE_VOLUMES=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            STOP_MODE="development"
            shift
            ;;
        --volumes|-v)
            REMOVE_VOLUMES="-v"
            shift
            ;;
        --all)
            # Stop both production and development
            echo -e "${YELLOW}Stopping all V2G Marketplace containers...${NC}"
            docker-compose down $REMOVE_VOLUMES 2>/dev/null || true
            docker-compose -f docker-compose.dev.yml down $REMOVE_VOLUMES 2>/dev/null || true
            echo -e "${GREEN}All containers stopped!${NC}"
            exit 0
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev       Stop development containers"
            echo "  --volumes   Remove volumes (WARNING: deletes data)"
            echo "  -v          Alias for --volumes"
            echo "  --all       Stop both production and development containers"
            echo "  --help      Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}Stopping V2G Marketplace...${NC}"

if [ "$STOP_MODE" = "development" ]; then
    docker-compose -f docker-compose.dev.yml down $REMOVE_VOLUMES
else
    docker-compose down $REMOVE_VOLUMES
fi

echo -e "${GREEN}V2G Marketplace stopped!${NC}"

if [ -n "$REMOVE_VOLUMES" ]; then
    echo -e "${YELLOW}Note: Volumes have been removed.${NC}"
fi
