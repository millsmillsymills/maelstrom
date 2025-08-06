#!/bin/bash
# Comprehensive monitoring stack validation script
# Tests health-checks, CVE scanning, and backup/restore functionality

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
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
VALIDATION_LOG="/tmp/stack_validation_${TIMESTAMP}.log"

# Validation results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "${VALIDATION_LOG}"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "${VALIDATION_LOG}"
    ((PASSED_TESTS++))
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "${VALIDATION_LOG}"
    ((WARNINGS++))
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "${VALIDATION_LOG}"
    ((FAILED_TESTS++))
}

test_start() {
    ((TOTAL_TESTS++))
    log "Test $TOTAL_TESTS: $1"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Comprehensive validation of the monitoring stack infrastructure.

OPTIONS:
    -h, --help              Show this help message
    --health-checks-only   Run only health check tests
    --security-only        Run only security/CVE scanning tests  
    --backups-only         Run only backup/restore tests
    --skip-health          Skip health check tests
    --skip-security        Skip security/CVE scanning tests
    --skip-backups         Skip backup/restore tests
    --quick                Run quick validation (reduced test coverage)
    --fix-issues          Attempt to fix discovered issues
    
VALIDATION CATEGORIES:
    1. Health Checks       - Test all service health endpoints and container status
    2. Security Scanning   - Run CVE scans on all container images
    3. Backup/Restore      - Test backup creation and integrity verification

EXAMPLES:
    $0                     # Run all validation tests
    $0 --health-checks-only # Only test service health
    $0 --quick             # Quick validation with reduced coverage
    $0 --fix-issues        # Run validation and attempt to fix issues

EOF
}

# Parse command line arguments
HEALTH_CHECKS_ONLY=false
SECURITY_ONLY=false
BACKUPS_ONLY=false
SKIP_HEALTH=false
SKIP_SECURITY=false
SKIP_BACKUPS=false
QUICK_MODE=false
FIX_ISSUES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        --health-checks-only)
            HEALTH_CHECKS_ONLY=true
            shift
            ;;
        --security-only)
            SECURITY_ONLY=true
            shift
            ;;
        --backups-only)
            BACKUPS_ONLY=true
            shift
            ;;
        --skip-health)
            SKIP_HEALTH=true
            shift
            ;;
        --skip-security)
            SKIP_SECURITY=true
            shift
            ;;
        --skip-backups)
            SKIP_BACKUPS=true
            shift
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --fix-issues)
            FIX_ISSUES=true
            shift
            ;;
        -*)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            error "Unexpected argument: $1"
            usage
            exit 1
            ;;
    esac
done

# Determine what to run based on options
if [[ ${HEALTH_CHECKS_ONLY} == true ]]; then
    SKIP_SECURITY=true
    SKIP_BACKUPS=true
elif [[ ${SECURITY_ONLY} == true ]]; then
    SKIP_HEALTH=true
    SKIP_BACKUPS=true
elif [[ ${BACKUPS_ONLY} == true ]]; then
    SKIP_HEALTH=true
    SKIP_SECURITY=true
fi

# Get active Docker Compose command
get_compose_command() {
    # Determine which compose files and profiles are active
    local cmd="docker-compose -f ${BASE_COMPOSE_FILE}"
    
    # Check if any profiles are running
    local running_services
    running_services=$(docker ps --format "{{.Names}}" 2>/dev/null || echo "")
    
    # Check if production services are running  
    if echo "${running_services}" | grep -qE "(wazuh|suricata|zeek|ml-analytics|jaeger)"; then
        cmd="${cmd} -f ${PROD_COMPOSE_FILE}"
        
        # Detect active profiles
        if echo "${running_services}" | grep -q "ml-analytics"; then
            cmd="${cmd} --profile ml-analytics"
        fi
        if echo "${running_services}" | grep -qE "(wazuh|elasticsearch)"; then
            cmd="${cmd} --profile wazuh-stack"
        fi
        if echo "${running_services}" | grep -qE "(suricata|zeek|ntopng)"; then
            cmd="${cmd} --profile security-stack"
        fi
        if echo "${running_services}" | grep -qE "(jaeger|self-healing)"; then
            cmd="${cmd} --profile analytics-stack"
        fi
    fi
    
    echo "${cmd}"
}

# Check prerequisites
check_prerequisites() {
    test_start "Prerequisites validation"
    
    local prereq_failed=false
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not available"
        prereq_failed=true
    else
        if ! docker info &> /dev/null; then
            error "Docker daemon is not running"
            prereq_failed=true
        fi
    fi
    
    # Check required scripts exist (only if tests will use them)
    local scripts=()
    
    if [[ ${SKIP_SECURITY} == false ]]; then
        scripts+=("/home/mills/scripts/scan_images.sh")
    fi
    
    if [[ ${SKIP_BACKUPS} == false ]]; then
        scripts+=(
            "/home/mills/scripts/backups/backup_influxdb.sh"
            "/home/mills/scripts/backups/backup_volume.sh"
        )
    fi
    
    for script in "${scripts[@]}"; do
        if [[ ! -f "${script}" ]]; then
            error "Required script not found: ${script}"
            prereq_failed=true
        elif [[ ! -x "${script}" ]]; then
            error "Script not executable: ${script}"
            prereq_failed=true
        fi
    done
    
    if [[ ${prereq_failed} == true ]]; then
        error "Prerequisites validation failed"
        return 1
    else
        success "Prerequisites validation passed"
        return 0
    fi
}

# Test container health checks
test_health_checks() {
    if [[ ${SKIP_HEALTH} == true ]]; then
        return 0
    fi
    
    log "=== HEALTH CHECKS VALIDATION ==="
    
    test_start "Container status verification"
    
    local compose_cmd
    compose_cmd=$(get_compose_command)
    
    # Get running services
    local running_services
    if ! running_services=$(${compose_cmd} ps --services --filter "status=running" 2>/dev/null); then
        error "Failed to get running services"
        return 1
    fi
    
    if [[ -z "${running_services}" ]]; then
        error "No services are currently running"
        return 1
    fi
    
    success "Found $(echo "${running_services}" | wc -l) running services"
    
    # Test individual service health
    test_start "Individual service health checks"
    
    local unhealthy_services=0
    
    while IFS= read -r service; do
        if [[ -z "${service}" ]]; then
            continue
        fi
        
        log "Testing health: ${service}"
        
        # Get container name
        local container_name
        container_name=$(${compose_cmd} ps -q "${service}" 2>/dev/null || echo "")
        
        if [[ -z "${container_name}" ]]; then
            warning "Service ${service} has no running container"
            continue
        fi
        
        # Check container health status
        local health_status
        health_status=$(docker inspect "${container_name}" --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
        
        case "${health_status}" in
            "healthy")
                success "Service ${service}: healthy"
                ;;
            "unhealthy")
                error "Service ${service}: unhealthy"
                ((unhealthy_services++))
                
                if [[ ${FIX_ISSUES} == true ]]; then
                    log "Attempting to restart unhealthy service: ${service}"
                    ${compose_cmd} restart "${service}"
                fi
                ;;
            "starting")
                warning "Service ${service}: still starting"
                ;;
            "none")
                log "Service ${service}: no health check defined"
                ;;
            *)
                warning "Service ${service}: unknown health status: ${health_status}"
                ;;
        esac
        
        if [[ ${QUICK_MODE} == false ]]; then
            sleep 1  # Brief delay between health checks
        fi
        
    done <<< "${running_services}"
    
    if [[ ${unhealthy_services} -eq 0 ]]; then
        success "All services with health checks are healthy"
    else
        error "${unhealthy_services} services are unhealthy"
    fi
    
    # Test specific endpoints
    test_start "Critical endpoint connectivity"
    
    local endpoints=(
        "http://localhost:3000/api/health:Grafana"
        "http://localhost:9090/-/ready:Prometheus"
        "http://localhost:9093/-/ready:Alertmanager"
        "http://localhost:8086/ping:InfluxDB"
    )
    
    for endpoint_info in "${endpoints[@]}"; do
        local endpoint="${endpoint_info%:*}"
        local service="${endpoint_info#*:}"
        
        log "Testing endpoint: ${endpoint} (${service})"
        
        if curl -f -s --max-time 10 "${endpoint}" > /dev/null 2>&1; then
            success "Endpoint ${service}: accessible"
        else
            error "Endpoint ${service}: not accessible"
            
            if [[ ${FIX_ISSUES} == true ]]; then
                log "Attempting to restart service for endpoint: ${service}"
                local service_name=$(echo "${service}" | tr '[:upper:]' '[:lower:]')
                ${compose_cmd} restart "${service_name}" || warning "Failed to restart ${service_name}"
            fi
        fi
    done
}

# Test security/CVE scanning
test_security_scanning() {
    if [[ ${SKIP_SECURITY} == true ]]; then
        return 0
    fi
    
    log "=== SECURITY SCANNING VALIDATION ==="
    
    test_start "CVE scanning execution"
    
    local scan_script="/home/mills/scripts/scan_images.sh"
    
    log "Running container image vulnerability scan..."
    
    local scan_result=0
    if [[ ${QUICK_MODE} == true ]]; then
        # Quick mode: scan only critical severity
        timeout 300 "${scan_script}" --severity HIGH,CRITICAL || scan_result=$?
    else
        # Full scan
        timeout 600 "${scan_script}" || scan_result=$?
    fi
    
    case ${scan_result} in
        0)
            success "Security scan passed - no critical vulnerabilities found"
            ;;
        1)
            warning "Security scan found vulnerabilities - check scan report"
            ;;
        124)
            error "Security scan timed out"
            ;;
        *)
            error "Security scan failed with exit code: ${scan_result}"
            ;;
    esac
    
    # Check for security monitoring services
    test_start "Security monitoring services status"
    
    local security_services=("security-monitor")
    local wazuh_services=("wazuh-manager" "wazuh-dashboard" "wazuh-elasticsearch")
    local network_security=("suricata" "zeek" "ntopng")
    
    # Check if security services are running
    local running_containers
    running_containers=$(docker ps --format "{{.Names}}" 2>/dev/null || echo "")
    
    for service in "${security_services[@]}"; do
        if echo "${running_containers}" | grep -q "^${service}$"; then
            success "Security service running: ${service}"
        else
            log "Security service not active: ${service}"
        fi
    done
    
    # Check Wazuh stack if running
    local wazuh_active=false
    for service in "${wazuh_services[@]}"; do
        if echo "${running_containers}" | grep -q "^${service}$"; then
            wazuh_active=true
            success "Wazuh service running: ${service}"
        fi
    done
    
    if [[ ${wazuh_active} == true ]]; then
        # Test Wazuh API if available
        if curl -f -s --max-time 10 "http://localhost:55000" > /dev/null 2>&1; then
            success "Wazuh API accessible"
        else
            warning "Wazuh API not accessible"
        fi
    fi
    
    # Check network security services
    for service in "${network_security[@]}"; do
        if echo "${running_containers}" | grep -q "^${service}$"; then
            success "Network security service running: ${service}"
        else
            log "Network security service not active: ${service}"
        fi
    done
}

# Test backup and restore functionality
test_backup_restore() {
    if [[ ${SKIP_BACKUPS} == true ]]; then
        return 0
    fi
    
    log "=== BACKUP/RESTORE VALIDATION ==="
    
    test_start "Backup script availability"
    
    local backup_scripts=(
        "/home/mills/scripts/backups/backup_influxdb.sh"
        "/home/mills/scripts/backups/backup_volume.sh"
        "/home/mills/scripts/backups/rotate_backups.sh"
    )
    
    for script in "${backup_scripts[@]}"; do
        if [[ -x "${script}" ]]; then
            success "Backup script available: $(basename "${script}")"
        else
            error "Backup script missing or not executable: ${script}"
        fi
    done
    
    # Test backup directory
    test_start "Backup directory validation"
    
    local backup_dir="${BACKUP_BASE_DIR:-/home/mills/backups}"
    
    if [[ -d "${backup_dir}" ]]; then
        if [[ -w "${backup_dir}" ]]; then
            success "Backup directory accessible: ${backup_dir}"
        else
            error "Backup directory not writable: ${backup_dir}"
        fi
    else
        warning "Backup directory does not exist: ${backup_dir}"
        
        if [[ ${FIX_ISSUES} == true ]]; then
            log "Creating backup directory: ${backup_dir}"
            mkdir -p "${backup_dir}" && success "Backup directory created"
        fi
    fi
    
    # Test InfluxDB backup functionality
    test_start "InfluxDB backup test"
    
    if docker ps | grep -q "influxdb"; then
        log "Testing InfluxDB backup creation..."
        
        local backup_script="/home/mills/scripts/backups/backup_influxdb.sh"
        local test_backup_dir="/tmp/influxdb_backup_test_${TIMESTAMP}"
        
        mkdir -p "${test_backup_dir}"
        
        if timeout 120 "${backup_script}" --dry-run --dest "${test_backup_dir}"; then
            success "InfluxDB backup test passed (dry-run)"
        else
            error "InfluxDB backup test failed"
        fi
        
        rm -rf "${test_backup_dir}"
    else
        warning "InfluxDB not running - skipping backup test"
    fi
    
    # Test volume backup functionality
    test_start "Volume backup test"
    
    local test_volumes=("prometheus_data" "grafana_data")
    local backup_script="/home/mills/scripts/backups/backup_volume.sh"
    
    for volume in "${test_volumes[@]}"; do
        if docker volume ls | grep -q "^local.*${volume}$"; then
            log "Testing backup for volume: ${volume}"
            
            if timeout 60 "${backup_script}" --dry-run "${volume}"; then
                success "Volume backup test passed: ${volume}"
            else
                error "Volume backup test failed: ${volume}"
            fi
        else
            log "Volume not found, skipping test: ${volume}"
        fi
        
        if [[ ${QUICK_MODE} == true ]]; then
            break  # Only test first volume in quick mode
        fi
    done
    
    # Test backup rotation
    test_start "Backup rotation test"
    
    local rotation_script="/home/mills/scripts/backups/rotate_backups.sh"
    
    if timeout 30 "${rotation_script}" --dry-run --backup-dir "${backup_dir}" 2>/dev/null; then
        success "Backup rotation test passed"
    else
        error "Backup rotation test failed"
    fi
}

# Generate validation report
generate_report() {
    log ""
    log "=== VALIDATION SUMMARY ==="
    log "Total tests: ${TOTAL_TESTS}"
    log "Passed: ${PASSED_TESTS}"
    log "Failed: ${FAILED_TESTS}"
    log "Warnings: ${WARNINGS}"
    log ""
    
    local success_rate=0
    if [[ ${TOTAL_TESTS} -gt 0 ]]; then
        success_rate=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
    fi
    
    log "Success rate: ${success_rate}%"
    log "Validation log: ${VALIDATION_LOG}"
    
    if [[ ${FAILED_TESTS} -eq 0 ]]; then
        success "All validation tests passed!"
        return 0
    else
        error "Validation completed with ${FAILED_TESTS} failures"
        return 1
    fi
}

# Main execution
main() {
    log "Comprehensive Stack Validation"
    log "Timestamp: $(date)"
    log "Log file: ${VALIDATION_LOG}"
    log ""
    
    # Initialize validation log
    echo "Stack Validation Report - $(date)" > "${VALIDATION_LOG}"
    echo "================================================" >> "${VALIDATION_LOG}"
    echo "" >> "${VALIDATION_LOG}"
    
    # Run prerequisite checks
    if ! check_prerequisites; then
        error "Prerequisites check failed - aborting validation"
        exit 1
    fi
    
    # Run validation categories
    test_health_checks
    test_security_scanning  
    test_backup_restore
    
    # Generate final report
    local validation_success=false
    if generate_report; then
        validation_success=true
    fi
    
    # Update README status if validation passes
    if [[ ${validation_success} == true ]]; then
        log "Updating README status..."
        if [[ -x "scripts/update_readme_status.py" ]]; then
            if python3 scripts/update_readme_status.py; then
                success "README status updated successfully"
            else
                warning "Failed to update README status"
            fi
        else
            warning "README status update script not found"
        fi
    fi
    
    if [[ ${validation_success} == true ]]; then
        exit 0
    else
        exit 1
    fi
}

# Cleanup function
cleanup() {
    log "Cleaning up temporary files..."
}

trap cleanup EXIT

# Execute main function
main "$@"