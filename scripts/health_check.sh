#!/bin/bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh

# Comprehensive Health Check and Self-Healing Script
# Monitors all critical services and attempts automatic recovery

LOG_FILE="/home/mills/health_check.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

check_service() {
    local service_name="$1"
    local check_command="$2"
    local recovery_command="$3"
    
    log "Checking $service_name..."
    
    if eval "$check_command" >/dev/null 2>&1; then
        log "✅ $service_name is healthy"
        return 0
    else
        log "❌ $service_name is unhealthy, attempting recovery..."
        eval "$recovery_command"
        sleep 5
        
        if eval "$check_command" >/dev/null 2>&1; then
            log "✅ $service_name recovered successfully"
            # Send success notification
            curl -X POST http://localhost:5001/webhook -H "Content-Type: application/json" \
                -d "{\"alerts\":[{\"status\":\"resolved\",\"labels\":{\"alertname\":\"ServiceRecovered\",\"service\":\"$service_name\"},\"annotations\":{\"summary\":\"$service_name was automatically recovered\"}}]}" 2>/dev/null
            return 0
        else
            log "🔥 $service_name recovery failed"
            # Send critical alert
            curl -X POST http://localhost:5001/webhook -H "Content-Type: application/json" \
                -d "{\"alerts\":[{\"status\":\"firing\",\"labels\":{\"alertname\":\"ServiceFailure\",\"severity\":\"critical\",\"service\":\"$service_name\"},\"annotations\":{\"summary\":\"$service_name failed and could not be automatically recovered\"}}]}" 2>/dev/null
            return 1
        fi
    fi
}

# Health Check Definitions
check_service "Grafana" "curl -s http://localhost:3000/api/health" "${DOCKER} restart grafana"
check_service "Prometheus" "curl -s http://localhost:9090/-/healthy" "${DOCKER} restart prometheus"
check_service "InfluxDB" "curl -s http://localhost:8086/ping" "${DOCKER} restart influxdb"
check_service "Alertmanager" "curl -s http://localhost:9093/api/v2/status" "${DOCKER} restart alertmanager"
check_service "Node Exporter" "curl -s http://localhost:9100/metrics | head -1" "${DOCKER} restart node-exporter"
check_service "cAdvisor" "curl -s http://localhost:8081/metrics | head -1" "${DOCKER} restart cadvisor"
check_service "UniFi Poller" "curl -s http://localhost:9130/metrics | head -1" "${DOCKER} restart unpoller-prometheus"
check_service "Slack Notifier" "curl -s http://localhost:5001/health" "${DOCKER} restart slack-notifier"

# Check Prometheus targets
unhealthy_targets=$(curl -s "http://localhost:9090/api/v1/targets" 2>/dev/null | grep -o '"health":"down"' | wc -l)
if [ "$unhealthy_targets" -gt 0 ]; then
    log "⚠️ Found $unhealthy_targets unhealthy Prometheus targets"
    # Restart prometheus to refresh targets
    ${DOCKER} restart prometheus
fi

# Check container restart loops
restart_count=$(${DOCKER} ps --format "{{.Names}}\t{{.Status}}" | grep -c "Restart")
if [ "$restart_count" -gt 2 ]; then
    log "⚠️ Found $restart_count containers in restart loops"
fi

# Disk space check
disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$disk_usage" -gt 85 ]; then
    log "⚠️ Disk usage is ${disk_usage}% - cleaning up..."
    ${DOCKER} system prune -f
fi

# Memory check
memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ "$memory_usage" -gt 90 ]; then
    log "⚠️ Memory usage is ${memory_usage}% - restarting high-memory containers"
    ${DOCKER} restart telegraf ml-analytics-fixed
fi

log "Health check completed"