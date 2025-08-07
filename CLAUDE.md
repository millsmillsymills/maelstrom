# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Infrastructure Scale & Current Status

This is a **production-grade monitoring infrastructure** called "Maelstrom" with significant complexity:
- **39+ containerized services** across 5 Docker networks (Docker Compose v3.8)
- **1,200+ lines** in docker-compose.yml with extensive configuration
- **53+ collections directories** with service-specific configurations
- **28+ services actively monitored** with health checks and alerting
- **11+ pre-built Grafana dashboards** for comprehensive visualization
- **Multiple data storage backends**: InfluxDB, Prometheus, MySQL, Loki, Elasticsearch
- **12+ Python services** using standardized python:3.11-slim base image
- **Security-hardened**: All containers use no-new-privileges, some require privileged mode for network analysis
- **Current Health**: Stack is in degraded state with some services requiring restoration (see README.md status table)

## Project Overview

This is a comprehensive network monitoring and metrics collection stack built with Docker Compose. The system combines multiple monitoring tools to provide comprehensive network visibility and infrastructure monitoring.

## Directory Structure

The project is organized into logical directories for better maintainability:

```
/home/mills/
├── docker/                     # Docker Compose files and deployment scripts
├── networking/                 # Network monitoring and discovery tools
│   └── collections/           # Network service configurations (UniFi, SNMP, Blackbox, etc.)
├── security/                   # Security monitoring and threat detection
│   └── collections/           # Security service configurations (Wazuh, Suricata, Zeek, etc.)
├── logs/                      # Application logs and auto-recovery logs
├── reports/                   # Status reports, analysis reports, and assessments
├── backups/                   # Backup scripts and backup data
├── troubleshooting/           # Health monitoring and validation tools
├── scripts/                   # Deployment and maintenance scripts
├── docs/                      # Documentation including this CLAUDE.md
└── collections/               # Core monitoring service configurations (Grafana, Prometheus, InfluxDB, etc.)
```

## Architecture

The monitoring stack consists of several interconnected services:

**Data Collection Layer:**
- **UniFi Poller** (unpoller): Collects metrics from UniFi network equipment
- **Plex Data Collector**: Python-based collector for Plex media server metrics
- **Telegraf**: General-purpose metrics collection agent with Docker and system monitoring
- **Pi-hole**: Network-wide DNS ad blocking with built-in metrics (primary + secondary)
- **Node Exporter**: Host system metrics (CPU, memory, disk, network)
- **cAdvisor**: Docker container resource monitoring and performance metrics
- **Blackbox Exporter**: Network connectivity and service availability testing
- **MySQL Exporter**: Database performance metrics for Zabbix
- **SNMP Exporter**: Network device monitoring via SNMP protocol
- **Network Discovery**: Python-based network scanning and device discovery
- **Security Monitor**: File system and configuration security monitoring
- **Unraid Monitor**: Custom Unraid server and Docker container monitoring

**Data Storage:**
- **InfluxDB 1.8**: Time-series database for UniFi, Plex, and Telegraf metrics
- **Prometheus**: Metrics storage and scraping system with 90-day retention
- **MySQL 8.0**: Database backend for Zabbix

**Monitoring & Alerting:**
- **Zabbix Server + Web UI**: Enterprise monitoring solution
- **Grafana**: Dashboards and visualization platform with pre-installed plugins
- **Alertmanager**: Proactive alerting and notification management
- **Loki**: Log aggregation system for centralized logging
- **Promtail**: Log collection agent for shipping logs to Loki
- **Slack Notifier**: Custom webhook-based notification service

**Security & Analysis:**
- **Wazuh**: SIEM platform with Elasticsearch backend and dashboard
- **Suricata**: Network intrusion detection system with custom rules
- **Zeek**: Network analysis platform for security monitoring  
- **ntopng**: Network traffic analysis with web interface
- **Jaeger**: Distributed tracing system for performance monitoring
- **Threat Intelligence**: Advanced geopolitical threat detection and automated response
- **ML Analytics**: Machine learning pipeline for predictive analytics

**Automation & Optimization:**
- **Self-healing Infrastructure**: Automated container and service recovery
- **Data Optimizer**: Intelligent data lifecycle management
- **Resource Optimizer**: Dynamic resource allocation and optimization
- **Maelstrom Monitor**: Custom server monitoring for specific infrastructure

**Network Configuration:**
- **monitoring** (172.30.0.0/24): Primary bridge network for internal communication
- **pihole_macvlan**: MacVLAN network for Pi-hole with direct LAN access (192.168.1.250)
- **security** (172.31.0.0/24): Dedicated network for security services
- **analytics** (172.32.0.0/24): Network for ML and analytics services  
- **storage** (172.33.0.0/24): Network for data storage services
- Multiple services using host networking mode for network analysis (Suricata, Zeek, ntopng)

## Common Commands

**CRITICAL**: Always check current service status before making changes using `docker-compose ps` and the status table in README.md.

### Service Management
```bash
# Check current service status (most important command)
docker-compose ps

# View current stack health status
cat README.md | grep -A 20 "Maelstrom Status"

# Start all services (use with caution - some may need individual attention)
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service (preferred for individual service issues)
docker-compose restart <service_name>

# View service logs (essential for troubleshooting)
docker-compose logs -f <service_name>

# Follow logs for multiple services
docker-compose logs -f <service1> <service2> <service3>
```

### Configuration Management
```bash
# Edit environment variables
nano .env

# Validate docker-compose configuration
docker-compose config

# Pull latest images
docker-compose pull
```

### Data Management
```bash
# Backup InfluxDB data
docker exec influxdb influxd backup -portable /backup

# Access InfluxDB CLI
docker exec -it influxdb influx

# Access MySQL for Zabbix
docker exec -it zabbix-mysql mysql -u root -p

# Rebuild Plex Data Collector container (the only service with custom Dockerfile)
docker-compose build plex-data-collector

# Rebuild custom Python services (when requirements.txt changes)
docker-compose build ml-analytics
docker-compose build threat-intelligence
docker-compose build unraid-monitor

# Check service health and logs for Python services
docker-compose logs -f --tail=50 <service_name>

# Validate environment file
docker-compose config --quiet
```

### Development & Testing
```bash
# No automated testing framework available - manual validation only
# ALWAYS validate service functionality through logs and health checks
docker-compose logs -f <service_name>

# Service health validation script (run frequently)
/home/mills/collections/swag/validate_services.sh

# Manual testing of custom Python services
docker exec -it <service_name> python -c "import <module>; print('OK')"

# Test Prometheus alert rules (basic validation only)
docker exec prometheus promtool check rules /etc/prometheus/alert_rules.yml

# Test configuration files before deployment (essential step)
docker-compose config --quiet

# Full deployment with comprehensive validation (use for major changes)
./docker/deploy_enhanced_stack.sh
```

### Infrastructure Repair & Recovery
```bash
# Execute comprehensive infrastructure analysis and repair scripts
# These are generated by analysis tools in ./output/<timestamp>/ directories
chmod +x output/<timestamp>/stack_fix.sh
./output/<timestamp>/stack_fix.sh

# Timezone standardization across all containers
chmod +x output/<timestamp>/timezone_fix.sh  
./output/<timestamp>/timezone_fix.sh

# Validate InfluxDB authentication and database connectivity
docker exec influxdb influx -execute 'SHOW DATABASES'
curl -i -XPOST "http://localhost:8086/write?db=telegraf" --data-binary "test_metric value=1"

# Check metrics collection pipeline health
docker-compose logs -f --tail=20 telegraf unpoller plex-data-collector network-discovery

# Monitor system performance after remediation
docker stats --no-stream | head -20
```

### Security & Monitoring
```bash
# Check Wazuh agent status
docker exec wazuh-manager /var/ossec/bin/agent_control -l

# View Suricata alerts
docker exec suricata tail -f /var/log/suricata/eve.json

# Monitor Zeek logs
docker exec zeek tail -f /usr/local/zeek/logs/current/conn.log

# Check threat intelligence status
docker-compose logs -f threat-intelligence

# View security monitoring alerts
docker-compose logs -f security-monitor

# Check alert status
curl -s http://localhost:9093/api/v1/alerts | jq '.'
curl -s http://localhost:9090/api/v1/alerts | jq '.'
```

### Network Analysis
```bash
# Test network connectivity via Blackbox
curl http://localhost:9115/probe?module=http_2xx&target=http://grafana:3000

# Check SNMP monitoring
curl http://localhost:9116/snmp?module=if_mib&target=192.168.1.1

# Network discovery scan results
docker-compose logs -f network-discovery
```

### Deployment & Maintenance
```bash
# Full stack deployment with validation
./docker/deploy_enhanced_stack.sh

# SWAG SSL proxy management
/home/mills/collections/swag/validate_services.sh
/home/mills/collections/swag/auto-backup.sh
/home/mills/collections/swag/ssl-renewal.sh
/home/mills/collections/swag/monitor-swag.sh

# Generate network host entries for local access
/home/mills/collections/swag/generate-hosts-entries.sh

# Create authentication for services
/home/mills/collections/swag/create_auth.sh
```

## Key Configuration Files

**Core Infrastructure:**
- `docker-compose.yml`: Main service orchestration with 50+ services (also in `docker/` directory)
- `.env`: Environment variables and credentials for all services
- `collections/prometheus/prometheus.yml`: Prometheus scrape configuration with multi-target monitoring
- `collections/prometheus/alert_rules.yml`: Alert rules for proactive monitoring
- `collections/telegraf/telegraf.conf`: Telegraf dual-output configuration (InfluxDB + Prometheus)
- `collections/alertmanager/alertmanager.yml`: Alert routing and Slack notification settings

**Data Collection:**
- `networking/collections/unifi-poller/up.conf`: UniFi Poller connection settings
- `collections/Plex-Data-Collector-For-InfluxDB/config.ini`: Plex collector settings
- `networking/collections/blackbox/blackbox.yml`: Network connectivity test configuration
- `networking/collections/snmp/snmp.yml`: SNMP device monitoring configuration

**Security & Analysis:**
- `security/collections/wazuh/local_rules.xml`: Custom Wazuh detection rules
- `security/collections/suricata/suricata.yaml`: Network IDS configuration
- `security/collections/suricata/rules/`: Custom Suricata detection rules
- `security/collections/zeek/local.zeek`: Zeek network analysis configuration
- `security/collections/threat-intelligence/geopolitical_threats.rules`: Custom threat detection rules

**Logging:**
- `collections/loki/loki-config.yml`: Log aggregation configuration
- `collections/promtail/config.yml`: Log collection and forwarding rules

**Custom Python Services:**
- `collections/*/requirements.txt`: Dependencies for each Python service
- `collections/*/`: Individual service configurations and source code

**Deployment & Status:**
- `docker/deploy_enhanced_stack.sh`: Comprehensive deployment script with validation
- `reports/INFRASTRUCTURE_STATUS.md`: Current infrastructure status and configuration
- `reports/SWAG_DEPLOYMENT_COMPLETE.md`: SSL proxy deployment status
- `reports/*_assessment_report_*.md`: Security and performance assessment reports

**Infrastructure Analysis & Repair:**
- `./output/<timestamp>/`: Generated analysis and repair deliverables
- `./output/<timestamp>/stack_fix.sh`: Infrastructure repair and database recovery script
- `./output/<timestamp>/timezone_fix.sh`: Container timezone standardization script
- `./output/<timestamp>/findings.json`: Structured analysis data for automation
- `./output/<timestamp>/validation_report.md`: Post-execution validation results

## Service Access Points

**Core Dashboards:**
- **Grafana**: http://localhost:3000 (admin/configured_password) - 11 pre-built dashboards available
- **Prometheus**: http://localhost:9090
- **Zabbix Web**: http://localhost:8080 (Admin/zabbix default login)
- **Alertmanager**: http://localhost:9093

**Security & Analysis:**
- **Wazuh Dashboard**: http://localhost:5601 (kibanaserver/kibanaserver)
- **Jaeger Tracing**: http://localhost:16686
- **Pi-hole Primary**: http://192.168.1.250/admin
- **Pi-hole Secondary**: http://localhost:8053/admin

**Data Sources:**
- **InfluxDB**: http://localhost:8086
- **Loki**: http://localhost:3100
- **MySQL (Zabbix)**: localhost:3306

**Metrics Endpoints:**
- **Node Exporter**: http://localhost:9100/metrics
- **cAdvisor**: http://localhost:8081/metrics  
- **MySQL Exporter**: http://localhost:9104/metrics
- **Blackbox Exporter**: http://localhost:9115/metrics
- **SNMP Exporter**: http://localhost:9116/metrics
- **Telegraf**: http://localhost:9273/metrics

**Network Protocols:**
- **Zabbix Server**: Port 10051
- **Wazuh Agent**: Port 1514 (logs), 1515 (enrollment), 55000 (API)
- **Syslog**: Port 514/udp

## Network Architecture

The stack uses multiple Docker networks with static IP assignments:

1. **monitoring** (172.30.0.0/24): Primary network for core monitoring services
2. **pihole_macvlan** (192.168.1.0/24): MacVLAN for Pi-hole direct LAN access  
3. **security** (172.31.0.0/24): Dedicated network for security services
4. **analytics** (172.32.0.0/24): Network for ML and analytics workloads
5. **storage** (172.33.0.0/24): Network for data storage services

**Host Network Mode:** Suricata, Zeek, and ntopng use host networking for deep packet inspection and network analysis.

**Key IP Assignments:**
- InfluxDB: 172.30.0.2
- Grafana: 172.30.0.3  
- Prometheus: 172.30.0.5
- Pi-hole Primary: 192.168.1.250 (MacVLAN)
- Pi-hole Secondary: 172.30.0.25
- Wazuh Stack: 172.30.0.28-30
- Custom services: 172.30.0.32-38

## Data Flow

1. UniFi Poller → InfluxDB (network equipment metrics)
2. Plex Collector → InfluxDB (media server statistics)
3. Telegraf → InfluxDB + Prometheus (system and Docker metrics)
4. Node Exporter → Prometheus (host system metrics)
5. cAdvisor → Prometheus (container metrics)
6. MySQL Exporter → Prometheus (database metrics)
7. InfluxDB Exporter → Prometheus (database performance)
8. Blackbox Exporter → Prometheus (connectivity tests)
9. Prometheus → Alertmanager (alert notifications)
10. Zabbix → MySQL (enterprise monitoring data)
11. Grafana ← InfluxDB/Prometheus (comprehensive visualization)

## Development Notes

**Architecture Patterns:**
- All persistent data stored in `collections/` subdirectories with bind mounts
- Environment variables centralized in `.env` file with service-specific prefixes
- Static IP assignments for reliable inter-service communication
- Multi-network architecture for service isolation and security
- Extensive use of Python-based custom monitoring services (38 total services)
- Only Plex Data Collector uses custom Dockerfile; all other Python services use base images with runtime pip installs
- No formal testing framework - services are validated through docker-compose logs and service health monitoring

**Security Hardening:**
- All containers use `no-new-privileges:true` security option
- Resource limits (memory/CPU) applied to prevent resource exhaustion
- Tmpfs mounts for temporary storage to reduce disk I/O
- Read-only containers where possible (node-exporter, blackbox-exporter)
- Non-root users specified for security-sensitive services
- Privileged mode only for network analysis services (Suricata, Zeek, ntopng)
- Host networking mode limited to network monitoring services requiring deep packet inspection

**Data Management:**
- InfluxDB 1.8 with configurable authentication for time-series data (authentication can be disabled for recovery)
- Prometheus with 90-day retention and 50GB storage limit
- MySQL 8.0 for Zabbix with optimized configuration
- Dual storage strategy: InfluxDB for long-term, Prometheus for alerting
- **Critical**: InfluxDB authentication failures can create monitoring blackouts - use repair scripts in ./output/ for recovery

**Custom Services:**
- 15+ custom Python services for specialized monitoring
- Standardized requirements.txt and Docker build patterns
- Automatic dependency installation and service startup
- Integration with Slack for alerting across all custom services

**Development Workflow:**
- Python services use runtime pip install from requirements.txt (no pre-built images)
- Services restart automatically via `restart: unless-stopped`
- Configuration changes require container restart: `docker-compose restart <service>`
- Environment variables are managed centrally in `.env` file
- All services mount their source code as volumes for easy development
- **No formal testing framework**: Services validated through logs and health monitoring only
- **No CI/CD pipeline**: Manual deployment via `./docker/deploy_enhanced_stack.sh`
- **No code quality tools**: No linting, formatting, or static analysis configured
- **GitHub Integration**: Repository has automated backup and status reporting workflows

**Monitoring Coverage:**
- Network: UniFi equipment, SNMP devices, connectivity tests, traffic analysis
- Security: SIEM, IDS/IPS, malware detection, threat intelligence
- Systems: Host metrics, container metrics, application performance
- Applications: Plex media server, Unraid infrastructure, custom services

## Troubleshooting

**Service Issues:**
- Check service logs: `docker-compose logs -f <service>`
- Verify container status: `docker-compose ps`
- Check resource usage: `docker stats`
- Restart individual services: `docker-compose restart <service>`
- Validate docker-compose configuration: `docker-compose config --quiet`
- Check service health: `/home/mills/collections/swag/validate_services.sh`

**Network Connectivity:**
- Test inter-service communication: `docker exec <container> ping <target>`
- Verify network configuration: `docker network ls` and `docker network inspect monitoring`
- Check static IP assignments match docker-compose.yml
- Ensure MacVLAN interface (ens2) is available for Pi-hole

**Configuration:**
- Validate docker-compose syntax: `docker-compose config`
- Ensure `.env` file contains all required variables
- Check file permissions in `collections/` directories
- Verify UniFi controller accessibility from Docker network

**Data & Storage:**
- Validate InfluxDB database creation and permissions
- Check Prometheus storage: `du -sh collections/prometheus_data/`
- Monitor MySQL performance: `docker exec zabbix-mysql mysqladmin status`
- Verify log aggregation in Loki: check retention and storage usage

**Environment Configuration:**
- Ensure `.env` file contains all required variables (see existing .env as template)
- Critical variables: INFLUXDB_*, GRAFANA_*, UNIFI_*, SLACK_WEBHOOK_URL
- TZ setting affects all container timestamps (currently America/Los_Angeles)
- MacVLAN network requires `ens2` interface to be available for Pi-hole

**Security Services:**
- Wazuh: Check agent enrollment and log ingestion
- Suricata: Verify network interface and rule updates
- Threat Intelligence: Monitor detection accuracy and alert volume
- Check privileged container permissions for network analysis services

**Performance:**
- Monitor container resource limits and usage
- Check for memory leaks in custom Python services
- Verify tmpfs mount usage and cleanup
- Review alert frequency and tune thresholds to reduce noise

**Critical Infrastructure Failures:**
- **InfluxDB Authentication Crisis**: Use `./output/<timestamp>/stack_fix.sh` for authentication system recovery
- **Data Collection Blackouts**: Restart services in sequence: telegraf, unpoller, plex-data-collector, network-discovery
- **Timezone Inconsistency**: Execute `./output/<timestamp>/timezone_fix.sh` for standardization across all containers
- **Wazuh SIEM Recovery**: Check dashboard API status and restart wazuh-manager, wazuh-dashboard services
- **System Resource Exhaustion**: Monitor load averages and implement resource optimization via generated scripts

## Alerting & Monitoring Patterns

**Alert Thresholds (Prometheus):**
- CPU usage: >80% for 2+ minutes triggers warning
- Memory usage: >85% for 2+ minutes triggers warning  
- Disk usage: >85% for 2+ minutes triggers warning
- Container down: Immediate critical alert

**Alert Routing:**
- Critical alerts → Slack via slack-notifier service (port 5001)
- Warning alerts → Standard webhook notifications
- Alert grouping: 10s wait, 1h repeat interval
- Slack webhook: Configured via SLACK_WEBHOOK_URL environment variable

**Operational Best Practices:**
- Check alert status regularly: `curl http://localhost:9093/api/v1/alerts`
- Monitor service health via dashboard: 28 services actively monitored
- Use deployment script for major changes: `./deploy_enhanced_stack.sh`
- Regular backups via SWAG auto-backup: `/home/mills/collections/swag/auto-backup.sh`
- Network validation: Ensure ens2 interface available for Pi-hole MacVLAN

## System Requirements & Dependencies

**Host System Prerequisites:**
- Docker Engine with Docker Compose v3.8+ support
- Network interface `ens2` available for MacVLAN (Pi-hole direct LAN access)
- Sufficient disk space: ~50GB for Prometheus data, plus InfluxDB/MySQL storage
- Memory: Minimum 8GB RAM recommended for full stack operation
- Linux host with kernel support for privileged containers (network analysis services)

**Critical Image Versions:**
- InfluxDB: 1.8 (time-series database for UniFi/Plex/Telegraf metrics)
- MySQL: 8.0 (Zabbix backend database)
- Telegraf: 1.27 (metrics collection agent)
- Python: 3.11-slim (base for 12 custom monitoring services)
- All other services use `:latest` tags for automatic updates

**Network Dependencies:**
- UniFi Controller accessible at 192.168.1.1 (configured in .env)
- Slack webhook URL for alerting notifications
- Internet access for pulling Docker images and threat intelligence updates
- Local LAN access required for SNMP monitoring and network discovery

## Development Standards & Patterns

**Current State (Production Environment):**
- **No unit testing**: Custom Python services lack automated test coverage
- **Manual deployment**: Deployment via `./docker/deploy_enhanced_stack.sh` with comprehensive validation
- **Manual validation**: Service health verified through logs and runtime monitoring
- **No code quality enforcement**: No linting, formatting, or static analysis tools
- **GitHub CI/CD**: Automated workflows for linting, validation, and deployment to production
- **Backup Automation**: Daily automated backups of configurations, data, and certificates

**Custom Service Development Workflow:**
```bash
# 1. Modify Python service code in collections/<service>/
# 2. Update requirements.txt if adding dependencies
# 3. Restart service to apply changes
docker-compose restart <service_name>

# 4. Monitor logs for issues
docker-compose logs -f <service_name>

# 5. Validate service health
/home/mills/collections/swag/validate_services.sh
```

**Adding New Custom Services:**
- Follow existing patterns in `collections/` subdirectories
- Create `requirements.txt` with Python dependencies
- Use python:3.11-slim base image with runtime pip install
- Add to docker-compose.yml with appropriate network and resource limits
- Include security hardening: `no-new-privileges:true`, memory limits
- Mount source code as volume for development iteration

**Configuration Management:**
- All environment variables centralized in `.env` file
- Service-specific configuration in `collections/<service>/` directories
- Static IP assignments for reliable inter-service communication
- Restart required for configuration changes: `docker-compose restart <service>`

## Working with this Infrastructure

**Before Making Changes:**
1. **Always check current status**: `docker-compose ps` and README.md status table
2. **Review recent logs**: Check `logs/` directory for auto-recovery events
3. **Backup if needed**: The infrastructure has automated daily backups, but manual backups available
4. **Understand service dependencies**: Many services are interconnected - check docker-compose.yml networks

**Service Recovery Patterns:**
- **Database services** (InfluxDB, MySQL): Critical for data retention - use repair scripts in `./output/*/`
- **Monitoring services** (Prometheus, Grafana): Check data source connectivity after restart  
- **Security services** (Wazuh, Suricata): May need rule reloading after configuration changes
- **Custom Python services**: Usually self-recover, check logs for import/dependency errors

**Deployment Safety:**
- **Test mode**: Use `docker-compose config --quiet` to validate before applying
- **Staged deployment**: Restart individual services rather than entire stack when possible
- **Rollback plan**: Keep `docker-compose.yml.backup` and use `./backups/` for configuration restoration
- **Health validation**: Always run `/home/mills/collections/swag/validate_services.sh` after changes