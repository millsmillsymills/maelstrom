#!/bin/bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
# Comprehensive Deployment Validation Script
# End-to-end validation of all monitoring stack enhancements

set -e

# Configuration
VALIDATION_LOG="/var/log/comprehensive-validation.log"
VALIDATION_REPORT="/home/mills/comprehensive-validation-report-$(date +%Y%m%d_%H%M%S).md"
RESULTS_DIR="/home/mills/validation-results"
TEST_TIMEOUT=300  # 5 minutes timeout for tests

# Test tracking
declare -A TEST_RESULTS=()
declare -A TEST_DETAILS=()
CRITICAL_FAILURES=0
WARNING_COUNT=0
TOTAL_TESTS=0

# Service health endpoints
declare -A SERVICE_ENDPOINTS=(
    ["grafana"]="http://localhost:3000/api/health"
    ["prometheus"]="http://localhost:9090/-/healthy"
    ["influxdb"]="http://localhost:8086/ping"
    ["alertmanager"]="http://localhost:9093/-/healthy"
    ["loki"]="http://localhost:3100/ready"
    ["wazuh-dashboard"]="http://localhost:5601/api/status"
    ["jaeger"]="http://localhost:16686/"
    ["ntopng"]="http://localhost:3001/"
    ["zabbix-web"]="http://localhost:8080/"
)

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$VALIDATION_LOG"
}

# Test result tracking
test_result() {
    local test_name="$1"
    local status="$2"  # PASS, FAIL, WARN, SKIP
    local details="$3"

    TEST_RESULTS["$test_name"]="$status"
    TEST_DETAILS["$test_name"]="$details"
    ((TOTAL_TESTS++))

    case "$status" in
        "FAIL")
            ((CRITICAL_FAILURES++))
            log "❌ CRITICAL: $test_name - $details"
            ;;
        "WARN")
            ((WARNING_COUNT++))
            log "⚠️ WARNING: $test_name - $details"
            ;;
        "PASS")
            log "✅ PASS: $test_name - $details"
            ;;
        "SKIP")
            log "⏭️ SKIP: $test_name - $details"
            ;;
    esac
}

# Test service health
test_service_health() {
    log "=== Testing Service Health ==="

    for service in "${!SERVICE_ENDPOINTS[@]}"; do
        local endpoint="${SERVICE_ENDPOINTS[$service]}"

        # Check if container is running
        if ! ${DOCKER} ps --filter "name=$service" --filter "status=running" --quiet | grep -q .; then
            test_result "service.${service}.running" "FAIL" "Container not running"
            continue
        fi

        # Test endpoint responsiveness
        if timeout 10 curl -s -f "$endpoint" &>/dev/null; then
            test_result "service.${service}.endpoint" "PASS" "Endpoint responding at $endpoint"
        else
            test_result "service.${service}.endpoint" "FAIL" "Endpoint not responding at $endpoint"
        fi

        # Test container health
        local health_status=$(${DOCKER} inspect "$service" --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
        if [[ "$health_status" == "healthy" ]]; then
            test_result "service.${service}.health" "PASS" "Container health check passing"
        elif [[ "$health_status" == "none" ]]; then
            test_result "service.${service}.health" "SKIP" "No health check configured"
        else
            test_result "service.${service}.health" "WARN" "Health check status: $health_status"
        fi
    done
}

# Test data collection pipeline
test_data_collection() {
    log "=== Testing Data Collection Pipeline ==="

    # Test Telegraf metrics collection
    if curl -s http://localhost:9273/metrics | grep -q "^# HELP"; then
        local metric_count=$(curl -s http://localhost:9273/metrics | grep -c "^# HELP")
        test_result "data.telegraf.metrics" "PASS" "Telegraf exposing $metric_count metric types"
    else
        test_result "data.telegraf.metrics" "FAIL" "Telegraf metrics endpoint not responding"
    fi

    # Test InfluxDB data ingestion
    if ${DOCKER} exec influxdb influx -execute 'SHOW DATABASES' 2>/dev/null | grep -q "telegraf"; then
        test_result "data.influxdb.database" "PASS" "InfluxDB telegraf database exists"

        # Test recent data
        local recent_points=$(${DOCKER} exec influxdb influx -database telegraf -execute 'SELECT COUNT(*) FROM cpu WHERE time > now() - 5m' 2>/dev/null | tail -1 || echo "0")
        if [[ "$recent_points" =~ ^[0-9]+$ ]] && [[ $recent_points -gt 0 ]]; then
            test_result "data.influxdb.recent" "PASS" "Recent data points in InfluxDB: $recent_points"
        else
            test_result "data.influxdb.recent" "WARN" "No recent data in InfluxDB"
        fi
    else
        test_result "data.influxdb.database" "FAIL" "InfluxDB telegraf database not found"
    fi

    # Test Prometheus scraping
    if curl -s http://localhost:9090/api/v1/targets | jq -e '.data.activeTargets[]' &>/dev/null; then
        local active_targets=$(curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length')
        test_result "data.prometheus.targets" "PASS" "Prometheus has $active_targets active targets"

        # Check target health
        local healthy_targets=$(curl -s http://localhost:9090/api/v1/targets | jq '[.data.activeTargets[] | select(.health == "up")] | length')
        local total_targets=$(curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length')
        if [[ $healthy_targets -eq $total_targets ]]; then
            test_result "data.prometheus.health" "PASS" "All $total_targets Prometheus targets healthy"
        else
            test_result "data.prometheus.health" "WARN" "Only $healthy_targets/$total_targets Prometheus targets healthy"
        fi
    else
        test_result "data.prometheus.targets" "FAIL" "Prometheus targets API not responding"
    fi
}

# Test alerting system
test_alerting_system() {
    log "=== Testing Alerting System ==="

    # Test Prometheus rules
    if curl -s http://localhost:9090/api/v1/rules | jq -e '.data.groups[]' &>/dev/null; then
        local rule_groups=$(curl -s http://localhost:9090/api/v1/rules | jq '.data.groups | length')
        test_result "alerting.prometheus.rules" "PASS" "Prometheus has $rule_groups rule groups loaded"

        # Check for recording rules
        local recording_rules=$(curl -s http://localhost:9090/api/v1/rules | jq '[.data.groups[].rules[] | select(.type == "recording")] | length')
        if [[ $recording_rules -gt 0 ]]; then
            test_result "alerting.prometheus.recording" "PASS" "$recording_rules recording rules active"
        else
            test_result "alerting.prometheus.recording" "WARN" "No recording rules found"
        fi

        # Check for alerting rules
        local alerting_rules=$(curl -s http://localhost:9090/api/v1/rules | jq '[.data.groups[].rules[] | select(.type == "alerting")] | length')
        if [[ $alerting_rules -gt 0 ]]; then
            test_result "alerting.prometheus.alerts" "PASS" "$alerting_rules alerting rules active"
        else
            test_result "alerting.prometheus.alerts" "WARN" "No alerting rules found"
        fi
    else
        test_result "alerting.prometheus.rules" "FAIL" "Prometheus rules API not responding"
    fi

    # Test Alertmanager
    if curl -s http://localhost:9093/api/v1/status | jq -e '.data' &>/dev/null; then
        test_result "alerting.alertmanager.status" "PASS" "Alertmanager API responding"

        # Check configuration
        if curl -s http://localhost:9093/api/v1/status | jq -e '.data.configYAML' &>/dev/null; then
            test_result "alerting.alertmanager.config" "PASS" "Alertmanager configuration loaded"
        else
            test_result "alerting.alertmanager.config" "FAIL" "Alertmanager configuration missing"
        fi
    else
        test_result "alerting.alertmanager.status" "FAIL" "Alertmanager API not responding"
    fi

    # Test current alerts
    local active_alerts=$(curl -s http://localhost:9093/api/v1/alerts | jq '[.data[] | select(.status.state == "active")] | length' 2>/dev/null || echo "0")
    if [[ $active_alerts -eq 0 ]]; then
        test_result "alerting.alerts.active" "PASS" "No active alerts (system healthy)"
    else
        test_result "alerting.alerts.active" "WARN" "$active_alerts active alerts (check alert details)"
    fi
}

# Test Phase 2 enhancements
test_phase2_enhancements() {
    log "=== Testing Phase 2 Enhancements ==="

    # Test OAuth/LDAP configuration
    if [[ -f "/home/mills/collections/grafana/grafana-oauth.ini" ]]; then
        if grep -q "enabled = true" "/home/mills/collections/grafana/grafana-oauth.ini"; then
            test_result "phase2.oauth.config" "PASS" "OAuth configuration deployed and enabled"
        else
            test_result "phase2.oauth.config" "WARN" "OAuth configuration exists but not enabled"
        fi
    else
        test_result "phase2.oauth.config" "FAIL" "OAuth configuration missing"
    fi

    # Test SSL certificates
    local ssl_certs=$(find /home/mills/collections/ssl-certs -name "*.crt" -not -name "ca.crt" | wc -l)
    if [[ $ssl_certs -gt 0 ]]; then
        test_result "phase2.ssl.certificates" "PASS" "$ssl_certs service certificates generated"

        # Check certificate validity
        local expired_certs=0
        for cert in /home/mills/collections/ssl-certs/*.crt; do
            if [[ -f "$cert" && "$cert" != *"ca.crt" ]]; then
                if ! openssl x509 -checkend 86400 -noout -in "$cert" &>/dev/null; then
                    ((expired_certs++))
                fi
            fi
        done

        if [[ $expired_certs -eq 0 ]]; then
            test_result "phase2.ssl.validity" "PASS" "All certificates valid for >24 hours"
        else
            test_result "phase2.ssl.validity" "WARN" "$expired_certs certificates expire within 24 hours"
        fi
    else
        test_result "phase2.ssl.certificates" "FAIL" "No SSL certificates found"
    fi

    # Test Vault configuration
    if [[ -f "/home/mills/collections/vault/vault-config.hcl" ]]; then
        test_result "phase2.vault.config" "PASS" "Vault configuration file exists"

        if [[ -x "/home/mills/collections/vault/vault-init.sh" ]]; then
            test_result "phase2.vault.init" "PASS" "Vault initialization script ready"
        else
            test_result "phase2.vault.init" "FAIL" "Vault initialization script missing or not executable"
        fi
    else
        test_result "phase2.vault.config" "FAIL" "Vault configuration missing"
    fi

    # Test backup system
    if [[ -x "/home/mills/collections/backup/backup-replication.sh" ]]; then
        test_result "phase2.backup.script" "PASS" "Backup replication script ready"

        if [[ -d "/home/mills/backups" ]]; then
            test_result "phase2.backup.directory" "PASS" "Backup directory structure exists"
        else
            test_result "phase2.backup.directory" "FAIL" "Backup directory not found"
        fi
    else
        test_result "phase2.backup.script" "FAIL" "Backup replication script missing"
    fi

    # Test security scanning
    if [[ -x "/home/mills/collections/security/container-security-scanner.sh" ]]; then
        test_result "phase2.security.scanner" "PASS" "Container security scanner ready"

        if [[ -d "/home/mills/security-scans" ]]; then
            test_result "phase2.security.output" "PASS" "Security scan output directory exists"
        else
            test_result "phase2.security.output" "FAIL" "Security scan output directory missing"
        fi
    else
        test_result "phase2.security.scanner" "FAIL" "Container security scanner missing"
    fi
}

# Test Tailscale integration
test_tailscale_integration() {
    log "=== Testing Tailscale Integration ==="

    # Test Tailscale status
    if command -v tailscale &>/dev/null; then
        if tailscale status &>/dev/null; then
            local tailscale_ip=$(tailscale ip -4 2>/dev/null || echo "unknown")
            test_result "tailscale.connection" "PASS" "Tailscale connected (IP: $tailscale_ip)"

            # Test peer count
            local peer_count=$(tailscale status | grep -c "^[0-9]" || echo "0")
            test_result "tailscale.peers" "PASS" "$peer_count peers in tailnet"
        else
            test_result "tailscale.connection" "FAIL" "Tailscale not connected"
        fi
    else
        test_result "tailscale.connection" "FAIL" "Tailscale not installed"
    fi

    # Test Tailscale integration scripts
    if [[ -x "/home/mills/bin/tailscale_up.sh" ]]; then
        test_result "tailscale.scripts.main" "PASS" "Main Tailscale integration script deployed"
    else
        test_result "tailscale.scripts.main" "FAIL" "Main Tailscale integration script missing"
    fi

    if [[ -x "/home/mills/bin/add_container_to_tailnet.sh" ]]; then
        test_result "tailscale.scripts.container" "PASS" "Container integration script deployed"
    else
        test_result "tailscale.scripts.container" "FAIL" "Container integration script missing"
    fi

    # Test Tailscale metrics exporter
    if [[ -x "/home/mills/bin/tailscale_metrics_exporter.sh" ]]; then
        test_result "tailscale.metrics.exporter" "PASS" "Tailscale metrics exporter deployed"
    else
        test_result "tailscale.metrics.exporter" "FAIL" "Tailscale metrics exporter missing"
    fi

    # Test Prometheus Tailnet configuration
    if [[ -f "/home/mills/output/20250627_214403/prometheus_tailnet.yml" ]]; then
        test_result "tailscale.prometheus.config" "PASS" "Prometheus Tailnet configuration exists"
    else
        test_result "tailscale.prometheus.config" "FAIL" "Prometheus Tailnet configuration missing"
    fi
}

# Test performance optimizations
test_performance_optimizations() {
    log "=== Testing Performance Optimizations ==="

    # Test recording rules
    if curl -s http://localhost:9090/api/v1/label/__name__/values | grep -q "instance:" 2>/dev/null; then
        local recording_metrics=$(curl -s http://localhost:9090/api/v1/label/__name__/values | grep -c "instance:" || echo "0")
        test_result "performance.recording.rules" "PASS" "$recording_metrics performance recording rules active"
    else
        test_result "performance.recording.rules" "WARN" "No performance recording rules found"
    fi

    # Test optimized configurations
    local optimized_configs=0
    for service in influxdb telegraf redis nginx; do
        if [[ -f "/home/mills/collections/$service/${service}-optimized.conf" ]] || [[ -f "/home/mills/collections/$service/${service}-cache.conf" ]]; then
            ((optimized_configs++))
        fi
    done

    if [[ $optimized_configs -gt 2 ]]; then
        test_result "performance.optimized.configs" "PASS" "$optimized_configs services have optimized configurations"
    else
        test_result "performance.optimized.configs" "WARN" "Limited optimized configurations ($optimized_configs services)"
    fi

    # Test SLA/SLO tracking
    if [[ -f "/home/mills/collections/prometheus/sla_slo_rules.yml" ]]; then
        local sla_rules=$(grep -c "sla:" "/home/mills/collections/prometheus/sla_slo_rules.yml" 2>/dev/null || echo "0")
        if [[ $sla_rules -gt 0 ]]; then
            test_result "performance.sla.rules" "PASS" "$sla_rules SLA tracking rules configured"
        else
            test_result "performance.sla.rules" "WARN" "SLA rules file exists but no rules found"
        fi
    else
        test_result "performance.sla.rules" "FAIL" "SLA/SLO rules file missing"
    fi

    # Test dashboard response times
    local grafana_response_time=$(curl -w "%{time_total}" -s -o /dev/null http://localhost:3000/api/health 2>/dev/null || echo "999")
    if (( $(echo "$grafana_response_time < 2.0" | bc -l) )); then
        test_result "performance.grafana.response" "PASS" "Grafana response time: ${grafana_response_time}s"
    else
        test_result "performance.grafana.response" "WARN" "Grafana slow response time: ${grafana_response_time}s"
    fi
}

# Test network connectivity and security
test_network_security() {
    log "=== Testing Network Security ==="

    # Test Docker network configuration
    local monitoring_networks=$(${DOCKER} network ls | grep -c "monitoring" || echo "0")
    if [[ $monitoring_networks -gt 0 ]]; then
        test_result "network.monitoring.networks" "PASS" "$monitoring_networks monitoring networks configured"
    else
        test_result "network.monitoring.networks" "WARN" "No dedicated monitoring networks found"
    fi

    # Test container security options
    local secure_containers=0
    for container in $(${DOCKER} ps --format "{{.Names}}"); do
        local security_opts=$(${DOCKER} inspect "$container" --format '{{.HostConfig.SecurityOpt}}' 2>/dev/null || echo "[]")
        if [[ "$security_opts" =~ "no-new-privileges:true" ]]; then
            ((secure_containers++))
        fi
    done

    local total_containers=$(${DOCKER} ps | wc -l)
    ((total_containers--))  # Remove header line

    if [[ $secure_containers -gt $((total_containers / 2)) ]]; then
        test_result "network.security.containers" "PASS" "$secure_containers/$total_containers containers use security options"
    else
        test_result "network.security.containers" "WARN" "Limited container security hardening ($secure_containers/$total_containers)"
    fi

    # Test firewall/iptables rules
    if command -v iptables &>/dev/null; then
        local docker_rules=$(iptables -L | grep -c "DOCKER" || echo "0")
        if [[ $docker_rules -gt 0 ]]; then
            test_result "network.firewall.docker" "PASS" "Docker firewall rules active"
        else
            test_result "network.firewall.docker" "WARN" "No Docker firewall rules detected"
        fi
    else
        test_result "network.firewall.docker" "SKIP" "iptables not available"
    fi
}

# Test backup and disaster recovery
test_backup_recovery() {
    log "=== Testing Backup and Recovery ==="

    # Test backup scripts
    if [[ -x "/home/mills/collections/backup/backup-replication.sh" ]]; then
        test_result "backup.replication.script" "PASS" "Backup replication script ready"

        # Test backup directory structure
        local backup_dirs=0
        for dir in daily weekly monthly staging; do
            if [[ -d "/home/mills/backups/$dir" ]]; then
                ((backup_dirs++))
            fi
        done

        if [[ $backup_dirs -eq 4 ]]; then
            test_result "backup.directory.structure" "PASS" "Complete backup directory structure"
        else
            test_result "backup.directory.structure" "WARN" "Incomplete backup directory structure ($backup_dirs/4)"
        fi
    else
        test_result "backup.replication.script" "FAIL" "Backup replication script missing"
    fi

    # Test backup health monitoring
    if [[ -x "/home/mills/collections/backup/backup-health-check.sh" ]]; then
        test_result "backup.health.script" "PASS" "Backup health check script ready"
    else
        test_result "backup.health.script" "FAIL" "Backup health check script missing"
    fi

    # Test cron job configuration (if accessible)
    if crontab -l 2>/dev/null | grep -q "backup"; then
        local backup_jobs=$(crontab -l | grep -c "backup" || echo "0")
        test_result "backup.cron.jobs" "PASS" "$backup_jobs backup cron jobs configured"
    else
        test_result "backup.cron.jobs" "WARN" "No backup cron jobs found"
    fi

    # Test encryption key
    if [[ -f "/etc/backup/encryption.key" ]]; then
        test_result "backup.encryption.key" "PASS" "Backup encryption key exists"
    else
        test_result "backup.encryption.key" "WARN" "Backup encryption key not found (will be generated on first run)"
    fi
}

# Generate comprehensive validation report
generate_comprehensive_report() {
    log "Generating comprehensive validation report..."

    mkdir -p "$RESULTS_DIR"

    local pass_count=0
    local fail_count=0
    local warn_count=0
    local skip_count=0

    for test in "${!TEST_RESULTS[@]}"; do
        case "${TEST_RESULTS[$test]}" in
            "PASS") ((pass_count++)) ;;
            "FAIL") ((fail_count++)) ;;
            "WARN") ((warn_count++)) ;;
            "SKIP") ((skip_count++)) ;;
        esac
    done

    local pass_rate=0
    if [[ $TOTAL_TESTS -gt 0 ]]; then
        pass_rate=$(( pass_count * 100 / TOTAL_TESTS ))
    fi

    cat > "$VALIDATION_REPORT" << EOF
# Comprehensive Monitoring Stack Validation Report

**Validation Date:** $(date '+%Y-%m-%d %H:%M:%S')
**Infrastructure:** Production Monitoring Stack
**Validation Scope:** Complete End-to-End Testing

## Executive Summary

### Overall Health Status
EOF

    if [[ $fail_count -eq 0 ]]; then
        echo "✅ **EXCELLENT** - All critical systems operational" >> "$VALIDATION_REPORT"
    elif [[ $fail_count -lt 3 ]]; then
        echo "⚠️ **GOOD** - Minor issues detected, system mostly operational" >> "$VALIDATION_REPORT"
    elif [[ $fail_count -lt 10 ]]; then
        echo "🟡 **FAIR** - Several issues require attention" >> "$VALIDATION_REPORT"
    else
        echo "❌ **POOR** - Significant issues requiring immediate action" >> "$VALIDATION_REPORT"
    fi

    cat >> "$VALIDATION_REPORT" << EOF

### Test Results Summary
- **Total Tests**: $TOTAL_TESTS
- **Passed**: $pass_count (${pass_rate}%)
- **Failed**: $fail_count
- **Warnings**: $warn_count
- **Skipped**: $skip_count

### Critical Metrics
- **Service Availability**: $(( (pass_count - warn_count) * 100 / TOTAL_TESTS ))%
- **Critical Failures**: $CRITICAL_FAILURES
- **System Readiness**: $( [[ $fail_count -eq 0 ]] && echo "Production Ready" || echo "Requires Attention")

## Detailed Test Results

### ✅ Passed Tests ($pass_count)
EOF

    for test in "${!TEST_RESULTS[@]}"; do
        if [[ "${TEST_RESULTS[$test]}" == "PASS" ]]; then
            echo "- **$test**: ${TEST_DETAILS[$test]}" >> "$VALIDATION_REPORT"
        fi
    done

    if [[ $fail_count -gt 0 ]]; then
        cat >> "$VALIDATION_REPORT" << EOF

### ❌ Failed Tests ($fail_count)
EOF
        for test in "${!TEST_RESULTS[@]}"; do
            if [[ "${TEST_RESULTS[$test]}" == "FAIL" ]]; then
                echo "- **$test**: ${TEST_DETAILS[$test]}" >> "$VALIDATION_REPORT"
            fi
        done
    fi

    if [[ $warn_count -gt 0 ]]; then
        cat >> "$VALIDATION_REPORT" << EOF

### ⚠️ Warnings ($warn_count)
EOF
        for test in "${!TEST_RESULTS[@]}"; do
            if [[ "${TEST_RESULTS[$test]}" == "WARN" ]]; then
                echo "- **$test**: ${TEST_DETAILS[$test]}" >> "$VALIDATION_REPORT"
            fi
        done
    fi

    if [[ $skip_count -gt 0 ]]; then
        cat >> "$VALIDATION_REPORT" << EOF

### ⏭️ Skipped Tests ($skip_count)
EOF
        for test in "${!TEST_RESULTS[@]}"; do
            if [[ "${TEST_RESULTS[$test]}" == "SKIP" ]]; then
                echo "- **$test**: ${TEST_DETAILS[$test]}" >> "$VALIDATION_REPORT"
            fi
        done
    fi

    cat >> "$VALIDATION_REPORT" << 'EOF'

## System Component Status

### Core Monitoring Services
| Component | Status | Health Check | Data Flow |
|-----------|--------|--------------|-----------|
EOF

    # Add service status table
    for service in grafana prometheus influxdb alertmanager loki; do
        local running_status="❌ Down"
        local health_status="❌ Fail"
        local data_status="❌ No Data"

        if [[ "${TEST_RESULTS[service.${service}.running]:-}" == "PASS" ]]; then
            running_status="✅ Running"
        fi

        if [[ "${TEST_RESULTS[service.${service}.endpoint]:-}" == "PASS" ]]; then
            health_status="✅ Healthy"
        elif [[ "${TEST_RESULTS[service.${service}.endpoint]:-}" == "WARN" ]]; then
            health_status="⚠️ Warning"
        fi

        if [[ "${TEST_RESULTS[data.${service}.metrics]:-}" == "PASS" ]] || [[ "${TEST_RESULTS[data.${service}.database]:-}" == "PASS" ]]; then
            data_status="✅ Active"
        fi

        echo "| $service | $running_status | $health_status | $data_status |" >> "$VALIDATION_REPORT"
    done

    cat >> "$VALIDATION_REPORT" << 'EOF'

### Phase 2 Enhancement Status
| Enhancement | Implementation | Configuration | Operational |
|-------------|----------------|---------------|-------------|
EOF

    # Add Phase 2 status
    local enhancements=("oauth" "ssl" "vault" "backup" "security")
    for enhancement in "${enhancements[@]}"; do
        local impl_status="❌ Missing"
        local config_status="❌ Not Configured"
        local ops_status="❌ Not Ready"

        # Check implementation status
        case "$enhancement" in
            "oauth")
                if [[ "${TEST_RESULTS[phase2.oauth.config]:-}" == "PASS" ]]; then
                    impl_status="✅ Deployed"
                    config_status="✅ Configured"
                    ops_status="✅ Ready"
                fi
                ;;
            "ssl")
                if [[ "${TEST_RESULTS[phase2.ssl.certificates]:-}" == "PASS" ]]; then
                    impl_status="✅ Deployed"
                    if [[ "${TEST_RESULTS[phase2.ssl.validity]:-}" == "PASS" ]]; then
                        config_status="✅ Valid"
                        ops_status="✅ Ready"
                    fi
                fi
                ;;
            "vault")
                if [[ "${TEST_RESULTS[phase2.vault.config]:-}" == "PASS" ]]; then
                    impl_status="✅ Deployed"
                    config_status="✅ Configured"
                    if [[ "${TEST_RESULTS[phase2.vault.init]:-}" == "PASS" ]]; then
                        ops_status="✅ Ready"
                    fi
                fi
                ;;
            "backup")
                if [[ "${TEST_RESULTS[phase2.backup.script]:-}" == "PASS" ]]; then
                    impl_status="✅ Deployed"
                    if [[ "${TEST_RESULTS[phase2.backup.directory]:-}" == "PASS" ]]; then
                        config_status="✅ Configured"
                        ops_status="✅ Ready"
                    fi
                fi
                ;;
            "security")
                if [[ "${TEST_RESULTS[phase2.security.scanner]:-}" == "PASS" ]]; then
                    impl_status="✅ Deployed"
                    if [[ "${TEST_RESULTS[phase2.security.output]:-}" == "PASS" ]]; then
                        config_status="✅ Configured"
                        ops_status="✅ Ready"
                    fi
                fi
                ;;
        esac

        echo "| $enhancement | $impl_status | $config_status | $ops_status |" >> "$VALIDATION_REPORT"
    done

    cat >> "$VALIDATION_REPORT" << 'EOF'

## Performance Metrics

### Response Time Analysis
EOF

    # Add performance metrics if available
    if [[ "${TEST_RESULTS[performance.grafana.response]:-}" == "PASS" ]]; then
        echo "- **Grafana Dashboard**: ${TEST_DETAILS[performance.grafana.response]}" >> "$VALIDATION_REPORT"
    fi

    if [[ "${TEST_RESULTS[data.telegraf.metrics]:-}" == "PASS" ]]; then
        echo "- **Telegraf Collection**: ${TEST_DETAILS[data.telegraf.metrics]}" >> "$VALIDATION_REPORT"
    fi

    cat >> "$VALIDATION_REPORT" << 'EOF'

### Data Pipeline Health
EOF

    if [[ "${TEST_RESULTS[data.prometheus.targets]:-}" == "PASS" ]]; then
        echo "- **Prometheus Targets**: ${TEST_DETAILS[data.prometheus.targets]}" >> "$VALIDATION_REPORT"
    fi

    if [[ "${TEST_RESULTS[data.influxdb.recent]:-}" == "PASS" ]]; then
        echo "- **InfluxDB Data Flow**: ${TEST_DETAILS[data.influxdb.recent]}" >> "$VALIDATION_REPORT"
    fi

    cat >> "$VALIDATION_REPORT" << 'EOF'

## Remediation Plan

### Immediate Actions (Critical - Within 24 Hours)
EOF

    local critical_actions=0
    for test in "${!TEST_RESULTS[@]}"; do
        if [[ "${TEST_RESULTS[$test]}" == "FAIL" ]] && [[ "$test" =~ (running|endpoint|database) ]]; then
            echo "- **$test**: ${TEST_DETAILS[$test]}" >> "$VALIDATION_REPORT"
            ((critical_actions++))
        fi
    done

    if [[ $critical_actions -eq 0 ]]; then
        echo "- No critical issues requiring immediate action" >> "$VALIDATION_REPORT"
    fi

    cat >> "$VALIDATION_REPORT" << 'EOF'

### Short-term Improvements (Within 1 Week)
EOF

    local short_term_actions=0
    for test in "${!TEST_RESULTS[@]}"; do
        if [[ "${TEST_RESULTS[$test]}" == "WARN" ]] || ([[ "${TEST_RESULTS[$test]}" == "FAIL" ]] && [[ ! "$test" =~ (running|endpoint|database) ]]); then
            echo "- **$test**: ${TEST_DETAILS[$test]}" >> "$VALIDATION_REPORT"
            ((short_term_actions++))
        fi
    done

    if [[ $short_term_actions -eq 0 ]]; then
        echo "- All systems operating within acceptable parameters" >> "$VALIDATION_REPORT"
    fi

    cat >> "$VALIDATION_REPORT" << 'EOF'

### Long-term Optimizations (Within 1 Month)
EOF

    for test in "${!TEST_RESULTS[@]}"; do
        if [[ "${TEST_RESULTS[$test]}" == "SKIP" ]]; then
            echo "- **$test**: ${TEST_DETAILS[$test]}" >> "$VALIDATION_REPORT"
        fi
    done

    cat >> "$VALIDATION_REPORT" << 'EOF'

## Operational Readiness

### Production Deployment Checklist
- [ ] All critical services healthy and responding
- [ ] Data collection pipeline operational
- [ ] Alerting system configured and tested
- [ ] Backup and recovery procedures validated
- [ ] Security measures implemented and verified
- [ ] Performance optimizations deployed
- [ ] Monitoring dashboards accessible
- [ ] Documentation updated and accessible

### Maintenance Schedule
- **Daily**: Health check monitoring, alert review
- **Weekly**: Performance metrics review, capacity planning
- **Monthly**: Security scans, backup testing, certificate renewal
- **Quarterly**: Comprehensive system validation, optimization review

## Support Information

### Emergency Procedures
1. **Service Outage**: Check container status, restart if needed
2. **Data Loss**: Initiate backup recovery procedures
3. **Security Incident**: Run security scans, review access logs
4. **Performance Degradation**: Check resource utilization, review optimization settings

### Key Contacts
- **System Administrator**: Review logs and service status
- **Security Team**: For security-related issues and incidents
- **Development Team**: For application-specific problems

---
*Report generated by Comprehensive Deployment Validation*
*Next validation scheduled: 1 week from deployment*
*For immediate assistance, check service logs and health endpoints*
EOF

    log "Comprehensive validation report generated: $VALIDATION_REPORT"
}

# Main validation execution
main() {
    log "=== Starting Comprehensive Deployment Validation ==="
    log "Validation started at $(date)"

    # Initialize results directory
    mkdir -p "$RESULTS_DIR"

    # Run all validation tests
    test_service_health
    test_data_collection
    test_alerting_system
    test_phase2_enhancements
    test_tailscale_integration
    test_performance_optimizations
    test_network_security
    test_backup_recovery

    # Generate comprehensive report
    generate_comprehensive_report

    # Final summary
    log "=== Validation Complete ==="
    log "Total tests: $TOTAL_TESTS"
    log "Critical failures: $CRITICAL_FAILURES"
    log "Warnings: $WARNING_COUNT"
    log "Report location: $VALIDATION_REPORT"

    if [[ $CRITICAL_FAILURES -eq 0 ]]; then
        log "✅ System validation successful - Ready for production"
        return 0
    elif [[ $CRITICAL_FAILURES -lt 5 ]]; then
        log "⚠️ System validation completed with minor issues"
        return 1
    else
        log "❌ System validation failed - Significant issues detected"
        return 2
    fi
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [options]

Options:
  --full              Run complete validation (default)
  --quick             Run essential health checks only
  --services          Test service health only
  --phase2            Test Phase 2 enhancements only
  --report            Generate report from cached results
  --help              Show this help message

Examples:
  $0                  # Run complete validation
  $0 --quick          # Quick health check
  $0 --services       # Service health only
  $0 --phase2         # Phase 2 enhancements only

EOF
    exit 1
}

# Execute based on arguments
case "${1:---full}" in
    --full|"")
        main
        ;;
    --quick)
        test_service_health
        test_data_collection
        generate_comprehensive_report
        ;;
    --services)
        test_service_health
        generate_comprehensive_report
        ;;
    --phase2)
        test_phase2_enhancements
        generate_comprehensive_report
        ;;
    --report)
        generate_comprehensive_report
        ;;
    --help)
        usage
        ;;
    *)
        log "ERROR: Unknown option: $1"
        usage
        ;;
esac
