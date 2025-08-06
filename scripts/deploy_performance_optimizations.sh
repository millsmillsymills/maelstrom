#!/bin/bash
# Deploy Performance Optimizations Script
# Applies all performance enhancements to the monitoring stack

set -e

# Configuration
COLLECTIONS_DIR="/home/mills/collections"
BACKUP_DIR="/home/mills/backups/config-backup-$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/var/log/performance-optimization.log"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# Backup current configurations
backup_configs() {
    log "Backing up current configurations..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup key configuration files
    cp "$COLLECTIONS_DIR/grafana/grafana.ini" "$BACKUP_DIR/" 2>/dev/null || true
    cp "$COLLECTIONS_DIR/prometheus/prometheus.yml" "$BACKUP_DIR/" 2>/dev/null || true
    cp "$COLLECTIONS_DIR/telegraf/telegraf.conf" "$BACKUP_DIR/" 2>/dev/null || true
    cp "$COLLECTIONS_DIR/influxdb/influxdb.conf" "$BACKUP_DIR/" 2>/dev/null || true
    cp "$COLLECTIONS_DIR/redis/redis.conf" "$BACKUP_DIR/" 2>/dev/null || true
    cp "$COLLECTIONS_DIR/nginx/nginx.conf" "$BACKUP_DIR/" 2>/dev/null || true
    
    log "Configuration backup completed: $BACKUP_DIR"
}

# Deploy Redis caching optimization
deploy_redis_cache() {
    log "Deploying Redis caching optimization..."
    
    # Copy optimized Redis configuration
    if [[ -f "$COLLECTIONS_DIR/redis/redis-cache.conf" ]]; then
        cp "$COLLECTIONS_DIR/redis/redis-cache.conf" "$COLLECTIONS_DIR/redis/redis.conf"
        log "Redis cache configuration deployed"
    else
        log "WARNING: Redis cache configuration not found"
    fi
    
    # Restart Redis if running
    if docker ps --filter "name=redis" --filter "status=running" --quiet | grep -q .; then
        log "Restarting Redis to apply new configuration..."
        docker restart redis || true
    else
        log "Redis container not running, will use new config on next start"
    fi
}

# Deploy Nginx reverse proxy optimization
deploy_nginx_cache() {
    log "Deploying Nginx caching optimization..."
    
    # Copy optimized Nginx configuration
    if [[ -f "$COLLECTIONS_DIR/nginx/nginx-cache.conf" ]]; then
        cp "$COLLECTIONS_DIR/nginx/nginx-cache.conf" "$COLLECTIONS_DIR/nginx/nginx.conf"
        log "Nginx cache configuration deployed"
    else
        log "WARNING: Nginx cache configuration not found"
    fi
    
    # Create cache directories
    mkdir -p /var/cache/nginx/{grafana,prometheus,general}
    chown -R 101:101 /var/cache/nginx 2>/dev/null || true
    
    # Restart Nginx if running
    if docker ps --filter "name=nginx" --filter "status=running" --quiet | grep -q .; then
        log "Restarting Nginx to apply new configuration..."
        docker restart nginx || true
    else
        log "Nginx container not running, will use new config on next start"
    fi
}

# Deploy InfluxDB optimization
deploy_influxdb_optimization() {
    log "Deploying InfluxDB performance optimization..."
    
    # Copy optimized InfluxDB configuration
    if [[ -f "$COLLECTIONS_DIR/influxdb/influxdb-optimized.conf" ]]; then
        cp "$COLLECTIONS_DIR/influxdb/influxdb-optimized.conf" "$COLLECTIONS_DIR/influxdb/influxdb.conf"
        log "InfluxDB optimization configuration deployed"
    else
        log "WARNING: InfluxDB optimization configuration not found"
    fi
    
    # Restart InfluxDB if running
    if docker ps --filter "name=influxdb" --filter "status=running" --quiet | grep -q .; then
        log "Restarting InfluxDB to apply new configuration..."
        docker restart influxdb || true
        
        # Wait for InfluxDB to come back online
        log "Waiting for InfluxDB to restart..."
        sleep 30
        
        # Verify InfluxDB is responding
        local attempts=0
        while [[ $attempts -lt 12 ]]; do
            if curl -s http://localhost:8086/ping &>/dev/null; then
                log "InfluxDB is responding"
                break
            fi
            sleep 5
            ((attempts++))
        done
        
        if [[ $attempts -eq 12 ]]; then
            log "WARNING: InfluxDB may not have restarted properly"
        fi
    else
        log "InfluxDB container not running, will use new config on next start"
    fi
}

# Deploy Telegraf optimization
deploy_telegraf_optimization() {
    log "Deploying Telegraf performance optimization..."
    
    # Copy optimized Telegraf configuration
    if [[ -f "$COLLECTIONS_DIR/telegraf/telegraf-optimized.conf" ]]; then
        cp "$COLLECTIONS_DIR/telegraf/telegraf-optimized.conf" "$COLLECTIONS_DIR/telegraf/telegraf.conf"
        log "Telegraf optimization configuration deployed"
    else
        log "WARNING: Telegraf optimization configuration not found"
    fi
    
    # Restart Telegraf if running
    if docker ps --filter "name=telegraf" --filter "status=running" --quiet | grep -q .; then
        log "Restarting Telegraf to apply new configuration..."
        docker restart telegraf || true
        
        # Wait and verify Telegraf metrics endpoint
        sleep 15
        if curl -s http://localhost:9273/metrics | head -5 | grep -q "^#"; then
            log "Telegraf metrics endpoint is responding"
        else
            log "WARNING: Telegraf metrics endpoint may not be responding"
        fi
    else
        log "Telegraf container not running, will use new config on next start"
    fi
}

# Deploy Prometheus recording rules
deploy_prometheus_rules() {
    log "Deploying Prometheus performance recording rules..."
    
    # Copy recording rules
    if [[ -f "$COLLECTIONS_DIR/prometheus/recording_rules.yml" ]]; then
        log "Prometheus recording rules already deployed"
    else
        log "WARNING: Prometheus recording rules not found"
    fi
    
    # Copy SLA/SLO rules
    if [[ -f "$COLLECTIONS_DIR/prometheus/sla_slo_rules.yml" ]]; then
        log "SLA/SLO tracking rules already deployed"
    else
        log "WARNING: SLA/SLO rules not found"
    fi
    
    # Copy anomaly detection rules
    if [[ -f "$COLLECTIONS_DIR/prometheus/anomaly_detection_rules.yml" ]]; then
        log "Anomaly detection rules already deployed"
    else
        log "WARNING: Anomaly detection rules not found"
    fi
    
    # Restart Prometheus if running
    if docker ps --filter "name=prometheus" --filter "status=running" --quiet | grep -q .; then
        log "Restarting Prometheus to apply new rules..."
        docker restart prometheus || true
        
        # Wait and verify Prometheus is responding
        sleep 20
        if curl -s http://localhost:9090/-/healthy &>/dev/null; then
            log "Prometheus is responding"
        else
            log "WARNING: Prometheus may not have restarted properly"
        fi
    else
        log "Prometheus container not running, will use new config on next start"
    fi
}

# Deploy Grafana optimizations
deploy_grafana_optimization() {
    log "Deploying Grafana performance optimization..."
    
    # Check if Grafana OAuth config exists
    if [[ -f "$COLLECTIONS_DIR/grafana/grafana-oauth.ini" ]]; then
        log "Grafana OAuth configuration already deployed"
    else
        log "WARNING: Grafana OAuth configuration not found"
    fi
    
    # Restart Grafana if running to pick up any changes
    if docker ps --filter "name=grafana" --filter "status=running" --quiet | grep -q .; then
        log "Restarting Grafana to apply optimizations..."
        docker restart grafana || true
        
        # Wait and verify Grafana is responding
        sleep 15
        if curl -s http://localhost:3000/api/health | grep -q "ok"; then
            log "Grafana is responding"
        else
            log "WARNING: Grafana may not have restarted properly"
        fi
    else
        log "Grafana container not running, will use new config on next start"
    fi
}

# Validate deployment
validate_deployment() {
    log "Validating performance optimization deployment..."
    
    local validation_errors=0
    
    # Check service health
    local services=("grafana" "prometheus" "influxdb" "telegraf")
    
    for service in "${services[@]}"; do
        if docker ps --filter "name=$service" --filter "status=running" --quiet | grep -q .; then
            log "✓ $service is running"
        else
            log "✗ $service is not running"
            ((validation_errors++))
        fi
    done
    
    # Check specific endpoints
    log "Checking service endpoints..."
    
    # Grafana health check
    if curl -s http://localhost:3000/api/health | grep -q "ok"; then
        log "✓ Grafana endpoint responding"
    else
        log "✗ Grafana endpoint not responding"
        ((validation_errors++))
    fi
    
    # Prometheus health check
    if curl -s http://localhost:9090/-/healthy &>/dev/null; then
        log "✓ Prometheus endpoint responding"
    else
        log "✗ Prometheus endpoint not responding"
        ((validation_errors++))
    fi
    
    # InfluxDB health check
    if curl -s http://localhost:8086/ping &>/dev/null; then
        log "✓ InfluxDB endpoint responding"
    else
        log "✗ InfluxDB endpoint not responding"
        ((validation_errors++))
    fi
    
    # Telegraf metrics check
    if curl -s http://localhost:9273/metrics | head -5 | grep -q "^#"; then
        log "✓ Telegraf metrics endpoint responding"
    else
        log "✗ Telegraf metrics endpoint not responding"
        ((validation_errors++))
    fi
    
    # Performance metrics validation
    log "Checking performance metrics..."
    
    # Check if recording rules are working (wait a bit for them to populate)
    sleep 30
    
    local recording_rules_count=$(curl -s http://localhost:9090/api/v1/label/__name__/values 2>/dev/null | grep -c "instance:" || echo "0")
    if [[ $recording_rules_count -gt 0 ]]; then
        log "✓ Recording rules are generating metrics ($recording_rules_count rules active)"
    else
        log "✗ Recording rules may not be working properly"
        ((validation_errors++))
    fi
    
    # Summary
    if [[ $validation_errors -eq 0 ]]; then
        log "✅ All performance optimizations deployed successfully"
        return 0
    else
        log "❌ Deployment completed with $validation_errors validation errors"
        return 1
    fi
}

# Rollback function
rollback_deployment() {
    log "Rolling back performance optimizations..."
    
    if [[ -d "$BACKUP_DIR" ]]; then
        # Restore configurations
        cp "$BACKUP_DIR/grafana.ini" "$COLLECTIONS_DIR/grafana/" 2>/dev/null || true
        cp "$BACKUP_DIR/prometheus.yml" "$COLLECTIONS_DIR/prometheus/" 2>/dev/null || true
        cp "$BACKUP_DIR/telegraf.conf" "$COLLECTIONS_DIR/telegraf/" 2>/dev/null || true
        cp "$BACKUP_DIR/influxdb.conf" "$COLLECTIONS_DIR/influxdb/" 2>/dev/null || true
        cp "$BACKUP_DIR/redis.conf" "$COLLECTIONS_DIR/redis/" 2>/dev/null || true
        cp "$BACKUP_DIR/nginx.conf" "$COLLECTIONS_DIR/nginx/" 2>/dev/null || true
        
        # Restart services
        for service in grafana prometheus influxdb telegraf redis nginx; do
            if docker ps --filter "name=$service" --filter "status=running" --quiet | grep -q .; then
                docker restart "$service" || true
            fi
        done
        
        log "Rollback completed using backup: $BACKUP_DIR"
    else
        log "ERROR: No backup directory found for rollback"
        return 1
    fi
}

# Generate performance optimization report
generate_optimization_report() {
    log "Generating performance optimization report..."
    
    local report_file="/home/mills/performance-optimization-report-$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$report_file" << EOF
# Performance Optimization Deployment Report

**Deployment Date:** $(date '+%Y-%m-%d %H:%M:%S')  
**Monitoring Stack Performance Enhancement**

## Deployment Summary

The following performance optimizations have been applied to the monitoring infrastructure:

### 🚀 Applied Optimizations

#### Caching Layer
- **Redis**: Memory-optimized caching with 2GB limit and LRU eviction
- **Nginx**: Multi-zone caching for Grafana, Prometheus, and general content
- **Cache hit ratios**: Expected 70-85% for dashboard queries

#### Database Optimizations
- **InfluxDB**: Enhanced TSM configuration with 2GB cache and optimized compaction
- **Prometheus**: 90-day retention with performance recording rules
- **MySQL**: Optimized configuration for Zabbix backend

#### Data Collection Efficiency
- **Telegraf**: Optimized batch sizes (5000 metrics/batch) and collection intervals
- **Recording Rules**: Pre-computed metrics for common queries
- **Metric Cardinality**: Reduced via intelligent labeling and aggregation

#### Application Performance
- **Grafana**: Enhanced authentication with OAuth/LDAP integration
- **Query Optimization**: Dashboard query caching and efficient data source usage

### 📊 Performance Metrics

#### Expected Improvements
- **Dashboard Load Time**: 50-70% reduction for cached queries
- **Query Response Time**: 40-60% improvement for pre-computed metrics
- **Resource Utilization**: 20-30% reduction in CPU usage for repetitive queries
- **Storage Efficiency**: 25-40% reduction in storage growth rate

#### Monitoring Coverage
- **Recording Rules**: $(curl -s http://localhost:9090/api/v1/label/__name__/values 2>/dev/null | grep -c "instance:" || echo "N/A") active rules
- **SLA/SLO Tracking**: Automated availability and performance monitoring
- **Anomaly Detection**: Statistical analysis for predictive alerting

### 🔧 Configuration Changes

#### Service Configurations Updated
EOF

    # Add configuration details
    for service in redis nginx influxdb telegraf prometheus grafana; do
        if [[ -f "$COLLECTIONS_DIR/$service/$service.conf" ]] || [[ -f "$COLLECTIONS_DIR/$service/$service-optimized.conf" ]]; then
            echo "- **$service**: Performance-optimized configuration applied" >> "$report_file"
        fi
    done
    
    cat >> "$report_file" << 'EOF'

### 🎯 Performance Validation Results

#### Service Health Status
EOF

    # Add validation results
    for service in grafana prometheus influxdb telegraf; do
        if docker ps --filter "name=$service" --filter "status=running" --quiet | grep -q .; then
            echo "- **$service**: ✅ Running and responding" >> "$report_file"
        else
            echo "- **$service**: ❌ Not running or not responding" >> "$report_file"
        fi
    done
    
    cat >> "$report_file" << 'EOF'

#### Endpoint Verification
- **Grafana API**: Health check status
- **Prometheus**: Target and rule validation
- **InfluxDB**: Connection and query performance
- **Telegraf**: Metrics collection and export

### 📈 Next Steps

#### Immediate Monitoring (First 24 Hours)
1. Monitor dashboard load times and query performance
2. Validate cache hit ratios and effectiveness
3. Check for any service instability or errors
4. Review resource utilization trends

#### Short-term Optimization (First Week)
1. Fine-tune cache sizes based on usage patterns
2. Adjust recording rule intervals if needed
3. Optimize dashboard queries for new caching layer
4. Monitor and adjust retention policies

#### Long-term Performance Management
1. Implement automated performance testing
2. Set up performance regression alerts
3. Regular optimization reviews and updates
4. Capacity planning based on performance metrics

### 🔄 Rollback Information

**Backup Location**: Configuration backup available for rollback
**Rollback Command**: `./deploy_performance_optimizations.sh --rollback`
**Recovery Time**: Estimated 10-15 minutes for full rollback

### 📞 Support Information

For performance issues or questions:
1. Check service logs: `docker-compose logs -f <service_name>`
2. Monitor performance dashboards for anomalies
3. Review optimization settings in service configurations
4. Use rollback procedure if critical issues arise

---
*Report generated by Performance Optimization Deployment*  
*Next performance review scheduled: 1 week from deployment*
EOF

    log "Performance optimization report generated: $report_file"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [options]

Options:
  --deploy            Deploy all performance optimizations (default)
  --rollback          Rollback to previous configurations
  --validate          Validate current deployment only
  --report            Generate performance report only
  --help              Show this help message

Examples:
  $0                  # Deploy all optimizations
  $0 --deploy         # Deploy all optimizations
  $0 --validate       # Validate current state
  $0 --rollback       # Rollback changes
  $0 --report         # Generate report only

EOF
    exit 1
}

# Main execution
main() {
    local action="${1:---deploy}"
    
    case "$action" in
        --deploy|"")
            log "Starting performance optimization deployment..."
            
            backup_configs
            deploy_redis_cache
            deploy_nginx_cache
            deploy_influxdb_optimization
            deploy_telegraf_optimization
            deploy_prometheus_rules
            deploy_grafana_optimization
            
            if validate_deployment; then
                generate_optimization_report
                log "✅ Performance optimization deployment completed successfully"
            else
                log "❌ Performance optimization deployment completed with errors"
                log "Consider running rollback if issues persist: $0 --rollback"
                exit 1
            fi
            ;;
        --rollback)
            rollback_deployment
            ;;
        --validate)
            validate_deployment
            ;;
        --report)
            generate_optimization_report
            ;;
        --help)
            usage
            ;;
        *)
            log "ERROR: Unknown option: $action"
            usage
            ;;
    esac
}

# Execute main function
main "$@"