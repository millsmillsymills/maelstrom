#!/usr/bin/env python3
"""
Resource Utilization Monitor and Optimizer
Automatically monitors system resources and optimizes container performance
"""

import docker
import psutil
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import requests
from dataclasses import dataclass

# Import secrets helper
try:
    import sys
    sys.path.append('/app')
    from collections.ml_analytics.secrets_helper import read_secret, get_database_url, get_slack_webhook
except ImportError:
    # Fallback for development
    import os
    def read_secret(name, fallback=None, required=True):
        return os.environ.get(fallback, fallback)
    def get_database_url(db_type="influxdb"):
        return "http://admin:password@influxdb:8086"
    def get_slack_webhook():
        return os.environ.get("SLACK_WEBHOOK_URL")

# Configuration
MONITORING_INTERVAL = 30  # seconds
OPTIMIZATION_INTERVAL = 300  # 5 minutes
RESOURCE_THRESHOLDS = {
    'cpu_warning': 80.0,
    'cpu_critical': 90.0,
    'memory_warning': 85.0,
    'memory_critical': 95.0,
    'disk_warning': 80.0,
    'disk_critical': 90.0,
    'network_warning': 100_000_000,  # 100MB/s
    'network_critical': 500_000_000   # 500MB/s
}

INFLUXDB_HOST = "influxdb"
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = "resource_monitoring"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ResourceMetrics:
    """Resource metrics data class"""
    timestamp: datetime
    host_cpu_percent: float
    host_memory_percent: float
    host_disk_percent: float
    host_network_bytes_sent: int
    host_network_bytes_recv: int
    containers: Dict[str, Dict]
    recommendations: List[str]

class ResourceOptimizer:
    """Advanced resource monitoring and optimization system"""
    
    def __init__(self):
        self.docker_client = docker.from_env()
        self.influxdb_client = None
        self.setup_influxdb()
        self.resource_history = []
        self.optimization_actions = []
        self.alerts_sent = set()
        
    def setup_influxdb(self):
        """Setup InfluxDB connection for metrics storage"""
        try:
            from influxdb import InfluxDBClient
            
            # Get credentials from secrets
            username = "admin"
            password = read_secret("influxdb_admin_password", "INFLUXDB_ADMIN_PASSWORD", required=False)
            
            if password:
                self.influxdb_client = InfluxDBClient(
                    host=INFLUXDB_HOST,
                    port=INFLUXDB_PORT,
                    username=username,
                    password=password,
                    database=INFLUXDB_DATABASE
                )
            else:
                # Unauthenticated mode
                self.influxdb_client = InfluxDBClient(
                    host=INFLUXDB_HOST,
                    port=INFLUXDB_PORT,
                    database=INFLUXDB_DATABASE
                )
            
            # Create database if it doesn't exist
            databases = self.influxdb_client.get_list_database()
            if not any(db['name'] == INFLUXDB_DATABASE for db in databases):
                self.influxdb_client.create_database(INFLUXDB_DATABASE)
                logger.info(f"Created InfluxDB database: {INFLUXDB_DATABASE}")
                
            logger.info("InfluxDB connection established for resource monitoring")
                
        except Exception as e:
            logger.error(f"Failed to setup InfluxDB: {e}")
            self.influxdb_client = None

    def collect_host_metrics(self) -> Dict:
        """Collect comprehensive host system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            network_io = psutil.net_io_counters()
            network_connections = len(psutil.net_connections())
            
            # Process metrics
            process_count = len(psutil.pids())
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency_mhz': cpu_freq.current if cpu_freq else 0,
                    'load_avg_1m': load_avg[0],
                    'load_avg_5m': load_avg[1],
                    'load_avg_15m': load_avg[2]
                },
                'memory': {
                    'total_bytes': memory.total,
                    'available_bytes': memory.available,
                    'used_bytes': memory.used,
                    'percent': memory.percent,
                    'swap_total': swap.total,
                    'swap_used': swap.used,
                    'swap_percent': swap.percent
                },
                'disk': {
                    'total_bytes': disk_usage.total,
                    'used_bytes': disk_usage.used,
                    'free_bytes': disk_usage.free,
                    'percent': (disk_usage.used / disk_usage.total) * 100,
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0,
                    'read_count': disk_io.read_count if disk_io else 0,
                    'write_count': disk_io.write_count if disk_io else 0
                },
                'network': {
                    'bytes_sent': network_io.bytes_sent,
                    'bytes_recv': network_io.bytes_recv,
                    'packets_sent': network_io.packets_sent,
                    'packets_recv': network_io.packets_recv,
                    'connections': network_connections
                },
                'system': {
                    'process_count': process_count,
                    'boot_time': psutil.boot_time(),
                    'users': len(psutil.users())
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting host metrics: {e}")
            return {}

    def collect_container_metrics(self) -> Dict[str, Dict]:
        """Collect detailed metrics for all Docker containers"""
        container_metrics = {}
        
        try:
            containers = self.docker_client.containers.list(all=True)
            
            for container in containers:
                try:
                    stats = container.stats(stream=False)
                    
                    # Calculate CPU percentage
                    cpu_percent = 0.0
                    if 'cpu_usage' in stats.get('cpu_stats', {}):
                        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                                   stats['precpu_stats']['cpu_usage']['total_usage']
                        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                                      stats['precpu_stats']['system_cpu_usage']
                        if system_delta > 0:
                            cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
                    
                    # Calculate memory metrics
                    memory_stats = stats.get('memory_stats', {})
                    memory_usage = memory_stats.get('usage', 0)
                    memory_limit = memory_stats.get('limit', 0)
                    memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0
                    
                    # Network I/O
                    network_stats = stats.get('networks', {})
                    network_rx = sum(net.get('rx_bytes', 0) for net in network_stats.values())
                    network_tx = sum(net.get('tx_bytes', 0) for net in network_stats.values())
                    
                    # Block I/O
                    blkio_stats = stats.get('blkio_stats', {})
                    blkio_read = sum(item.get('value', 0) for item in blkio_stats.get('io_service_bytes_recursive', []) if item.get('op') == 'Read')
                    blkio_write = sum(item.get('value', 0) for item in blkio_stats.get('io_service_bytes_recursive', []) if item.get('op') == 'Write')
                    
                    container_metrics[container.name] = {
                        'id': container.id[:12],
                        'status': container.status,
                        'image': container.image.tags[0] if container.image.tags else 'unknown',
                        'created': container.attrs['Created'],
                        'cpu_percent': round(cpu_percent, 2),
                        'memory_usage_bytes': memory_usage,
                        'memory_limit_bytes': memory_limit,
                        'memory_percent': round(memory_percent, 2),
                        'network_rx_bytes': network_rx,
                        'network_tx_bytes': network_tx,
                        'block_read_bytes': blkio_read,
                        'block_write_bytes': blkio_write,
                        'restart_count': container.attrs['RestartCount'],
                        'health_status': self.get_container_health(container)
                    }
                    
                except Exception as e:
                    logger.warning(f"Error collecting metrics for container {container.name}: {e}")
                    container_metrics[container.name] = {
                        'status': 'error',
                        'error': str(e)
                    }
                    
        except Exception as e:
            logger.error(f"Error collecting container metrics: {e}")
            
        return container_metrics

    def get_container_health(self, container) -> str:
        """Get container health status"""
        try:
            health = container.attrs.get('State', {}).get('Health', {})
            return health.get('Status', 'unknown')
        except Exception:
            return 'unknown'

    def analyze_resource_usage(self, host_metrics: Dict, container_metrics: Dict) -> Tuple[List[str], List[str]]:
        """Analyze resource usage and generate recommendations"""
        issues = []
        recommendations = []
        
        # Analyze host resources
        if host_metrics:
            cpu_percent = host_metrics.get('cpu', {}).get('percent', 0)
            memory_percent = host_metrics.get('memory', {}).get('percent', 0)
            disk_percent = host_metrics.get('disk', {}).get('percent', 0)
            
            # CPU analysis
            if cpu_percent >= RESOURCE_THRESHOLDS['cpu_critical']:
                issues.append(f"CRITICAL: Host CPU usage at {cpu_percent:.1f}%")
                recommendations.append("Consider scaling containers or optimizing CPU-intensive services")
            elif cpu_percent >= RESOURCE_THRESHOLDS['cpu_warning']:
                issues.append(f"WARNING: Host CPU usage at {cpu_percent:.1f}%")
                recommendations.append("Monitor CPU usage trends and prepare for scaling")
            
            # Memory analysis
            if memory_percent >= RESOURCE_THRESHOLDS['memory_critical']:
                issues.append(f"CRITICAL: Host memory usage at {memory_percent:.1f}%")
                recommendations.append("Restart memory-intensive containers or add more RAM")
            elif memory_percent >= RESOURCE_THRESHOLDS['memory_warning']:
                issues.append(f"WARNING: Host memory usage at {memory_percent:.1f}%")
                recommendations.append("Review container memory limits and usage patterns")
            
            # Disk analysis
            if disk_percent >= RESOURCE_THRESHOLDS['disk_critical']:
                issues.append(f"CRITICAL: Disk usage at {disk_percent:.1f}%")
                recommendations.append("Clean up old logs, images, and unused volumes immediately")
            elif disk_percent >= RESOURCE_THRESHOLDS['disk_warning']:
                issues.append(f"WARNING: Disk usage at {disk_percent:.1f}%")
                recommendations.append("Schedule disk cleanup and review data retention policies")
        
        # Analyze container resources
        high_cpu_containers = []
        high_memory_containers = []
        unhealthy_containers = []
        
        for name, metrics in container_metrics.items():
            if metrics.get('status') == 'error':
                continue
                
            cpu_percent = metrics.get('cpu_percent', 0)
            memory_percent = metrics.get('memory_percent', 0)
            health_status = metrics.get('health_status', 'unknown')
            
            # High CPU containers
            if cpu_percent > 80:
                high_cpu_containers.append((name, cpu_percent))
            
            # High memory containers
            if memory_percent > 85:
                high_memory_containers.append((name, memory_percent))
            
            # Unhealthy containers
            if health_status in ['unhealthy', 'starting'] or metrics.get('status') not in ['running']:
                unhealthy_containers.append(name)
        
        # Generate container-specific recommendations
        if high_cpu_containers:
            issues.append(f"High CPU containers: {', '.join([f'{name} ({cpu:.1f}%)' for name, cpu in high_cpu_containers])}")
            recommendations.append("Review and optimize high CPU containers or increase resource limits")
        
        if high_memory_containers:
            issues.append(f"High memory containers: {', '.join([f'{name} ({mem:.1f}%)' for name, mem in high_memory_containers])}")
            recommendations.append("Consider restarting high memory containers or increasing memory limits")
        
        if unhealthy_containers:
            issues.append(f"Unhealthy containers: {', '.join(unhealthy_containers)}")
            recommendations.append("Investigate and restart unhealthy containers")
        
        return issues, recommendations

    def apply_optimizations(self, recommendations: List[str], host_metrics: Dict, container_metrics: Dict):
        """Apply automated optimizations based on analysis"""
        optimizations_applied = []
        
        try:
            # Automatic Docker cleanup if disk space is critical
            disk_percent = host_metrics.get('disk', {}).get('percent', 0)
            if disk_percent >= RESOURCE_THRESHOLDS['disk_critical']:
                logger.info("Applying automatic Docker cleanup due to critical disk usage")
                
                # Prune unused containers, images, and networks
                pruned_containers = self.docker_client.containers.prune()
                pruned_images = self.docker_client.images.prune()
                pruned_networks = self.docker_client.networks.prune()
                pruned_volumes = self.docker_client.volumes.prune()
                
                optimizations_applied.append(f"Docker cleanup: containers={len(pruned_containers.get('ContainersDeleted', []))}, "
                                           f"images={len(pruned_images.get('ImagesDeleted', []))}, "
                                           f"networks={len(pruned_networks.get('NetworksDeleted', []))}, "
                                           f"volumes={len(pruned_volumes.get('VolumesDeleted', []))}")
            
            # Restart unhealthy containers
            unhealthy_containers = []
            for name, metrics in container_metrics.items():
                if (metrics.get('health_status') == 'unhealthy' or 
                    metrics.get('status') not in ['running'] and 
                    metrics.get('status') != 'exited'):
                    
                    try:
                        container = self.docker_client.containers.get(name)
                        if container.status != 'running':
                            container.restart()
                            unhealthy_containers.append(name)
                            logger.info(f"Restarted unhealthy container: {name}")
                    except Exception as e:
                        logger.error(f"Failed to restart container {name}: {e}")
            
            if unhealthy_containers:
                optimizations_applied.append(f"Restarted containers: {', '.join(unhealthy_containers)}")
            
            # Memory optimization: restart high-memory containers if critical
            memory_percent = host_metrics.get('memory', {}).get('percent', 0)
            if memory_percent >= RESOURCE_THRESHOLDS['memory_critical']:
                high_memory_containers = [(name, metrics) for name, metrics in container_metrics.items() 
                                        if metrics.get('memory_percent', 0) > 90]
                
                # Restart the highest memory consumer (if not critical service)
                if high_memory_containers:
                    high_memory_containers.sort(key=lambda x: x[1].get('memory_percent', 0), reverse=True)
                    container_name = high_memory_containers[0][0]
                    
                    # Don't restart critical infrastructure services
                    critical_services = ['influxdb', 'grafana', 'prometheus', 'mysql', 'vault']
                    if not any(service in container_name.lower() for service in critical_services):
                        try:
                            container = self.docker_client.containers.get(container_name)
                            container.restart()
                            optimizations_applied.append(f"Restarted high-memory container: {container_name}")
                            logger.info(f"Restarted high-memory container: {container_name}")
                        except Exception as e:
                            logger.error(f"Failed to restart high-memory container {container_name}: {e}")
            
            if optimizations_applied:
                self.optimization_actions.extend(optimizations_applied)
                logger.info(f"Applied optimizations: {'; '.join(optimizations_applied)}")
            
            return optimizations_applied
            
        except Exception as e:
            logger.error(f"Error applying optimizations: {e}")
            return []

    def send_alerts(self, issues: List[str], recommendations: List[str], host_metrics: Dict):
        """Send alerts for critical resource issues"""
        try:
            webhook_url = get_slack_webhook()
            if not webhook_url or not issues:
                return
            
            # Only send alerts for new issues or critical issues
            critical_issues = [issue for issue in issues if 'CRITICAL' in issue]
            new_issues = [issue for issue in issues if issue not in self.alerts_sent]
            
            alerts_to_send = list(set(critical_issues + new_issues))
            
            if not alerts_to_send:
                return
            
            # Create alert message
            severity = "🚨 CRITICAL" if critical_issues else "⚠️ WARNING"
            message = f"{severity} Resource Alert - {len(alerts_to_send)} issues detected"
            
            # Prepare attachment fields
            attachment_fields = []
            
            # Add system overview
            if host_metrics:
                cpu_percent = host_metrics.get('cpu', {}).get('percent', 0)
                memory_percent = host_metrics.get('memory', {}).get('percent', 0)
                disk_percent = host_metrics.get('disk', {}).get('percent', 0)
                
                attachment_fields.append({
                    'title': 'System Resources',
                    'value': f'CPU: {cpu_percent:.1f}% | Memory: {memory_percent:.1f}% | Disk: {disk_percent:.1f}%',
                    'short': False
                })
            
            # Add issues
            for issue in alerts_to_send[:5]:  # Limit to 5 issues
                attachment_fields.append({
                    'title': 'Issue',
                    'value': issue,
                    'short': False
                })
            
            # Add top recommendations
            if recommendations:
                attachment_fields.append({
                    'title': 'Recommendations',
                    'value': '\n'.join(f'• {rec}' for rec in recommendations[:3]),
                    'short': False
                })
            
            payload = {
                'text': message,
                'attachments': [{
                    'color': 'danger' if critical_issues else 'warning',
                    'fields': attachment_fields,
                    'footer': 'Maelstrom Resource Monitor',
                    'ts': int(time.time())
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Sent resource alert with {len(alerts_to_send)} issues")
                self.alerts_sent.update(alerts_to_send)
            else:
                logger.error(f"Failed to send alert: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending alerts: {e}")

    def store_metrics(self, metrics: ResourceMetrics):
        """Store metrics in InfluxDB"""
        if not self.influxdb_client:
            return
            
        try:
            points = []
            
            # Host metrics point
            host_point = {
                'measurement': 'host_resources',
                'tags': {
                    'host': 'maelstrom'
                },
                'fields': {
                    'cpu_percent': metrics.host_cpu_percent,
                    'memory_percent': metrics.host_memory_percent,
                    'disk_percent': metrics.host_disk_percent,
                    'network_bytes_sent': metrics.host_network_bytes_sent,
                    'network_bytes_recv': metrics.host_network_bytes_recv,
                    'container_count': len(metrics.containers),
                    'recommendations_count': len(metrics.recommendations)
                },
                'time': metrics.timestamp
            }
            points.append(host_point)
            
            # Container metrics points
            for container_name, container_data in metrics.containers.items():
                if container_data.get('status') == 'error':
                    continue
                    
                container_point = {
                    'measurement': 'container_resources',
                    'tags': {
                        'container_name': container_name,
                        'container_id': container_data.get('id', 'unknown'),
                        'image': container_data.get('image', 'unknown'),
                        'status': container_data.get('status', 'unknown')
                    },
                    'fields': {
                        'cpu_percent': float(container_data.get('cpu_percent', 0)),
                        'memory_usage_bytes': int(container_data.get('memory_usage_bytes', 0)),
                        'memory_percent': float(container_data.get('memory_percent', 0)),
                        'network_rx_bytes': int(container_data.get('network_rx_bytes', 0)),
                        'network_tx_bytes': int(container_data.get('network_tx_bytes', 0)),
                        'block_read_bytes': int(container_data.get('block_read_bytes', 0)),
                        'block_write_bytes': int(container_data.get('block_write_bytes', 0)),
                        'restart_count': int(container_data.get('restart_count', 0))
                    },
                    'time': metrics.timestamp
                }
                points.append(container_point)
            
            self.influxdb_client.write_points(points)
            logger.debug(f"Stored {len(points)} resource metric points in InfluxDB")
            
        except Exception as e:
            logger.error(f"Error storing metrics in InfluxDB: {e}")

    def generate_resource_report(self, metrics: ResourceMetrics, issues: List[str], 
                               recommendations: List[str], optimizations: List[str]) -> str:
        """Generate comprehensive resource report"""
        
        report = f"""# Resource Monitoring Report
**Timestamp**: {metrics.timestamp.isoformat()}

## System Overview
- **CPU Usage**: {metrics.host_cpu_percent:.1f}%
- **Memory Usage**: {metrics.host_memory_percent:.1f}%
- **Disk Usage**: {metrics.host_disk_percent:.1f}%
- **Network I/O**: {metrics.host_network_bytes_sent:,} sent, {metrics.host_network_bytes_recv:,} received
- **Active Containers**: {len([c for c in metrics.containers.values() if c.get('status') == 'running'])}
- **Total Containers**: {len(metrics.containers)}

## Resource Issues
"""
        
        if issues:
            for issue in issues:
                report += f"- {issue}\n"
        else:
            report += "- No issues detected ✅\n"
        
        report += "\n## Recommendations\n"
        if recommendations:
            for rec in recommendations:
                report += f"- {rec}\n"
        else:
            report += "- System operating optimally ✅\n"
        
        if optimizations:
            report += "\n## Optimizations Applied\n"
            for opt in optimizations:
                report += f"- {opt}\n"
        
        # Top containers by resource usage
        if metrics.containers:
            running_containers = {name: data for name, data in metrics.containers.items() 
                                if data.get('status') == 'running' and data.get('cpu_percent', 0) > 0}
            
            if running_containers:
                # Top CPU consumers
                top_cpu = sorted(running_containers.items(), 
                               key=lambda x: x[1].get('cpu_percent', 0), reverse=True)[:5]
                
                report += "\n## Top CPU Consumers\n"
                for name, data in top_cpu:
                    report += f"- **{name}**: {data.get('cpu_percent', 0):.1f}% CPU\n"
                
                # Top Memory consumers
                top_memory = sorted(running_containers.items(), 
                                  key=lambda x: x[1].get('memory_percent', 0), reverse=True)[:5]
                
                report += "\n## Top Memory Consumers\n"
                for name, data in top_memory:
                    memory_mb = data.get('memory_usage_bytes', 0) / (1024 * 1024)
                    report += f"- **{name}**: {data.get('memory_percent', 0):.1f}% ({memory_mb:.1f} MB)\n"
        
        return report

    def run_monitoring_cycle(self):
        """Run a complete monitoring and optimization cycle"""
        try:
            logger.info("Starting resource monitoring cycle")
            
            # Collect metrics
            host_metrics = self.collect_host_metrics()
            container_metrics = self.collect_container_metrics()
            
            if not host_metrics:
                logger.warning("Failed to collect host metrics")
                return
            
            # Create metrics object
            metrics = ResourceMetrics(
                timestamp=datetime.utcnow(),
                host_cpu_percent=host_metrics.get('cpu', {}).get('percent', 0),
                host_memory_percent=host_metrics.get('memory', {}).get('percent', 0),
                host_disk_percent=host_metrics.get('disk', {}).get('percent', 0),
                host_network_bytes_sent=host_metrics.get('network', {}).get('bytes_sent', 0),
                host_network_bytes_recv=host_metrics.get('network', {}).get('bytes_recv', 0),
                containers=container_metrics,
                recommendations=[]
            )
            
            # Analyze resources
            issues, recommendations = self.analyze_resource_usage(host_metrics, container_metrics)
            metrics.recommendations = recommendations
            
            # Store metrics
            self.store_metrics(metrics)
            
            # Apply optimizations if needed
            optimizations = []
            if issues:
                optimizations = self.apply_optimizations(recommendations, host_metrics, container_metrics)
            
            # Send alerts for critical issues
            self.send_alerts(issues, recommendations, host_metrics)
            
            # Generate and save report
            report = self.generate_resource_report(metrics, issues, recommendations, optimizations)
            
            # Save report to file
            report_dir = Path('/app/reports')
            report_dir.mkdir(exist_ok=True)
            report_file = report_dir / f"resource_report_{int(time.time())}.md"
            report_file.write_text(report)
            
            # Keep resource history (last 24 hours)
            self.resource_history.append(metrics)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            self.resource_history = [m for m in self.resource_history if m.timestamp > cutoff_time]
            
            logger.info(f"Monitoring cycle complete: {len(issues)} issues, {len(recommendations)} recommendations, {len(optimizations)} optimizations")
            
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")

    def run_continuous_monitoring(self):
        """Run continuous resource monitoring"""
        logger.info("Starting continuous resource monitoring")
        
        while True:
            try:
                self.run_monitoring_cycle()
                time.sleep(MONITORING_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Stopping resource monitoring")
                break
            except Exception as e:
                logger.error(f"Error in continuous monitoring: {e}")
                time.sleep(60)


if __name__ == "__main__":
    optimizer = ResourceOptimizer()
    optimizer.run_continuous_monitoring()
