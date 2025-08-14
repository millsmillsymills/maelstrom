#!/bin/bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
# Enhanced Service Dependency Management Implementation

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/mills/logs/dependency-management-${TIMESTAMP}.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

success() { log "${GREEN}✅ $1${NC}"; }
warning() { log "${YELLOW}⚠️ $1${NC}"; }
error() { log "${RED}❌ $1${NC}"; }
info() { log "${BLUE}ℹ️ $1${NC}"; }

# Create Enhanced Health Check System
create_enhanced_health_checks() {
    info "Creating enhanced health check system"

    mkdir -p /home/mills/collections/health-system

    cat > /home/mills/collections/health-system/comprehensive-health-check.sh << 'EOF'
#!/bin/bash
# Comprehensive Health Check System

HEALTH_LOG="/home/mills/logs/health-$(date +%Y%m%d_%H%M%S).log"

# Service dependency map
declare -A SERVICE_DEPS=(
    ["grafana"]="influxdb prometheus"
    ["prometheus"]="node-exporter cadvisor"
    ["alertmanager"]="prometheus"
    ["mysql-exporter-stable"]="zabbix-mysql"
    ["wazuh-manager"]="wazuh-indexer"
    ["threat-intelligence"]="prometheus"
    ["security-monitor"]=""
    ["ml-analytics"]="prometheus"
)

# Health check functions for different service types
check_http_service() {
    local service="$1"
    local port="$2"
    local path="${3:-/}"

    if curl -s --max-time 5 "http://localhost:${port}${path}" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

check_docker_service() {
    local service="$1"

    if ${DOCKER} ps --format "{{.Names}}" | grep -q "^${service}$"; then
        local status=$(${DOCKER} inspect --format="{{.State.Status}}" "$service" 2>/dev/null)
        if [[ "$status" == "running" ]]; then
            return 0
        fi
    fi
    return 1
}

wait_for_dependency() {
    local service="$1"
    local timeout="${2:-60}"
    local count=0

    echo "Waiting for $service dependency..."

    while [ $count -lt $timeout ]; do
        if check_docker_service "$service"; then
            echo "✅ $service is ready"
            return 0
        fi
        sleep 2
        ((count += 2))
    done

    echo "❌ $service dependency timeout"
    return 1
}

# Main health check routine
perform_health_check() {
    local service="$1"
    local health_status="unknown"

    echo "Checking health of $service..."

    # Check if service is running
    if check_docker_service "$service"; then
        health_status="running"

        # Perform service-specific health checks
        case "$service" in
            "grafana")
                if check_http_service "$service" 3000 "/api/health"; then
                    health_status="healthy"
                else
                    health_status="unhealthy"
                fi
                ;;
            "prometheus")
                if check_http_service "$service" 9090 "/-/healthy"; then
                    health_status="healthy"
                else
                    health_status="unhealthy"
                fi
                ;;
            "influxdb")
                if check_http_service "$service" 8086 "/ping"; then
                    health_status="healthy"
                else
                    health_status="unhealthy"
                fi
                ;;
            "nginx-monitoring-gateway")
                if check_http_service "$service" 8888; then
                    health_status="healthy"
                else
                    health_status="unhealthy"
                fi
                ;;
            *)
                # Generic health check - if running, consider healthy
                health_status="healthy"
                ;;
        esac
    else
        health_status="stopped"
    fi

    echo "$service: $health_status" >> "$HEALTH_LOG"
    echo "$health_status"
}

# Check all dependencies for a service
check_service_dependencies() {
    local service="$1"
    local deps="${SERVICE_DEPS[$service]}"

    if [[ -n "$deps" ]]; then
        echo "Checking dependencies for $service: $deps"

        for dep in $deps; do
            if ! wait_for_dependency "$dep" 30; then
                echo "❌ Dependency $dep not available for $service"
                return 1
            fi
        done

        echo "✅ All dependencies ready for $service"
    fi

    return 0
}

# Restart service with dependency checks
restart_service_with_deps() {
    local service="$1"

    echo "Restarting $service with dependency checks..."

    # Stop the service
    ${DOCKER} stop "$service" 2>/dev/null || true

    # Wait for dependencies
    check_service_dependencies "$service"

    # Start the service
    ${DOCKER} start "$service" 2>/dev/null || true

    # Wait and verify
    sleep 10
    local health=$(perform_health_check "$service")

    if [[ "$health" == "healthy" || "$health" == "running" ]]; then
        echo "✅ $service restarted successfully"
        return 0
    else
        echo "❌ $service restart failed"
        return 1
    fi
}

# Main execution
case "${1:-check}" in
    "check")
        echo "=== Comprehensive Health Check $(date) ===" >> "$HEALTH_LOG"

        services=("influxdb" "prometheus" "grafana" "nginx-monitoring-gateway" "mysql-exporter-stable" "threat-intelligence" "security-monitor" "wazuh-manager")

        for service in "${services[@]}"; do
            health=$(perform_health_check "$service")
            echo "$service: $health"
        done
        ;;
    "restart")
        if [[ -n "$2" ]]; then
            restart_service_with_deps "$2"
        else
            echo "Usage: $0 restart <service_name>"
        fi
        ;;
    "deps")
        if [[ -n "$2" ]]; then
            check_service_dependencies "$2"
        else
            echo "Usage: $0 deps <service_name>"
        fi
        ;;
    *)
        echo "Usage: $0 {check|restart <service>|deps <service>}"
        ;;
esac
EOF

    chmod +x /home/mills/collections/health-system/comprehensive-health-check.sh
    success "Enhanced health check system created"
}

# Create Service Startup Orchestrator
create_startup_orchestrator() {
    info "Creating service startup orchestrator"

    cat > /home/mills/collections/health-system/service-orchestrator.sh << 'EOF'
#!/bin/bash
# Service Startup Orchestrator with Dependency Management

ORCHESTRATOR_LOG="/home/mills/logs/orchestrator-$(date +%Y%m%d_%H%M%S).log"

# Service startup order (dependency-aware)
STARTUP_ORDER=(
    # Core infrastructure first
    "redis-cache-enhanced"
    "3689204dd82a_influxdb"

    # Monitoring core
    "prometheus"
    "grafana"
    "alertmanager"
    "nginx-monitoring-gateway"

    # Exporters and collectors
    "node-exporter"
    "cadvisor"
    "telegraf"
    "mysql-exporter-stable"

    # Security services
    "wazuh-manager"
    "security-monitor"

    # Analytics and intelligence
    "threat-intelligence"
    "ml-analytics"

    # Health monitoring
    "health-monitor-enhanced"
)

log_orchestrator() {
    echo "$(date): $1" | tee -a "$ORCHESTRATOR_LOG"
}

start_service_with_wait() {
    local service="$1"
    local wait_time="${2:-30}"

    log_orchestrator "Starting $service..."

    # Check if service exists
    if ! ${DOCKER} ps -a --format "{{.Names}}" | grep -q "^${service}$"; then
        log_orchestrator "Service $service not found, skipping"
        return 0
    fi

    # Start the service
    ${DOCKER} start "$service" 2>/dev/null || {
        log_orchestrator "Failed to start $service"
        return 1
    }

    # Wait for service to be ready
    local count=0
    while [ $count -lt $wait_time ]; do
        local status=$(${DOCKER} inspect --format="{{.State.Status}}" "$service" 2>/dev/null)

        if [[ "$status" == "running" ]]; then
            log_orchestrator "✅ $service is running"

            # Additional health check for critical services
            case "$service" in
                "grafana")
                    sleep 10  # Allow Grafana to initialize
                    ;;
                "prometheus")
                    sleep 5   # Allow Prometheus to start
                    ;;
                "influxdb")
                    sleep 5   # Allow InfluxDB to initialize
                    ;;
            esac

            return 0
        fi

        sleep 2
        ((count += 2))
    done

    log_orchestrator "❌ $service startup timeout"
    return 1
}

# Orchestrated startup
orchestrated_startup() {
    log_orchestrator "=== Starting Orchestrated Service Startup ==="

    local failed_services=()
    local started_services=()

    for service in "${STARTUP_ORDER[@]}"; do
        if start_service_with_wait "$service" 45; then
            started_services+=("$service")
        else
            failed_services+=("$service")
        fi

        # Small delay between service starts
        sleep 3
    done

    log_orchestrator "=== Startup Summary ==="
    log_orchestrator "Started: ${#started_services[@]} services"
    log_orchestrator "Failed: ${#failed_services[@]} services"

    if [ ${#failed_services[@]} -gt 0 ]; then
        log_orchestrator "Failed services: ${failed_services[*]}"
    fi

    log_orchestrator "=== Orchestrated Startup Complete ==="
}

# Graceful shutdown
orchestrated_shutdown() {
    log_orchestrator "=== Starting Orchestrated Shutdown ==="

    # Reverse order for shutdown
    local shutdown_order=($(printf '%s\n' "${STARTUP_ORDER[@]}" | tac))

    for service in "${shutdown_order[@]}"; do
        if ${DOCKER} ps --format "{{.Names}}" | grep -q "^${service}$"; then
            log_orchestrator "Stopping $service..."
            ${DOCKER} stop "$service" --time 30 2>/dev/null || true
            sleep 2
        fi
    done

    log_orchestrator "=== Orchestrated Shutdown Complete ==="
}

# Main execution
case "${1:-startup}" in
    "startup")
        orchestrated_startup
        ;;
    "shutdown")
        orchestrated_shutdown
        ;;
    *)
        echo "Usage: $0 {startup|shutdown}"
        ;;
esac
EOF

    chmod +x /home/mills/collections/health-system/service-orchestrator.sh
    success "Service startup orchestrator created"
}

# Create Dependency Health Monitor
create_dependency_monitor() {
    info "Creating dependency health monitor"

    cat > /home/mills/collections/health-system/dependency-monitor.py << 'EOF'
#!/usr/bin/env python3
import time
import ${DOCKER} import logging
import json
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DependencyHealthMonitor:
    def __init__(self):
        try:
            self.docker_client = docker.from_env()
        except:
            self.docker_client = None
            logger.error("Docker client not available")

        # Define service dependencies
        self.dependencies = {
            'grafana': ['influxdb', 'prometheus'],
            'prometheus': ['node-exporter', 'cadvisor'],
            'alertmanager': ['prometheus'],
            'mysql-exporter-stable': ['zabbix-mysql'],
            'wazuh-manager': ['wazuh-indexer'],
            'threat-intelligence': ['prometheus'],
            'ml-analytics': ['prometheus'],
            'nginx-monitoring-gateway': ['grafana', 'prometheus']
        }

        self.health_history = defaultdict(list)

    def check_container_health(self, container_name):
        """Check if a container is healthy"""
        try:
            if not self.docker_client:
                return False

            containers = self.docker_client.containers.list(all=True)
            container = next((c for c in containers if container_name in c.name), None)

            if not container:
                return False

            if container.status != 'running':
                return False

            # Additional health checks for specific services
            if container_name == 'grafana':
                # Check if Grafana API is responding
                try:
                    import requests
                    response = requests.get('http://localhost:3000/api/health', timeout=5)
                    return response.status_code == 200
                except:
                    return False

            elif container_name == 'prometheus':
                try:
                    import requests
                    response = requests.get('http://localhost:9090/-/healthy', timeout=5)
                    return response.status_code == 200
                except:
                    return False

            elif container_name == 'influxdb':
                try:
                    import requests
                    response = requests.get('http://localhost:8086/ping', timeout=5)
                    return response.status_code == 200
                except:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking {container_name}: {e}")
            return False

    def check_service_dependencies(self, service_name):
        """Check if all dependencies of a service are healthy"""
        if service_name not in self.dependencies:
            return True, []

        failed_deps = []
        for dep in self.dependencies[service_name]:
            if not self.check_container_health(dep):
                failed_deps.append(dep)

        return len(failed_deps) == 0, failed_deps

    def restart_service_if_deps_healthy(self, service_name):
        """Restart a service if its dependencies are healthy"""
        try:
            deps_healthy, failed_deps = self.check_service_dependencies(service_name)

            if deps_healthy:
                logger.info(f"Dependencies healthy for {service_name}, attempting restart")

                if self.docker_client:
                    containers = self.docker_client.containers.list(all=True)
                    container = next((c for c in containers if service_name in c.name), None)

                    if container:
                        container.restart()
                        logger.info(f"Restarted {service_name}")
                        return True
            else:
                logger.warning(f"Dependencies unhealthy for {service_name}: {failed_deps}")

            return False

        except Exception as e:
            logger.error(f"Error restarting {service_name}: {e}")
            return False

    def generate_health_report(self):
        """Generate comprehensive health report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'services': {},
            'dependency_issues': [],
            'recommendations': []
        }

        all_services = set()
        for service, deps in self.dependencies.items():
            all_services.add(service)
            all_services.update(deps)

        for service in all_services:
            health = self.check_container_health(service)
            report['services'][service] = {
                'healthy': health,
                'status': 'healthy' if health else 'unhealthy'
            }

            # Track health history
            self.health_history[service].append({
                'timestamp': datetime.now().isoformat(),
                'healthy': health
            })

            # Keep only last 100 entries
            if len(self.health_history[service]) > 100:
                self.health_history[service] = self.health_history[service][-100:]

        # Check dependency issues
        for service, deps in self.dependencies.items():
            service_healthy = report['services'].get(service, {}).get('healthy', False)
            deps_healthy, failed_deps = self.check_service_dependencies(service)

            if not service_healthy and deps_healthy:
                report['dependency_issues'].append({
                    'service': service,
                    'issue': 'service_unhealthy_but_deps_healthy',
                    'recommendation': f'Restart {service} as dependencies are available'
                })
                report['recommendations'].append(f'Restart {service}')

            elif not service_healthy and not deps_healthy:
                report['dependency_issues'].append({
                    'service': service,
                    'issue': 'dependencies_unhealthy',
                    'failed_dependencies': failed_deps,
                    'recommendation': f'Fix dependencies {failed_deps} before restarting {service}'
                })

        return report

    def run_monitoring_cycle(self):
        """Run one monitoring cycle"""
        try:
            logger.info("Starting dependency health monitoring cycle")

            report = self.generate_health_report()

            # Log summary
            healthy_count = sum(1 for s in report['services'].values() if s['healthy'])
            total_count = len(report['services'])

            logger.info(f"Health status: {healthy_count}/{total_count} services healthy")

            # Take action on dependency issues
            for issue in report['dependency_issues']:
                if issue['issue'] == 'service_unhealthy_but_deps_healthy':
                    service = issue['service']
                    logger.info(f"Attempting to restart {service} (dependencies healthy)")
                    self.restart_service_if_deps_healthy(service)

            # Save report
            report_file = f"/tmp/dependency_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)

            return report

        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")
            return None

    def run_continuous_monitoring(self):
        """Run continuous dependency monitoring"""
        logger.info("Starting Dependency Health Monitor")

        while True:
            try:
                self.run_monitoring_cycle()

                # Sleep for 5 minutes between cycles
                time.sleep(300)

            except KeyboardInterrupt:
                logger.info("Dependency monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)

def main():
    monitor = DependencyHealthMonitor()
    monitor.run_continuous_monitoring()

if __name__ == "__main__":
    main()
EOF

    success "Dependency health monitor created"
}

# Create Service Recovery Procedures
create_recovery_procedures() {
    info "Creating service recovery procedures"

    cat > /home/mills/collections/health-system/service-recovery.sh << 'EOF'
#!/bin/bash
# Service Recovery Procedures

RECOVERY_LOG="/home/mills/logs/service-recovery-$(date +%Y%m%d_%H%M%S).log"

log_recovery() {
    echo "$(date): $1" | tee -a "$RECOVERY_LOG"
}

# Service-specific recovery procedures
recover_grafana() {
    log_recovery "Recovering Grafana service"

    # Reset admin password
    ${DOCKER} exec grafana bash -c "grafana-cli admin reset-admin-password admin123" 2>/dev/null || true

    # Check database connectivity
    ${DOCKER} exec grafana bash -c "grafana-cli admin data-migration run" 2>/dev/null || true

    # Restart with clean state
    ${DOCKER} restart grafana
    sleep 30

    # Verify recovery
    if curl -s http://localhost:3000/api/health | grep -q "ok"; then
        log_recovery "✅ Grafana recovery successful"
        return 0
    else
        log_recovery "❌ Grafana recovery failed"
        return 1
    fi
}

recover_prometheus() {
    log_recovery "Recovering Prometheus service"

    # Check configuration
    ${DOCKER} exec prometheus promtool check config /etc/prometheus/prometheus.yml || {
        log_recovery "❌ Prometheus configuration invalid"
        return 1
    }

    # Restart service
    ${DOCKER} restart prometheus
    sleep 20

    # Verify recovery
    if curl -s http://localhost:9090/-/healthy >/dev/null; then
        log_recovery "✅ Prometheus recovery successful"
        return 0
    else
        log_recovery "❌ Prometheus recovery failed"
        return 1
    fi
}

recover_mysql_exporter() {
    log_recovery "Recovering MySQL Exporter service"

    # Stop existing instances
    ${DOCKER} stop mysql-exporter-stable mysql-exporter-production 2>/dev/null || true
    ${DOCKER} rm mysql-exporter-stable mysql-exporter-production 2>/dev/null || true

    # Deploy minimal stable version
    ${DOCKER} run -d \
        --name mysql-exporter-recovery \
        --network mills_monitoring \
        --restart unless-stopped \
        --security-opt no-new-privileges:true \
        --memory 32m \
        --cpus 0.1 \
        -e DATA_SOURCE_NAME="root:zabbix_password@tcp(zabbix-mysql:3306)/" \
        prom/mysqld-exporter:latest \
        --collect.global_status

    sleep 10
    if ${DOCKER} ps | grep -q mysql-exporter-recovery; then
        log_recovery "✅ MySQL Exporter recovery successful"
        return 0
    else
        log_recovery "❌ MySQL Exporter recovery failed"
        return 1
    fi
}

recover_service() {
    local service="$1"

    log_recovery "Attempting recovery for $service"

    case "$service" in
        "grafana")
            recover_grafana
            ;;
        "prometheus")
            recover_prometheus
            ;;
        "mysql-exporter-stable"|"mysql-exporter-production")
            recover_mysql_exporter
            ;;
        *)
            # Generic recovery
            log_recovery "Generic recovery for $service"
            ${DOCKER} restart "$service"
            sleep 15

            if ${DOCKER} ps | grep -q "$service"; then
                log_recovery "✅ Generic recovery successful for $service"
                return 0
            else
                log_recovery "❌ Generic recovery failed for $service"
                return 1
            fi
            ;;
    esac
}

# Auto-recovery based on health status
auto_recovery() {
    log_recovery "=== Starting Auto-Recovery Process ==="

    # Services that need recovery
    services_to_check=("grafana" "prometheus" "mysql-exporter-stable" "threat-intelligence" "security-monitor" "ml-analytics")

    for service in "${services_to_check[@]}"; do
        # Check if service is unhealthy
        if ! ${DOCKER} ps --format "{{.Names}}" | grep -q "^${service}$" || \
           ${DOCKER} ps --format "{{.Names}}\t{{.Status}}" | grep "$service" | grep -q "Restarting"; then

            log_recovery "Service $service needs recovery"
            recover_service "$service"
        else
            log_recovery "Service $service is healthy"
        fi
    done

    log_recovery "=== Auto-Recovery Process Complete ==="
}

# Main execution
case "${1:-auto}" in
    "auto")
        auto_recovery
        ;;
    "service")
        if [[ -n "$2" ]]; then
            recover_service "$2"
        else
            echo "Usage: $0 service <service_name>"
        fi
        ;;
    *)
        echo "Usage: $0 {auto|service <name>}"
        ;;
esac
EOF

    chmod +x /home/mills/collections/health-system/service-recovery.sh
    success "Service recovery procedures created"
}

# Schedule Automated Dependency Management
schedule_dependency_automation() {
    info "Scheduling automated dependency management"

    # Add comprehensive health monitoring to crontab
    (crontab -l 2>/dev/null | grep -v "health-system"; cat << 'EOF'
# Enhanced Health and Dependency Management
*/5 * * * * /home/mills/collections/health-system/comprehensive-health-check.sh check >> /home/mills/logs/health-checks.log 2>&1
*/15 * * * * /home/mills/collections/health-system/service-recovery.sh auto >> /home/mills/logs/auto-recovery.log 2>&1
0 2 * * * /home/mills/collections/health-system/service-orchestrator.sh startup >> /home/mills/logs/orchestrator.log 2>&1
EOF
) | crontab -

    success "Dependency management automation scheduled"
}

# Main execution
main() {
    log "🚀 Starting Enhanced Service Dependency Management Implementation"

    # Create all dependency management components
    create_enhanced_health_checks
    create_startup_orchestrator
    create_dependency_monitor
    create_recovery_procedures
    schedule_dependency_automation

    # Test the health check system
    info "Testing health check system"
    /home/mills/collections/health-system/comprehensive-health-check.sh check

    log "🎉 Enhanced Service Dependency Management completed!"
    success "All dependency management components implemented and scheduled"
    info "Log file: $LOG_FILE"
}

# Execute main function
main "$@"
