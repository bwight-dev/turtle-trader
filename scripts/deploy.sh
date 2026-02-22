#!/bin/bash
# Turtle Trading Bot - Deployment Script
# Usage: ./scripts/deploy.sh [command]
#
# Commands:
#   build    - Build Docker images
#   start    - Start services
#   stop     - Stop services
#   restart  - Restart services
#   logs     - Show logs
#   status   - Show service status
#   shell    - Open shell in container
#   test     - Run tests in container
#   deploy   - Full deployment (build + start)

set -e

# Configuration
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="turtle-trading"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
check_env() {
    if [ ! -f ".env" ]; then
        log_warn ".env file not found. Creating from .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info ".env file created. Please update with your credentials."
        else
            log_error "No .env.example found. Please create .env manually."
            exit 1
        fi
    fi
}

# Build Docker images
build() {
    log_info "Building Docker images..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME build
    log_info "Build complete!"
}

# Start services
start() {
    check_env
    log_info "Starting services..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d
    log_info "Services started!"
    status
}

# Stop services
stop() {
    log_info "Stopping services..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME down
    log_info "Services stopped!"
}

# Restart services
restart() {
    log_info "Restarting services..."
    stop
    start
}

# Show logs
logs() {
    local service=${1:-""}
    if [ -n "$service" ]; then
        docker compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f $service
    else
        docker compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f
    fi
}

# Show service status
status() {
    log_info "Service status:"
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
}

# Open shell in container
shell() {
    local service=${1:-"turtle-bot"}
    log_info "Opening shell in $service..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME exec $service /bin/bash
}

# Run tests in container
test_run() {
    log_info "Running tests..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME run --rm turtle-bot \
        python -m pytest tests/unit/ -v
}

# Full deployment
deploy() {
    log_info "Starting full deployment..."
    check_env
    build
    start
    log_info "Deployment complete!"
}

# Health check
health() {
    log_info "Checking health..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME exec turtle-bot \
        python -c "print('Health check passed!')" && \
        log_info "Bot is healthy!" || \
        log_error "Bot health check failed!"
}

# Pull latest changes and redeploy
update() {
    log_info "Updating deployment..."
    git pull
    build
    restart
    log_info "Update complete!"
}

# Clean up unused images and containers
cleanup() {
    log_info "Cleaning up..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME down --rmi local --volumes --remove-orphans
    docker system prune -f
    log_info "Cleanup complete!"
}

# Show help
show_help() {
    echo "Turtle Trading Bot - Deployment Script"
    echo ""
    echo "Usage: ./scripts/deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  build    - Build Docker images"
    echo "  start    - Start services"
    echo "  stop     - Stop services"
    echo "  restart  - Restart services"
    echo "  logs     - Show logs (optional: service name)"
    echo "  status   - Show service status"
    echo "  shell    - Open shell in container (optional: service name)"
    echo "  test     - Run tests in container"
    echo "  deploy   - Full deployment (build + start)"
    echo "  health   - Check service health"
    echo "  update   - Pull latest and redeploy"
    echo "  cleanup  - Remove containers, images, volumes"
    echo "  help     - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/deploy.sh deploy     # Full deployment"
    echo "  ./scripts/deploy.sh logs       # Show all logs"
    echo "  ./scripts/deploy.sh logs turtle-bot  # Show bot logs only"
    echo "  ./scripts/deploy.sh shell      # Open shell in bot container"
}

# Main command handler
case "${1:-help}" in
    build)
        build
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs "$2"
        ;;
    status)
        status
        ;;
    shell)
        shell "$2"
        ;;
    test)
        test_run
        ;;
    deploy)
        deploy
        ;;
    health)
        health
        ;;
    update)
        update
        ;;
    cleanup)
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
