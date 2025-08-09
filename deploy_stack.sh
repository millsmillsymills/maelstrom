#!/bin/bash
# Enhanced monitoring stack deployment with profile support
# Supports both base configuration and heavy services via profiles

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_COMPOSE_FILE="${SCRIPT_DIR}/base.yml"
PROD_COMPOSE_FILE="${SCRIPT_DIR}/prod.yml"

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS] [PROFILES...]

Deploy the monitoring stack with optional heavy service profiles.

OPTIONS:
    -h, --help          Show this help message
    --base-only        Deploy only base services (no heavy services)
    --all-profiles     Deploy all heavy service profiles
    --compatibility    Use Docker Swarm compatibility mode
    --dry-run          Show what would be deployed without doing it
    --no-pull         Skip pulling images before deploy
    --stop             Stop all services
    --down             Stop and remove all services
    --skip-backup      Skip post-deploy GitHub backup

AVAILABLE PROFILES:
    ml-analytics       ML Analytics services (ml-analytics, data-optimizer, resource-optimizer)  
    wazuh-stack        Wazuh SIEM stack (elasticsearch, manager, dashboard)
    security-stack     Security monitoring (suricata, zeek, ntopng, threat-intelligence)
    analytics-stack    Analytics services (jaeger, self-healing, maelstrom-monitor)

EXAMPLES:
    $0                              # Deploy base services only
    $0 ml-analytics                 # Deploy base + ML analytics
    $0 wazuh-stack security-stack   # Deploy base + Wazuh + security monitoring
    $0 --all-profiles               # Deploy everything
    $0 --compatibility ml-analytics # Deploy with swarm compatibility mode
    $0 --stop                       # Stop all services
    $0 --down                       # Stop and remove all services

EOF
}

# Parse command line arguments
PROFILES=()
BASE_ONLY=false
ALL_PROFILES=false
COMPATIBILITY=false
DRY_RUN=false
NO_PULL=false
SKIP_BACKUP=false
STOP_SERVICES=false
DOWN_SERVICES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        --base-only)
            BASE_ONLY=true
            shift
            ;;
        --all-profiles)
            ALL_PROFILES=true
            shift
            ;;
        --compatibility)
            COMPATIBILITY=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-pull)
            NO_PULL=true
            shift
            ;;
        --stop)
            STOP_SERVICES=true
            shift
            ;;
        --down)
            DOWN_SERVICES=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        ml-analytics|wazuh-stack|security-stack|analytics-stack)
            PROFILES+=("$1")
            shift
            ;;
        -*) 
            error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            error "Unknown profile: $1"
            error "Available profiles: ml-analytics, wazuh-stack, security-stack, analytics-stack"
            exit 1
            ;;
    esac
done

# Set all profiles if requested
if [[ ${ALL_PROFILES} == true ]]; then
    PROFILES=("ml-analytics" "wazuh-stack" "security-stack" "analytics-stack")
fi

# Choose Compose binary (prefer v2 plugin)
get_compose_bin() {
    if docker compose version >/dev/null 2>&1; then
        echo "docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        echo "docker-compose"
    else
        error "Docker Compose is not installed (neither plugin nor v1)"
        exit 1
    fi
}

# Build Docker Compose command using selected binary
build_compose_command() {
    local compose_bin
    compose_bin=$(get_compose_bin)
    local cmd="${compose_bin}"
    
    # Add base compose file
    cmd="${cmd} -f ${BASE_COMPOSE_FILE}"
    
    # Add production overlay if not base-only
    if [[ ${BASE_ONLY} == false && ${#PROFILES[@]} -gt 0 ]]; then
        cmd="${cmd} -f ${PROD_COMPOSE_FILE}"
        
        # Add profiles
        for profile in "${PROFILES[@]}"; do
            cmd="${cmd} --profile ${profile}"
        done
    fi
    
    echo "${cmd}"
}

# Validate compose files exist
validate_compose_files() {
    if [[ ! -f "${BASE_COMPOSE_FILE}" ]]; then
        error "Base compose file not found: ${BASE_COMPOSE_FILE}"
        exit 1
    fi
    
    if [[ ${BASE_ONLY} == false && ${#PROFILES[@]} -gt 0 ]]; then
        if [[ ! -f "${PROD_COMPOSE_FILE}" ]]; then
            error "Production compose file not found: ${PROD_COMPOSE_FILE}"
            exit 1
        fi
    fi
    
    success "Compose files validated"
}

# Validate Docker Compose configuration
validate_configuration() {
    local compose_cmd
    compose_cmd=$(build_compose_command)
    
    log "Validating Docker Compose configuration..."
    if ${compose_cmd} config --quiet; then
        success "Configuration validation passed"
    else
        error "Configuration validation failed"
        exit 1
    fi
}

# Check Docker daemon status
check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker is not available"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running"
        exit 1
    fi
    
    success "Docker daemon is available"
}

# Stop services
stop_services() {
    local compose_cmd
    compose_cmd=$(build_compose_command)
    
    log "Stopping all services..."
    
    if [[ ${DRY_RUN} == true ]]; then
        log "DRY RUN: Would execute: ${compose_cmd} stop"
        return 0
    fi
    
    if ${compose_cmd} stop; then
        success "Services stopped successfully"
    else
        error "Failed to stop services"
        exit 1
    fi
}

# Remove services and volumes
down_services() {
    local compose_cmd
    compose_cmd=$(build_compose_command)
    
    log "Stopping and removing all services and networks..."
    
    if [[ ${DRY_RUN} == true ]]; then
        log "DRY RUN: Would execute: ${compose_cmd} down"
        return 0
    fi
    
    if ${compose_cmd} down; then
        success "Services removed successfully"
    else
        error "Failed to remove services"
        exit 1
    fi
}

# Deploy services
deploy_services() {
    local compose_cmd
    compose_cmd=$(build_compose_command)
    
    # Add compatibility flag if requested
    if [[ ${COMPATIBILITY} == true ]]; then
        compose_cmd="${compose_cmd} --compatibility"
    fi
    
    log "Deploying monitoring stack..."
    if [[ ${BASE_ONLY} == true ]]; then
        log "Mode: Base services only"
    elif [[ ${#PROFILES[@]} -gt 0 ]]; then
        log "Mode: Base services + profiles: ${PROFILES[*]}"
    else
        log "Mode: Base services only (no profiles specified)"
    fi
    
    if [[ ${DRY_RUN} == true ]]; then
        log "DRY RUN: Would execute: ${compose_cmd} up -d"
        log "Services that would be deployed:"
        ${compose_cmd} config --services | sed 's/^/  /'
        return 0
    fi
    
    # Pull latest images unless skipped
    if [[ ${NO_PULL} == true ]]; then
        log "Skipping image pull (--no-pull set)"
    else
        log "Pulling latest images..."
        if ! ${compose_cmd} pull --quiet; then
            warning "Some images could not be pulled, continuing with local images"
        fi
    fi
    
    # Deploy services
    if ${compose_cmd} up -d; then
        success "Stack deployed successfully"
        
        # Show running services
        log "Running services:"
        ${compose_cmd} ps --format "table {{.Name}}\t{{.State}}\t{{.Ports}}" | sed '1d' | sed 's/^/  /'
        
    else
        error "Failed to deploy stack"
        exit 1
    fi
}

# Display service status
show_status() {
    local compose_cmd
    compose_cmd=$(build_compose_command)
    
    log "Current service status:"
    ${compose_cmd} ps
}

# Main execution
main() {
    log "Enhanced Monitoring Stack Deployment"
    
    # Handle stop/down operations
    if [[ ${STOP_SERVICES} == true ]]; then
        check_docker
        validate_compose_files
        stop_services
        exit 0
    fi
    
    if [[ ${DOWN_SERVICES} == true ]]; then
        check_docker  
        validate_compose_files
        down_services
        exit 0
    fi
    
    # Handle deployment
    check_docker
    validate_compose_files
    validate_configuration
    
    if [[ ${DRY_RUN} == false ]]; then
        deploy_services
        
        # Run post-deployment validation
        log "Running post-deployment validation..."
        if [[ -x "validate_stack.sh" ]]; then
            if ./validate_stack.sh --quick --skip-security; then
                success "Post-deployment validation passed"

                # Optionally skip Git backup via flag or env
                if [[ ${SKIP_BACKUP} == true || "${DEPLOY_SKIP_BACKUP:-}" == "1" ]]; then
                    warning "Skipping GitHub backup (skip flag/env set)"
                else
                    # Backup configuration to GitHub if validation passes
                    log "Backing up configuration to GitHub..."
                    if [[ -x "scripts/git_backup.sh" ]]; then
                        local commit_message="🚀 Post-deployment config sync"
                        if [[ ${#PROFILES[@]} -gt 0 ]]; then
                            commit_message="$commit_message (profiles: ${PROFILES[*]})"
                        fi

                        if ./scripts/git_backup.sh "$commit_message"; then
                            success "Configuration backed up to GitHub"
                        else
                            warning "Configuration backup failed - check logs"
                        fi
                    else
                        warning "Git backup script not found - skipping backup"
                    fi
                fi
            else
                warning "Post-deployment validation failed - skipping GitHub backup"
            fi
        else
            warning "Validation script not found - skipping validation and backup"
        fi
        
        log ""
        success "Deployment completed successfully!"
        
        if [[ ${#PROFILES[@]} -gt 0 ]]; then
            success "Active profiles: ${PROFILES[*]}"
        fi
        
        log ""
        log "Access points:"
        log "  Grafana: http://localhost:3000"
        log "  Prometheus: http://localhost:9090"
        log "  Alertmanager: http://localhost:9093"
        
        if [[ " ${PROFILES[*]} " =~ " wazuh-stack " ]]; then
            log "  Wazuh Dashboard: http://localhost:5601"
        fi
        
        if [[ " ${PROFILES[*]} " =~ " analytics-stack " ]]; then
            log "  Jaeger: http://localhost:16686"
        fi
        
        if [[ " ${PROFILES[*]} " =~ " security-stack " ]]; then
            log "  ntopng: http://localhost:3001"
        fi
    else
        success "DRY RUN completed - no services were deployed"
    fi
}

# Execute main function
main "$@"
