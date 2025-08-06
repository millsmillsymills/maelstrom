# 🌊 Maelstrom Monitoring Stack

[![Lint and Validate](https://github.com/millsmillsymills/maelstrom/workflows/Lint%20and%20Validate%20Infrastructure/badge.svg)](https://github.com/millsmillsymills/maelstrom/actions)
[![Deploy Status](https://github.com/millsmillsymills/maelstrom/workflows/Deploy%20to%20Maelstrom/badge.svg)](https://github.com/millsmillsymills/maelstrom/actions)

Production-grade monitoring and security infrastructure built with Docker Compose. Comprehensive network visibility, security monitoring, and infrastructure observability for enterprise environments.

## 🟢 Maelstrom Status

| Key Metric       | Value             |
|------------------|------------------|
| Stack Health     | 🟡 Degraded |
| Critical Alerts  | ✅ None |
| Failing Services | 1 |
| Last Check       | 2025-08-06 22:27 UTC |

**Failing Services:**
- mysql-exporter (restarting)

**Failing Services:**
- wazuh-manager (restarting)

**Failing Services:**
- wazuh-manager (restarting)

**Failing Services:**
- wazuh-manager (restarting)

**Failing Services:**
- wazuh-manager (restarting)

**Failing Services:**
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

**Failing Services:**
- wazuh-manager (restarting)
- zabbix-web (unhealthy)
- prometheus (restarting)

<!-- STATUS-BEGIN -->
| Key Metric       | Value             |
|------------------|------------------|
| Stack Health     | 🟡 Degraded |
| Critical Alerts  | ✅ None |
| Failing Services | 1 |
| Last Check       | 2025-08-06 22:27 UTC |

**Failing Services:**
- mysql-exporter (restarting)

**Failing Services:**
- mysql-exporter (restarting)
<!-- STATUS-END -->

## 🏗️ Architecture Overview

The Maelstrom stack consists of **39 containerized services** organized across **5 Docker networks**:

### Core Monitoring (Base Stack)
- **InfluxDB 1.8** - Time-series database for metrics storage
- **Grafana** - Dashboards and visualization (with 11+ pre-built dashboards)
- **Prometheus** - Metrics collection and alerting engine
- **Alertmanager** - Alert routing and notification management
- **Telegraf** - System and Docker metrics collection
- **Node Exporter** - Host system metrics
- **cAdvisor** - Container resource monitoring

### Data Collection & Export
- **UniFi Poller** - Network equipment metrics from UniFi Controller
- **Plex Data Collector** - Media server statistics and usage
- **Blackbox Exporter** - Network connectivity and uptime monitoring
- **SNMP Exporter** - Network device monitoring via SNMP
- **MySQL Exporter** - Database performance metrics

### Security Stack (Profile: `security-stack`)
- **Wazuh SIEM** - Complete security information and event management
- **Suricata** - Network intrusion detection system
- **Zeek** - Network analysis and traffic inspection
- **ntopng** - Network traffic analysis and monitoring
- **Threat Intelligence** - Automated threat detection and response

### ML Analytics (Profile: `ml-analytics`) 
- **ML Analytics Engine** - Predictive analytics for infrastructure
- **Data Optimizer** - Intelligent data lifecycle management
- **Resource Optimizer** - Dynamic resource allocation

### Enterprise Monitoring
- **Zabbix Server** - Enterprise-grade monitoring platform
- **Pi-hole** - Network-wide DNS filtering (Primary + Secondary)
- **Loki + Promtail** - Centralized log aggregation
- **Jaeger** - Distributed tracing system

## 🚀 Quick Start

### Deploy Base Stack
```bash
# Clone repository
git clone https://github.com/millsmillsymills/maelstrom.git
cd maelstrom

# Deploy core monitoring services
./deploy_stack.sh --base-only
```

### Deploy with Profiles
```bash
# Deploy with security monitoring
./deploy_stack.sh security-stack

# Deploy everything
./deploy_stack.sh --all-profiles

# Deploy with high availability
./deploy_stack.sh --compatibility ml-analytics security-stack
```

### Validation & Health Checks
```bash
# Comprehensive validation
./validate_stack.sh

# Quick health check
./validate_stack.sh --health-checks-only --quick

# Security scan
./validate_stack.sh --security-only
```

## 📊 Service Access Points

### Core Dashboards
- **Grafana**: http://localhost:3000 (admin/configured_password)
- **Prometheus**: http://localhost:9090
- **Zabbix Web**: http://localhost:8080
- **Alertmanager**: http://localhost:9093

### Security Monitoring  
- **Wazuh Dashboard**: http://localhost:5601 (kibanaserver/kibanaserver)
- **Pi-hole Primary**: http://192.168.1.250/admin
- **ntopng**: http://localhost:3001

### Data Sources
- **InfluxDB**: http://localhost:8086
- **Loki**: http://localhost:3100

## 🛡️ Security Features

### Infrastructure Hardening
- All containers use `no-new-privileges:true`
- Resource limits prevent resource exhaustion
- Read-only containers where possible
- Non-root users for security-sensitive services
- Network segmentation with dedicated subnets

### Vulnerability Management
- **Trivy integration** for container image scanning  
- **Automated CVE scanning** in CI/CD pipeline
- **Security monitoring** via Wazuh SIEM
- **Network intrusion detection** with Suricata/Zeek

### Backup & Recovery
- **Automated backups** of all persistent data
- **InfluxDB portable backups** with compression
- **Docker volume backups** with integrity verification
- **Configurable retention** policies (7-day default)

## 🔧 Operations

### Service Management
```bash
# Start all services
docker-compose up -d

# Restart specific service  
docker-compose restart <service_name>

# View service logs
docker-compose logs -f <service_name>

# Check service health
./validate_stack.sh --health-checks-only
```

### Backup Operations
```bash
# Manual backup
./scripts/backups/backup_influxdb.sh
./scripts/backups/backup_volume.sh prometheus_data

# Setup automated backups
./scripts/backups/setup_backup_cron.sh

# Backup rotation
./scripts/backups/rotate_backups.sh
```

### Security Operations  
```bash
# Run vulnerability scan
./scripts/scan_images.sh

# Check security monitoring
docker-compose logs -f security-monitor threat-intelligence

# View threat intelligence alerts
docker-compose logs -f geopolitical-threat-detector
```

## 📁 Project Structure

```
/home/mills/
├── base.yml                    # Core monitoring services
├── prod.yml                   # Heavy services with profiles
├── docker-compose.yml         # Legacy monolithic config
├── deploy_stack.sh            # Profile-aware deployment
├── validate_stack.sh          # Comprehensive validation
├── collections/               # Service configurations
│   ├── grafana/              # Grafana dashboards & plugins
│   ├── prometheus/           # Prometheus config & rules
│   ├── influxdb/             # InfluxDB data
│   ├── alertmanager/         # Alert routing config
│   └── [38 other services]
├── scripts/
│   ├── scan_images.sh        # Vulnerability scanning
│   ├── backups/              # Backup automation
│   └── update_readme_status.py
├── networking/collections/    # Network monitoring configs
├── security/collections/     # Security service configs
└── .github/workflows/        # CI/CD automation
```

## 🌐 Network Architecture

### Networks
- **monitoring** (172.30.0.0/24) - Primary bridge network
- **pihole_macvlan** (192.168.1.0/24) - Direct LAN access for Pi-hole
- **security** (172.31.0.0/24) - Dedicated security services
- **analytics** (172.32.0.0/24) - ML and analytics workloads
- **storage** (172.33.0.0/24) - Data storage services

### Service Discovery
Static IP assignments ensure reliable inter-service communication:
- InfluxDB: 172.30.0.2
- Grafana: 172.30.0.3
- Prometheus: 172.30.0.5
- Pi-hole: 192.168.1.250 (MacVLAN)

## 📈 Monitoring Coverage

- **Network**: UniFi equipment, SNMP devices, connectivity tests
- **Security**: SIEM, IDS/IPS, malware detection, threat intelligence  
- **Systems**: Host metrics, container metrics, application performance
- **Applications**: Plex media server, Unraid infrastructure
- **Infrastructure**: Docker containers, resource utilization, health checks

## 🚨 Alerting & Notifications

### Alert Thresholds
- CPU usage: >80% for 2+ minutes (warning)
- Memory usage: >85% for 2+ minutes (warning)
- Disk usage: >85% for 2+ minutes (warning)
- Container down: Immediate critical alert

### Notification Channels
- **Slack integration** via webhook notifications
- **GitHub Issues** for deployment failures
- **Email alerts** via Alertmanager SMTP relay

## 🔄 CI/CD Pipeline

### Automated Validation
- **Dockerfile linting** with Hadolint  
- **YAML validation** with yamllint
- **Shell script linting** with shellcheck
- **Docker Compose validation** with syntax checking
- **Security scanning** with Trivy
- **Infrastructure testing** with pytest

### Deployment Automation
- **Health-aware deployment** - only deploys if validation passes
- **Automatic rollback** on deployment failure
- **Status updates** in README.md
- **GitHub Issue creation** for failures

## 🏷️ Service Profiles

Deploy only what you need with service profiles:

| Profile | Services | Use Case |
|---------|----------|----------|
| `base` | Core monitoring (28 services) | Essential infrastructure monitoring |
| `ml-analytics` | ML pipeline (3 services) | Predictive analytics & optimization |
| `wazuh-stack` | SIEM platform (3 services) | Enterprise security monitoring |
| `security-stack` | Network security (6 services) | IDS/IPS, threat detection |
| `analytics-stack` | Advanced analytics (5 services) | Performance tracing, self-healing |

## 📊 System Requirements

### Minimum Requirements
- **RAM**: 8GB (16GB recommended for full stack)
- **Disk**: 100GB SSD (for data retention and logs)
- **CPU**: 4 cores (8+ cores recommended for ML analytics)
- **Network**: 1Gbps interface for traffic analysis

### Dependencies
- Docker Engine 20.10+
- Docker Compose v3.8+
- Linux kernel 5.0+ (for privileged network services)
- Network interface available for MacVLAN (Pi-hole direct access)

## 🤝 Contributing

This is a single-admin production system with no formal contribution process. However, improvements and optimizations are welcome:

1. Fork the repository
2. Create feature branch
3. Test changes with `./validate_stack.sh`
4. Submit pull request with detailed testing notes

## 📜 License

MIT License - See LICENSE file for details.

## 🆘 Support & Troubleshooting

### Common Issues
- **Health check failures**: Run `./validate_stack.sh --fix-issues`
- **Network connectivity**: Verify MacVLAN interface availability
- **Resource constraints**: Check `docker stats` and adjust limits
- **Security alerts**: Review Wazuh dashboard and threat intelligence logs

### Logs & Debugging
- **Service logs**: `docker-compose logs -f <service>`
- **Validation logs**: `./validate_stack.sh` generates detailed reports
- **Backup logs**: Located in `/home/mills/logs/`
- **Security logs**: Wazuh dashboard and `/var/log/` mounts

### Emergency Recovery
```bash
# Stop all services
./deploy_stack.sh --down

# Restore from backup
./scripts/backups/restore_influxdb.sh <backup_path>

# Redeploy with validation
./deploy_stack.sh --all-profiles
./validate_stack.sh --fix-issues
```

---

**Maelstrom** - *Where monitoring meets the storm* 🌊

Built with ❤️ for production environments that demand reliability, security, and comprehensive observability.