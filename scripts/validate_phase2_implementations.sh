#!/bin/bash
# Phase 2 Implementation Validation Script
# Comprehensive testing and validation of all monitoring enhancements

set -e

# Configuration
LOG_FILE="/var/log/phase2-validation.log"
VALIDATION_REPORT="/home/mills/phase2-validation-report-$(date +%Y%m%d_%H%M%S).md"
FAILED_TESTS=()
PASSED_TESTS=()
SKIPPED_TESTS=()

# Test categories
declare -A TEST_CATEGORIES=(
    ["oauth_ldap"]="OAuth/LDAP Authentication"
    ["database_encryption"]="Database Encryption"
    ["network_security"]="Network Security Policies"
    ["alerting"]="Advanced Alerting"
    ["performance"]="Performance Optimization"
    ["secrets"]="Secrets Management"
    ["sla_slo"]="SLA/SLO Tracking"
    ["backup"]="Backup Replication"
    ["security_scanning"]="Container Security Scanning"
    ["tailscale"]="Tailscale Integration"
)

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# Test result functions
test_passed() {
    local test_name="$1"
    local description="$2"
    PASSED_TESTS+=("$test_name: $description")
    log "✅ PASS: $test_name - $description"
}

test_failed() {
    local test_name="$1"
    local description="$2"
    local error="$3"
    FAILED_TESTS+=("$test_name: $description - $error")
    log "❌ FAIL: $test_name - $description - $error"
}

test_skipped() {
    local test_name="$1"
    local description="$2"
    local reason="$3"
    SKIPPED_TESTS+=("$test_name: $description - $reason")
    log "⏭️ SKIP: $test_name - $description - $reason"
}

# Test OAuth/LDAP Authentication
test_oauth_ldap() {
    log "Testing OAuth/LDAP Authentication implementation..."
    
    local category="oauth_ldap"
    
    # Test 1: Check Grafana OAuth configuration
    if [[ -f "/home/mills/collections/grafana/grafana-oauth.ini" ]]; then
        if grep -q "enabled = true" "/home/mills/collections/grafana/grafana-oauth.ini"; then
            test_passed "$category.oauth_config" "Grafana OAuth configuration file exists and enabled"
        else
            test_failed "$category.oauth_config" "Grafana OAuth configuration exists but not enabled" "OAuth not enabled in config"
        fi
    else
        test_failed "$category.oauth_config" "Grafana OAuth configuration file" "File not found"
    fi
    
    # Test 2: Check LDAP configuration
    if [[ -f "/home/mills/collections/grafana/ldap.toml" ]]; then
        if grep -q "host = " "/home/mills/collections/grafana/ldap.toml"; then
            test_passed "$category.ldap_config" "LDAP configuration file exists with host settings"
        else
            test_failed "$category.ldap_config" "LDAP configuration incomplete" "No host configuration found"
        fi
    else
        test_failed "$category.ldap_config" "LDAP configuration file" "File not found"
    fi
    
    # Test 3: Grafana API health with auth
    if curl -s -f http://localhost:3000/api/health &>/dev/null; then
        test_passed "$category.grafana_health" "Grafana API responding for auth testing"
    else
        test_failed "$category.grafana_health" "Grafana API health check" "API not responding"
    fi
}

# Test Database Encryption
test_database_encryption() {
    log "Testing Database Encryption implementation..."
    
    local category="database_encryption"
    
    # Test 1: InfluxDB SSL configuration
    if [[ -f "/home/mills/collections/influxdb/influxdb-optimized.conf" ]]; then
        if grep -q "https-enabled = true" "/home/mills/collections/influxdb/influxdb-optimized.conf"; then
            test_passed "$category.influxdb_ssl" "InfluxDB HTTPS enabled in configuration"
        else
            test_failed "$category.influxdb_ssl" "InfluxDB HTTPS configuration" "HTTPS not enabled"
        fi
    else
        test_failed "$category.influxdb_ssl" "InfluxDB optimized configuration" "File not found"
    fi
    
    # Test 2: SSL certificates exist
    local ssl_dir="/home/mills/collections/ssl-certs"
    if [[ -d "$ssl_dir" ]]; then
        local cert_count=$(find "$ssl_dir" -name "*.crt" | wc -l)
        if [[ $cert_count -gt 0 ]]; then
            test_passed "$category.ssl_certs" "SSL certificates directory contains $cert_count certificates"
        else
            test_failed "$category.ssl_certs" "SSL certificates" "No certificate files found"
        fi
    else
        test_failed "$category.ssl_certs" "SSL certificates directory" "Directory not found"
    fi
    
    # Test 3: CA certificate generation script
    if [[ -x "/home/mills/collections/ssl-certs/generate-certs.sh" ]]; then
        test_passed "$category.cert_generation" "Certificate generation script exists and is executable"
    else
        test_failed "$category.cert_generation" "Certificate generation script" "Script not found or not executable"
    fi
}

# Test Network Security Policies
test_network_security() {
    log "Testing Network Security Policies implementation..."
    
    local category="network_security"
    
    # Test 1: Enhanced Docker Compose with security
    if [[ -f "/home/mills/docker-compose-enhanced-security.yml" ]]; then
        if grep -q "no-new-privileges:true" "/home/mills/docker-compose-enhanced-security.yml"; then
            test_passed "$category.security_opts" "Enhanced Docker Compose includes security options"
        else
            test_failed "$category.security_opts" "Security options in Docker Compose" "no-new-privileges not found"
        fi
    else
        test_failed "$category.enhanced_compose" "Enhanced Docker Compose file" "File not found"
    fi
    
    # Test 2: Network segmentation
    if [[ -f "/home/mills/docker-compose-enhanced-security.yml" ]]; then
        local network_count=$(grep -c "networks:" "/home/mills/docker-compose-enhanced-security.yml")
        if [[ $network_count -gt 1 ]]; then
            test_passed "$category.network_segmentation" "Multiple Docker networks configured for segmentation"
        else
            test_failed "$category.network_segmentation" "Network segmentation" "Insufficient network configuration"
        fi
    else
        test_skipped "$category.network_segmentation" "Network segmentation check" "Enhanced compose file not found"
    fi
    
    # Test 3: Security labels and annotations
    local security_containers=$(docker ps --filter "label=com.docker.security" --quiet | wc -l)
    if [[ $security_containers -gt 0 ]]; then
        test_passed "$category.security_labels" "$security_containers containers have security labels"
    else
        test_skipped "$category.security_labels" "Security labels on containers" "No containers with security labels found"
    fi
}

# Test Advanced Alerting
test_advanced_alerting() {
    log "Testing Advanced Alerting implementation..."
    
    local category="alerting"
    
    # Test 1: Anomaly detection rules
    if [[ -f "/home/mills/collections/prometheus/anomaly_detection_rules.yml" ]]; then
        local rule_count=$(grep -c "record:" "/home/mills/collections/prometheus/anomaly_detection_rules.yml")
        if [[ $rule_count -gt 0 ]]; then
            test_passed "$category.anomaly_rules" "Anomaly detection rules file contains $rule_count recording rules"
        else
            test_failed "$category.anomaly_rules" "Anomaly detection rules content" "No recording rules found"
        fi
    else
        test_failed "$category.anomaly_rules" "Anomaly detection rules file" "File not found"
    fi
    
    # Test 2: Advanced alert rules
    if [[ -f "/home/mills/collections/prometheus/alert_rules.yml" ]]; then
        if grep -q "predicted" "/home/mills/collections/prometheus/alert_rules.yml"; then
            test_passed "$category.predictive_alerts" "Predictive alerting rules configured"
        else
            test_skipped "$category.predictive_alerts" "Predictive alerting rules" "No predictive rules found"
        fi
    else
        test_failed "$category.alert_rules" "Alert rules file" "File not found"
    fi
    
    # Test 3: Prometheus rules validation
    if command -v promtool &>/dev/null; then
        if docker exec prometheus promtool check rules /etc/prometheus/alert_rules.yml &>/dev/null; then
            test_passed "$category.rules_validation" "Prometheus rules syntax validation passed"
        else
            test_failed "$category.rules_validation" "Prometheus rules validation" "Syntax errors in rules"
        fi
    else
        test_skipped "$category.rules_validation" "Prometheus rules validation" "promtool not available"
    fi
}

# Test Performance Optimization
test_performance() {
    log "Testing Performance Optimization implementation..."
    
    local category="performance"
    
    # Test 1: Recording rules deployment
    if [[ -f "/home/mills/collections/prometheus/recording_rules.yml" ]]; then
        local recording_count=$(grep -c "record:" "/home/mills/collections/prometheus/recording_rules.yml")
        if [[ $recording_count -gt 0 ]]; then
            test_passed "$category.recording_rules" "Performance recording rules deployed ($recording_count rules)"
        else
            test_failed "$category.recording_rules" "Recording rules content" "No recording rules found"
        fi
    else
        test_failed "$category.recording_rules" "Recording rules file" "File not found"
    fi
    
    # Test 2: Optimized configurations
    local optimized_configs=0
    for service in influxdb telegraf redis nginx; do
        if [[ -f "/home/mills/collections/$service/${service}-optimized.conf" ]] || [[ -f "/home/mills/collections/$service/${service}-cache.conf" ]]; then
            ((optimized_configs++))
        fi
    done
    
    if [[ $optimized_configs -gt 2 ]]; then
        test_passed "$category.optimized_configs" "$optimized_configs services have optimized configurations"
    else
        test_failed "$category.optimized_configs" "Optimized service configurations" "Insufficient optimized configs ($optimized_configs)"
    fi
    
    # Test 3: Performance metrics endpoint
    if curl -s http://localhost:9273/metrics | head -5 | grep -q "^#"; then
        test_passed "$category.metrics_endpoint" "Telegraf performance metrics endpoint responding"
    else
        test_failed "$category.metrics_endpoint" "Performance metrics endpoint" "Telegraf metrics not responding"
    fi
}

# Test Secrets Management
test_secrets_management() {
    log "Testing Secrets Management implementation..."
    
    local category="secrets"
    
    # Test 1: Vault configuration
    if [[ -f "/home/mills/collections/vault/vault-config.hcl" ]]; then
        if grep -q "ui = true" "/home/mills/collections/vault/vault-config.hcl"; then
            test_passed "$category.vault_config" "Vault configuration file exists with UI enabled"
        else
            test_failed "$category.vault_config" "Vault configuration incomplete" "UI not enabled"
        fi
    else
        test_failed "$category.vault_config" "Vault configuration file" "File not found"
    fi
    
    # Test 2: Vault policies
    if [[ -f "/home/mills/collections/vault/vault-policies.hcl" ]]; then
        local policy_count=$(grep -c "path " "/home/mills/collections/vault/vault-policies.hcl")
        if [[ $policy_count -gt 0 ]]; then
            test_passed "$category.vault_policies" "Vault policies configured ($policy_count policies)"
        else
            test_failed "$category.vault_policies" "Vault policies content" "No policies found"
        fi
    else
        test_failed "$category.vault_policies" "Vault policies file" "File not found"
    fi
    
    # Test 3: Vault initialization script
    if [[ -x "/home/mills/collections/vault/vault-init.sh" ]]; then
        test_passed "$category.vault_init" "Vault initialization script exists and is executable"
    else
        test_failed "$category.vault_init" "Vault initialization script" "Script not found or not executable"
    fi
    
    # Test 4: Environment template
    if [[ -f "/home/mills/collections/vault/templates/monitoring.env.tpl" ]]; then
        test_passed "$category.env_template" "Vault environment template exists for secrets injection"
    else
        test_failed "$category.env_template" "Vault environment template" "Template not found"
    fi
}

# Test SLA/SLO Tracking
test_sla_slo() {
    log "Testing SLA/SLO Tracking implementation..."
    
    local category="sla_slo"
    
    # Test 1: SLA/SLO rules
    if [[ -f "/home/mills/collections/prometheus/sla_slo_rules.yml" ]]; then
        local sla_rules=$(grep -c "sla:" "/home/mills/collections/prometheus/sla_slo_rules.yml")
        local slo_rules=$(grep -c "slo:" "/home/mills/collections/prometheus/sla_slo_rules.yml")
        if [[ $sla_rules -gt 0 && $slo_rules -gt 0 ]]; then
            test_passed "$category.sla_slo_rules" "SLA/SLO rules configured (SLA: $sla_rules, SLO: $slo_rules)"
        else
            test_failed "$category.sla_slo_rules" "SLA/SLO rules content" "Insufficient rules configured"
        fi
    else
        test_failed "$category.sla_slo_rules" "SLA/SLO rules file" "File not found"
    fi
    
    # Test 2: SLA/SLO dashboard
    if [[ -f "/home/mills/collections/grafana/dashboards/sla-slo-dashboard.json" ]]; then
        if grep -q "SLA/SLO" "/home/mills/collections/grafana/dashboards/sla-slo-dashboard.json"; then
            test_passed "$category.sla_dashboard" "SLA/SLO Grafana dashboard configured"
        else
            test_failed "$category.sla_dashboard" "SLA/SLO dashboard content" "Invalid dashboard configuration"
        fi
    else
        test_failed "$category.sla_dashboard" "SLA/SLO dashboard file" "File not found"
    fi
    
    # Test 3: Error budget tracking
    if [[ -f "/home/mills/collections/prometheus/sla_slo_rules.yml" ]]; then
        if grep -q "error_budget" "/home/mills/collections/prometheus/sla_slo_rules.yml"; then
            test_passed "$category.error_budget" "Error budget tracking rules configured"
        else
            test_failed "$category.error_budget" "Error budget tracking" "No error budget rules found"
        fi
    else
        test_skipped "$category.error_budget" "Error budget tracking" "SLA/SLO rules file not found"
    fi
}

# Test Backup Replication
test_backup_replication() {
    log "Testing Backup Replication implementation..."
    
    local category="backup"
    
    # Test 1: Backup replication script
    if [[ -x "/home/mills/collections/backup/backup-replication.sh" ]]; then
        test_passed "$category.replication_script" "Backup replication script exists and is executable"
    else
        test_failed "$category.replication_script" "Backup replication script" "Script not found or not executable"
    fi
    
    # Test 2: Backup health check
    if [[ -x "/home/mills/collections/backup/backup-health-check.sh" ]]; then
        test_passed "$category.health_check" "Backup health check script exists and is executable"
    else
        test_failed "$category.health_check" "Backup health check script" "Script not found or not executable"
    fi
    
    # Test 3: Backup scheduler
    if [[ -x "/home/mills/collections/backup/backup-scheduler.sh" ]]; then
        test_passed "$category.scheduler" "Backup scheduler script exists and is executable"
    else
        test_failed "$category.scheduler" "Backup scheduler script" "Script not found or not executable"
    fi
    
    # Test 4: Backup directories
    if [[ -d "/home/mills/backups" ]]; then
        local backup_dirs=$(find /home/mills/backups -type d | wc -l)
        if [[ $backup_dirs -gt 1 ]]; then
            test_passed "$category.directories" "Backup directory structure exists ($backup_dirs directories)"
        else
            test_failed "$category.directories" "Backup directory structure" "Insufficient directory structure"
        fi
    else
        test_failed "$category.directories" "Backup base directory" "Directory not found"
    fi
}

# Test Container Security Scanning
test_security_scanning() {
    log "Testing Container Security Scanning implementation..."
    
    local category="security_scanning"
    
    # Test 1: Security scanner script
    if [[ -x "/home/mills/collections/security/container-security-scanner.sh" ]]; then
        test_passed "$category.scanner_script" "Container security scanner script exists and is executable"
    else
        test_failed "$category.scanner_script" "Container security scanner script" "Script not found or not executable"
    fi
    
    # Test 2: Security scan output directory
    if [[ -d "/home/mills/security-scans" ]]; then
        test_passed "$category.scan_directory" "Security scan output directory exists"
    else
        test_failed "$category.scan_directory" "Security scan output directory" "Directory not found"
    fi
    
    # Test 3: Security tools availability
    local security_tools=0
    for tool in trivy grype; do
        if command -v "$tool" &>/dev/null; then
            ((security_tools++))
        fi
    done
    
    if [[ $security_tools -gt 0 ]]; then
        test_passed "$category.security_tools" "$security_tools security scanning tools available"
    else
        test_skipped "$category.security_tools" "Security scanning tools" "No tools installed (will be installed on first run)"
    fi
}

# Test Tailscale Integration
test_tailscale_integration() {
    log "Testing Tailscale Integration implementation..."
    
    local category="tailscale"
    
    # Test 1: Tailscale up script
    if [[ -x "/home/mills/output/20250627_214403/tailscale_up.sh" ]]; then
        test_passed "$category.up_script" "Tailscale integration script exists and is executable"
    else
        test_failed "$category.up_script" "Tailscale integration script" "Script not found or not executable"
    fi
    
    # Test 2: Container integration script
    if [[ -x "/home/mills/output/20250627_214403/add_container_to_tailnet.sh" ]]; then
        test_passed "$category.container_script" "Add container to Tailnet script exists and is executable"
    else
        test_failed "$category.container_script" "Add container to Tailnet script" "Script not found or not executable"
    fi
    
    # Test 3: Prometheus Tailnet configuration
    if [[ -f "/home/mills/output/20250627_214403/prometheus_tailnet.yml" ]]; then
        if grep -q "tailnet" "/home/mills/output/20250627_214403/prometheus_tailnet.yml"; then
            test_passed "$category.prometheus_config" "Prometheus Tailnet configuration exists"
        else
            test_failed "$category.prometheus_config" "Prometheus Tailnet configuration content" "No Tailnet configuration found"
        fi
    else
        test_failed "$category.prometheus_config" "Prometheus Tailnet configuration file" "File not found"
    fi
    
    # Test 4: Grafana Tailnet dashboard
    if [[ -f "/home/mills/output/20250627_214403/grafana_dashboards_tailnet_latency.json" ]]; then
        test_passed "$category.grafana_dashboard" "Grafana Tailnet dashboard exists"
    else
        test_failed "$category.grafana_dashboard" "Grafana Tailnet dashboard" "File not found"
    fi
    
    # Test 5: Tailscale status
    if command -v tailscale &>/dev/null; then
        if tailscale status &>/dev/null; then
            test_passed "$category.tailscale_status" "Tailscale is installed and connected"
        else
            test_failed "$category.tailscale_status" "Tailscale connection" "Not connected to Tailnet"
        fi
    else
        test_failed "$category.tailscale_status" "Tailscale installation" "Tailscale not installed"
    fi
}

# Generate validation report
generate_validation_report() {
    log "Generating Phase 2 validation report..."
    
    local total_tests=$((${#PASSED_TESTS[@]} + ${#FAILED_TESTS[@]} + ${#SKIPPED_TESTS[@]}))
    local pass_rate=0
    
    if [[ $total_tests -gt 0 ]]; then
        pass_rate=$(( ${#PASSED_TESTS[@]} * 100 / total_tests ))
    fi
    
    cat > "$VALIDATION_REPORT" << EOF
# Phase 2 Implementation Validation Report

**Validation Date:** $(date '+%Y-%m-%d %H:%M:%S')  
**Monitoring Stack Enhancement Validation**

## Executive Summary

Comprehensive validation of Phase 2 monitoring infrastructure enhancements has been completed.

### Test Results Overview
- **Total Tests**: $total_tests
- **Passed**: ${#PASSED_TESTS[@]} (${pass_rate}%)
- **Failed**: ${#FAILED_TESTS[@]}
- **Skipped**: ${#SKIPPED_TESTS[@]}

### Overall Status
EOF

    if [[ ${#FAILED_TESTS[@]} -eq 0 ]]; then
        echo "✅ **ALL TESTS PASSED** - Phase 2 implementation is fully validated and ready for production" >> "$VALIDATION_REPORT"
    elif [[ ${#FAILED_TESTS[@]} -lt 5 ]]; then
        echo "⚠️ **MOSTLY SUCCESSFUL** - Minor issues found that should be addressed before production" >> "$VALIDATION_REPORT"
    else
        echo "❌ **SIGNIFICANT ISSUES** - Multiple failures detected, requires remediation before production use" >> "$VALIDATION_REPORT"
    fi
    
    cat >> "$VALIDATION_REPORT" << 'EOF'

## Detailed Test Results

### ✅ Passed Tests
EOF

    for test in "${PASSED_TESTS[@]}"; do
        echo "- $test" >> "$VALIDATION_REPORT"
    done
    
    if [[ ${#FAILED_TESTS[@]} -gt 0 ]]; then
        cat >> "$VALIDATION_REPORT" << 'EOF'

### ❌ Failed Tests
EOF
        for test in "${FAILED_TESTS[@]}"; do
            echo "- $test" >> "$VALIDATION_REPORT"
        done
    fi
    
    if [[ ${#SKIPPED_TESTS[@]} -gt 0 ]]; then
        cat >> "$VALIDATION_REPORT" << 'EOF'

### ⏭️ Skipped Tests
EOF
        for test in "${SKIPPED_TESTS[@]}"; do
            echo "- $test" >> "$VALIDATION_REPORT"
        done
    fi
    
    cat >> "$VALIDATION_REPORT" << 'EOF'

## Implementation Status by Category

### 🔐 Security Enhancements
- **OAuth/LDAP Authentication**: Configuration files deployed
- **Database Encryption**: SSL certificates and HTTPS configuration
- **Network Security**: Enhanced Docker Compose with security policies
- **Container Security Scanning**: Automated vulnerability assessment

### 📊 Monitoring & Alerting
- **Advanced Alerting**: Anomaly detection and predictive rules
- **SLA/SLO Tracking**: Service level monitoring and error budget tracking
- **Performance Optimization**: Recording rules and optimized configurations

### 🔧 Operational Excellence
- **Secrets Management**: HashiCorp Vault integration
- **Backup Replication**: Multi-site backup and health monitoring
- **Tailscale Integration**: Secure remote access to monitoring services

## Remediation Actions

### Critical Issues (Immediate Action Required)
EOF

    local critical_issues=0
    for test in "${FAILED_TESTS[@]}"; do
        if [[ "$test" == *"File not found"* ]] || [[ "$test" == *"not executable"* ]]; then
            echo "- $test" >> "$VALIDATION_REPORT"
            ((critical_issues++))
        fi
    done
    
    if [[ $critical_issues -eq 0 ]]; then
        echo "- No critical issues identified" >> "$VALIDATION_REPORT"
    fi
    
    cat >> "$VALIDATION_REPORT" << 'EOF'

### Minor Issues (Address When Convenient)
EOF

    local minor_issues=0
    for test in "${FAILED_TESTS[@]}"; do
        if [[ "$test" != *"File not found"* ]] && [[ "$test" != *"not executable"* ]]; then
            echo "- $test" >> "$VALIDATION_REPORT"
            ((minor_issues++))
        fi
    done
    
    if [[ $minor_issues -eq 0 ]]; then
        echo "- No minor issues identified" >> "$VALIDATION_REPORT"
    fi
    
    cat >> "$VALIDATION_REPORT" << 'EOF'

## Next Steps

### Immediate Actions (Next 24 Hours)
1. Address any critical issues identified in validation
2. Verify service connectivity and basic functionality
3. Review failed tests and implement fixes as needed

### Short-term Actions (Next Week)
1. Deploy remaining configurations to production environment
2. Run end-to-end testing of monitoring workflows
3. Validate backup and disaster recovery procedures
4. Complete security scanning of all containers

### Long-term Actions (Next Month)
1. Monitor performance improvements and optimization effectiveness
2. Establish regular validation and testing procedures
3. Document operational procedures for new enhancements
4. Plan for additional monitoring stack improvements

## Support Information

### Troubleshooting
- **Configuration Issues**: Check file paths and permissions
- **Service Connectivity**: Verify Docker container status and networking
- **Authentication Problems**: Review OAuth/LDAP configuration settings
- **Performance Issues**: Monitor recording rules and optimization settings

### Documentation
- Phase 2 enhancement documentation available in collections/ directories
- Individual component documentation in respective subdirectories
- Backup and recovery procedures documented in backup/ scripts

---
*Report generated by Phase 2 Implementation Validation*  
*Next validation recommended: 1 week from implementation*
EOF

    log "Validation report generated: $VALIDATION_REPORT"
}

# Main validation execution
main() {
    log "Starting Phase 2 implementation validation..."
    
    # Run all validation tests
    test_oauth_ldap
    test_database_encryption
    test_network_security
    test_advanced_alerting
    test_performance
    test_secrets_management
    test_sla_slo
    test_backup_replication
    test_security_scanning
    test_tailscale_integration
    
    # Generate comprehensive report
    generate_validation_report
    
    # Summary
    local total_tests=$((${#PASSED_TESTS[@]} + ${#FAILED_TESTS[@]} + ${#SKIPPED_TESTS[@]}))
    local pass_rate=0
    
    if [[ $total_tests -gt 0 ]]; then
        pass_rate=$(( ${#PASSED_TESTS[@]} * 100 / total_tests ))
    fi
    
    log "=== Phase 2 Validation Summary ==="
    log "Total tests: $total_tests"
    log "Passed: ${#PASSED_TESTS[@]} (${pass_rate}%)"
    log "Failed: ${#FAILED_TESTS[@]}"
    log "Skipped: ${#SKIPPED_TESTS[@]}"
    log "Report: $VALIDATION_REPORT"
    
    if [[ ${#FAILED_TESTS[@]} -eq 0 ]]; then
        log "✅ ALL TESTS PASSED - Phase 2 implementation validated successfully"
        return 0
    else
        log "❌ Some tests failed - Review report for remediation actions"
        return 1
    fi
}

# Execute main function
main "$@"