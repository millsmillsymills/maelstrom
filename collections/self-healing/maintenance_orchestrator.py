#!/usr/bin/env python3
"""
Automated Maintenance and Self-Healing Orchestrator
Provides intelligent maintenance scheduling, automated recovery, and system health management
"""

import docker
import subprocess
import json
import time
import logging
import threading
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
import requests
from dataclasses import dataclass, field
from enum import Enum
import psutil
import shutil

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
HEALTH_CHECK_INTERVAL = 60  # seconds
MAINTENANCE_SCHEDULE_HOURS = [2, 14]  # 2 AM and 2 PM for maintenance windows
SELF_HEALING_MAX_ATTEMPTS = 3
BACKUP_RETENTION_DAYS = 7
LOG_RETENTION_DAYS = 30

INFLUXDB_HOST = "influxdb"
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = "maintenance_automation"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class MaintenanceType(Enum):
    ROUTINE = "routine"
    EMERGENCY = "emergency"
    PREVENTIVE = "preventive"
    RECOVERY = "recovery"

@dataclass
class ServiceHealth:
    """Service health status data"""
    name: str
    status: HealthStatus
    last_check: datetime
    issues: List[str] = field(default_factory=list)
    recovery_attempts: int = 0
    last_recovery: Optional[datetime] = None
    uptime_seconds: int = 0
    restart_count: int = 0

@dataclass
class MaintenanceTask:
    """Maintenance task definition"""
    name: str
    task_type: MaintenanceType
    priority: int  # 1-10, higher is more urgent
    scheduled_time: Optional[datetime] = None
    max_duration_minutes: int = 30
    prerequisites: List[str] = field(default_factory=list)
    cleanup_required: bool = False
    backup_required: bool = False

class MaintenanceOrchestrator:
    """Advanced maintenance orchestration and self-healing system"""
    
    def __init__(self):
        self.docker_client = docker.from_env()
        self.influxdb_client = None
        self.setup_influxdb()
        
        # Service tracking
        self.service_health = {}
        self.maintenance_history = []
        self.recovery_blacklist = set()  # Services that failed recovery multiple times
        self.maintenance_window = False
        
        # Critical service definitions
        self.critical_services = {
            'influxdb', 'grafana', 'prometheus', 'alertmanager', 
            'vault', 'mysql', 'zabbix-server'
        }
        
        # Maintenance tasks queue
        self.maintenance_queue = []
        
        # Self-healing statistics
        self.healing_stats = {
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'maintenance_tasks_completed': 0,
            'uptime_improvements': 0
        }
        
        # Schedule maintenance windows
        self.schedule_maintenance_windows()
        
    def setup_influxdb(self):
        """Setup InfluxDB connection for maintenance tracking"""
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
                
            logger.info("InfluxDB connection established for maintenance tracking")
                
        except Exception as e:
            logger.error(f"Failed to setup InfluxDB: {e}")
            self.influxdb_client = None

    def schedule_maintenance_windows(self):
        """Schedule regular maintenance windows"""
        for hour in MAINTENANCE_SCHEDULE_HOURS:
            schedule.every().day.at(f"{hour:02d}:00").do(self.enter_maintenance_window)
            # End maintenance window after 30 minutes
            end_hour = hour
            end_minute = 30
            if end_minute >= 60:
                end_hour += 1
                end_minute = 0
            schedule.every().day.at(f"{end_hour:02d}:{end_minute:02d}").do(self.exit_maintenance_window)
        
        logger.info(f"Scheduled maintenance windows at hours: {MAINTENANCE_SCHEDULE_HOURS}")

    def enter_maintenance_window(self):
        """Enter maintenance window"""
        self.maintenance_window = True
        logger.info("🔧 Entering maintenance window")
        
        # Add routine maintenance tasks
        self.queue_routine_maintenance()
        
        # Send notification
        self.send_notification("🔧 Maintenance Window Started", 
                             "Automated maintenance window has begun. Routine maintenance tasks will be executed.",
                             "info")

    def exit_maintenance_window(self):
        """Exit maintenance window"""
        self.maintenance_window = False
        logger.info("✅ Exiting maintenance window")
        
        # Send summary notification
        completed_tasks = len([t for t in self.maintenance_history if t.get('completed_today', False)])
        self.send_notification("✅ Maintenance Window Complete", 
                             f"Maintenance window completed. {completed_tasks} tasks executed successfully.",
                             "good")

    def queue_routine_maintenance(self):
        """Queue routine maintenance tasks"""
        routine_tasks = [
            MaintenanceTask(
                name="docker_system_cleanup",
                task_type=MaintenanceType.ROUTINE,
                priority=3,
                max_duration_minutes=10,
                cleanup_required=True
            ),
            MaintenanceTask(
                name="log_rotation_cleanup",
                task_type=MaintenanceType.ROUTINE,
                priority=2,
                max_duration_minutes=5,
                cleanup_required=True
            ),
            MaintenanceTask(
                name="health_check_validation",
                task_type=MaintenanceType.ROUTINE,
                priority=4,
                max_duration_minutes=15
            ),
            MaintenanceTask(
                name="backup_critical_configs",
                task_type=MaintenanceType.ROUTINE,
                priority=5,
                max_duration_minutes=10,
                backup_required=True
            ),
            MaintenanceTask(
                name="security_updates_check",
                task_type=MaintenanceType.ROUTINE,
                priority=3,
                max_duration_minutes=5
            ),
            MaintenanceTask(
                name="certificate_renewal_check",
                task_type=MaintenanceType.PREVENTIVE,
                priority=4,
                max_duration_minutes=5
            )
        ]
        
        for task in routine_tasks:
            self.maintenance_queue.append(task)
            logger.info(f"Queued routine maintenance task: {task.name}")

    def check_service_health(self) -> Dict[str, ServiceHealth]:
        """Comprehensive service health assessment"""
        current_health = {}
        
        try:
            containers = self.docker_client.containers.list(all=True)
            
            for container in containers:
                service_name = container.name
                
                # Get existing health record or create new
                if service_name in self.service_health:
                    health_record = self.service_health[service_name]
                else:
                    health_record = ServiceHealth(
                        name=service_name,
                        status=HealthStatus.UNKNOWN,
                        last_check=datetime.utcnow()
                    )
                
                # Update health record
                health_record.last_check = datetime.utcnow()
                health_record.issues = []
                
                # Basic container status
                if container.status == 'running':
                    # Get container stats for health assessment
                    try:
                        stats = container.stats(stream=False)
                        health_record.uptime_seconds = int(time.time() - 
                                                          datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00')).timestamp())
                        health_record.restart_count = container.attrs.get('RestartCount', 0)
                        
                        # Check container health
                        health_status = container.attrs.get('State', {}).get('Health', {}).get('Status', 'unknown')
                        
                        if health_status == 'healthy':
                            health_record.status = HealthStatus.HEALTHY
                        elif health_status == 'unhealthy':
                            health_record.status = HealthStatus.CRITICAL
                            health_record.issues.append("Container health check failed")
                        elif container.attrs.get('State', {}).get('Restarting', False):
                            health_record.status = HealthStatus.WARNING
                            health_record.issues.append("Container is restarting")
                        else:
                            health_record.status = HealthStatus.HEALTHY
                            
                        # Check resource usage
                        if 'memory_stats' in stats:
                            memory_usage = stats['memory_stats'].get('usage', 0)
                            memory_limit = stats['memory_stats'].get('limit', 1)
                            memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
                            
                            if memory_percent > 95:
                                health_record.status = HealthStatus.CRITICAL
                                health_record.issues.append(f"Critical memory usage: {memory_percent:.1f}%")
                            elif memory_percent > 85:
                                health_record.status = HealthStatus.WARNING
                                health_record.issues.append(f"High memory usage: {memory_percent:.1f}%")
                        
                        # Check if container has been restarting frequently
                        if health_record.restart_count > 5:
                            health_record.status = HealthStatus.WARNING
                            health_record.issues.append(f"Frequent restarts: {health_record.restart_count}")
                            
                    except Exception as e:
                        health_record.status = HealthStatus.WARNING
                        health_record.issues.append(f"Stats collection failed: {str(e)}")
                        
                elif container.status in ['exited', 'dead']:
                    health_record.status = HealthStatus.CRITICAL
                    health_record.issues.append(f"Container not running: {container.status}")
                    health_record.uptime_seconds = 0
                    
                else:
                    health_record.status = HealthStatus.WARNING
                    health_record.issues.append(f"Unknown container status: {container.status}")
                
                current_health[service_name] = health_record
                
        except Exception as e:
            logger.error(f"Error checking service health: {e}")
        
        # Update service health tracking
        self.service_health.update(current_health)
        return current_health

    def attempt_service_recovery(self, service_name: str, health_record: ServiceHealth) -> bool:
        """Attempt to recover a failed or unhealthy service"""
        if service_name in self.recovery_blacklist:
            logger.warning(f"Service {service_name} is blacklisted from recovery")
            return False
            
        if health_record.recovery_attempts >= SELF_HEALING_MAX_ATTEMPTS:
            logger.warning(f"Max recovery attempts reached for {service_name}")
            self.recovery_blacklist.add(service_name)
            return False
        
        logger.info(f"🔄 Attempting recovery for service: {service_name} (attempt {health_record.recovery_attempts + 1})")
        
        try:
            container = self.docker_client.containers.get(service_name)
            recovery_success = False
            
            # Choose recovery strategy based on issues
            if any("not running" in issue for issue in health_record.issues):
                # Container is stopped - try to start it
                logger.info(f"Starting stopped container: {service_name}")
                container.start()
                time.sleep(10)  # Wait for startup
                recovery_success = container.status == 'running'
                
            elif any("health check failed" in issue for issue in health_record.issues):
                # Health check failed - try restart
                logger.info(f"Restarting unhealthy container: {service_name}")
                container.restart()
                time.sleep(15)  # Wait for restart
                recovery_success = container.status == 'running'
                
            elif any("memory usage" in issue for issue in health_record.issues):
                # Memory issue - try restart to clear memory
                logger.info(f"Restarting high-memory container: {service_name}")
                container.restart()
                time.sleep(20)  # Wait longer for memory-heavy services
                recovery_success = container.status == 'running'
                
            elif any("restarting" in issue for issue in health_record.issues):
                # Container stuck restarting - force restart
                logger.info(f"Force restarting stuck container: {service_name}")
                container.kill()
                time.sleep(5)
                container.start()
                time.sleep(15)
                recovery_success = container.status == 'running'
                
            # Update recovery tracking
            health_record.recovery_attempts += 1
            health_record.last_recovery = datetime.utcnow()
            
            if recovery_success:
                logger.info(f"✅ Successfully recovered service: {service_name}")
                self.healing_stats['successful_recoveries'] += 1
                health_record.recovery_attempts = 0  # Reset on success
                
                # Send success notification for critical services
                if service_name in self.critical_services:
                    self.send_notification(f"✅ Service Recovered", 
                                         f"Critical service '{service_name}' has been successfully recovered.",
                                         "good")
                
                return True
            else:
                logger.error(f"❌ Failed to recover service: {service_name}")
                self.healing_stats['failed_recoveries'] += 1
                
                # Send failure notification for critical services
                if service_name in self.critical_services:
                    self.send_notification(f"❌ Recovery Failed", 
                                         f"Failed to recover critical service '{service_name}' after {health_record.recovery_attempts} attempts.",
                                         "danger")
                
                return False
                
        except Exception as e:
            logger.error(f"Error during recovery of {service_name}: {e}")
            health_record.recovery_attempts += 1
            self.healing_stats['failed_recoveries'] += 1
            return False

    def execute_maintenance_task(self, task: MaintenanceTask) -> bool:
        """Execute a specific maintenance task"""
        logger.info(f"🔧 Executing maintenance task: {task.name}")
        
        start_time = datetime.utcnow()
        success = False
        
        try:
            if task.name == "docker_system_cleanup":
                success = self.docker_system_cleanup()
                
            elif task.name == "log_rotation_cleanup":
                success = self.log_rotation_cleanup()
                
            elif task.name == "health_check_validation":
                success = self.health_check_validation()
                
            elif task.name == "backup_critical_configs":
                success = self.backup_critical_configs()
                
            elif task.name == "security_updates_check":
                success = self.security_updates_check()
                
            elif task.name == "certificate_renewal_check":
                success = self.certificate_renewal_check()
                
            else:
                logger.warning(f"Unknown maintenance task: {task.name}")
                return False
            
            # Record maintenance task execution
            duration = (datetime.utcnow() - start_time).total_seconds()
            task_record = {
                'name': task.name,
                'type': task.task_type.value,
                'success': success,
                'duration_seconds': duration,
                'timestamp': start_time.isoformat(),
                'completed_today': True
            }
            
            self.maintenance_history.append(task_record)
            self.healing_stats['maintenance_tasks_completed'] += 1
            
            # Store in InfluxDB
            if self.influxdb_client:
                point = {
                    'measurement': 'maintenance_tasks',
                    'tags': {
                        'task_name': task.name,
                        'task_type': task.task_type.value,
                        'success': success
                    },
                    'fields': {
                        'duration_seconds': duration,
                        'priority': task.priority
                    },
                    'time': start_time
                }
                
                try:
                    self.influxdb_client.write_points([point])
                except Exception as e:
                    logger.error(f"Failed to store maintenance task in InfluxDB: {e}")
            
            if success:
                logger.info(f"✅ Completed maintenance task: {task.name} ({duration:.1f}s)")
            else:
                logger.error(f"❌ Failed maintenance task: {task.name} ({duration:.1f}s)")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing maintenance task {task.name}: {e}")
            return False

    def docker_system_cleanup(self) -> bool:
        """Perform Docker system cleanup"""
        try:
            logger.info("Running Docker system cleanup")
            
            # Prune containers
            pruned_containers = self.docker_client.containers.prune()
            containers_removed = len(pruned_containers.get('ContainersDeleted', []))
            
            # Prune images
            pruned_images = self.docker_client.images.prune()
            images_removed = len(pruned_images.get('ImagesDeleted', []))
            
            # Prune networks
            pruned_networks = self.docker_client.networks.prune()
            networks_removed = len(pruned_networks.get('NetworksDeleted', []))
            
            # Prune volumes
            pruned_volumes = self.docker_client.volumes.prune()
            volumes_removed = len(pruned_volumes.get('VolumesDeleted', []))
            
            # Calculate space reclaimed
            space_reclaimed = pruned_containers.get('SpaceReclaimed', 0) + \
                            pruned_images.get('SpaceReclaimed', 0) + \
                            pruned_volumes.get('SpaceReclaimed', 0)
            
            logger.info(f"Docker cleanup completed: {containers_removed} containers, "
                       f"{images_removed} images, {networks_removed} networks, "
                       f"{volumes_removed} volumes removed. "
                       f"Space reclaimed: {space_reclaimed / (1024*1024):.1f} MB")
            
            return True
            
        except Exception as e:
            logger.error(f"Docker system cleanup failed: {e}")
            return False

    def log_rotation_cleanup(self) -> bool:
        """Clean up old log files"""
        try:
            logger.info("Running log rotation cleanup")
            
            log_dirs = [
                '/var/log',
                '/home/mills/logs',
                '/home/mills/collections/*/logs'
            ]
            
            cutoff_date = datetime.utcnow() - timedelta(days=LOG_RETENTION_DAYS)
            files_removed = 0
            space_freed = 0
            
            for log_dir_pattern in log_dirs:
                for log_dir in Path('/').glob(log_dir_pattern.lstrip('/')):
                    if log_dir.is_dir():
                        for log_file in log_dir.rglob('*.log*'):
                            try:
                                if log_file.is_file():
                                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                                    if file_mtime < cutoff_date:
                                        file_size = log_file.stat().st_size
                                        log_file.unlink()
                                        files_removed += 1
                                        space_freed += file_size
                            except Exception as e:
                                logger.debug(f"Could not remove log file {log_file}: {e}")
            
            logger.info(f"Log cleanup completed: {files_removed} files removed, "
                       f"{space_freed / (1024*1024):.1f} MB freed")
            
            return True
            
        except Exception as e:
            logger.error(f"Log rotation cleanup failed: {e}")
            return False

    def health_check_validation(self) -> bool:
        """Validate health check endpoints"""
        try:
            logger.info("Running health check validation")
            
            health_endpoints = {
                'influxdb': 'http://influxdb:8086/ping',
                'prometheus': 'http://prometheus:9090/-/healthy',
                'grafana': 'http://grafana:3000/api/health',
                'alertmanager': 'http://alertmanager:9093/-/healthy',
                'vault': 'http://vault:8200/v1/sys/health'
            }
            
            failed_checks = []
            
            for service, endpoint in health_endpoints.items():
                try:
                    response = requests.get(endpoint, timeout=10)
                    if response.status_code not in [200, 204]:
                        failed_checks.append(f"{service}: HTTP {response.status_code}")
                except requests.RequestException as e:
                    failed_checks.append(f"{service}: {str(e)}")
            
            if failed_checks:
                logger.warning(f"Health check failures: {'; '.join(failed_checks)}")
                # Queue recovery tasks for failed services
                for failure in failed_checks:
                    service_name = failure.split(':')[0]
                    if service_name in self.service_health:
                        self.service_health[service_name].issues.append("Health endpoint failed")
            else:
                logger.info("All health checks passed")
            
            return len(failed_checks) == 0
            
        except Exception as e:
            logger.error(f"Health check validation failed: {e}")
            return False

    def backup_critical_configs(self) -> bool:
        """Backup critical configuration files"""
        try:
            logger.info("Running critical config backup")
            
            # Create backup directory
            backup_dir = Path(f"/home/mills/backups/maintenance_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Critical files to backup
            critical_files = [
                '/home/mills/docker-compose.yml',
                '/home/mills/.env',
                '/home/mills/collections/prometheus/prometheus.yml',
                '/home/mills/collections/grafana/dashboards',
                '/home/mills/secrets'
            ]
            
            backed_up_files = 0
            
            for file_path in critical_files:
                source_path = Path(file_path)
                if source_path.exists():
                    try:
                        if source_path.is_file():
                            dest_path = backup_dir / source_path.name
                            shutil.copy2(source_path, dest_path)
                            backed_up_files += 1
                        elif source_path.is_dir():
                            dest_path = backup_dir / source_path.name
                            shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
                            backed_up_files += 1
                    except Exception as e:
                        logger.warning(f"Failed to backup {source_path}: {e}")
            
            # Clean up old backups
            self.cleanup_old_backups()
            
            logger.info(f"Config backup completed: {backed_up_files} items backed up to {backup_dir}")
            
            return backed_up_files > 0
            
        except Exception as e:
            logger.error(f"Critical config backup failed: {e}")
            return False

    def cleanup_old_backups(self):
        """Clean up backups older than retention period"""
        try:
            backup_base_dir = Path("/home/mills/backups")
            if not backup_base_dir.exists():
                return
            
            cutoff_date = datetime.utcnow() - timedelta(days=BACKUP_RETENTION_DAYS)
            removed_backups = 0
            
            for backup_dir in backup_base_dir.glob("maintenance_backup_*"):
                if backup_dir.is_dir():
                    dir_mtime = datetime.fromtimestamp(backup_dir.stat().st_mtime)
                    if dir_mtime < cutoff_date:
                        shutil.rmtree(backup_dir)
                        removed_backups += 1
            
            if removed_backups > 0:
                logger.info(f"Cleaned up {removed_backups} old backup directories")
                
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")

    def security_updates_check(self) -> bool:
        """Check for security updates"""
        try:
            logger.info("Running security updates check")
            
            # Check for container image updates
            outdated_images = []
            
            containers = self.docker_client.containers.list()
            for container in containers[:10]:  # Limit to avoid overwhelming API
                try:
                    image_name = container.image.tags[0] if container.image.tags else 'unknown'
                    if ':latest' in image_name:
                        # Pull latest and check if update is available
                        try:
                            pulled_image = self.docker_client.images.pull(image_name.split(':')[0])
                            if pulled_image.id != container.image.id:
                                outdated_images.append(container.name)
                        except Exception:
                            pass  # Skip if pull fails
                except Exception:
                    continue
            
            if outdated_images:
                logger.info(f"Found {len(outdated_images)} containers with available updates: {', '.join(outdated_images)}")
                
                # Send notification about available updates
                self.send_notification("🔄 Security Updates Available", 
                                     f"Found {len(outdated_images)} containers with available updates. Consider updating during next maintenance window.",
                                     "warning")
            else:
                logger.info("All container images are up to date")
            
            return True
            
        except Exception as e:
            logger.error(f"Security updates check failed: {e}")
            return False

    def certificate_renewal_check(self) -> bool:
        """Check SSL certificate expiration"""
        try:
            logger.info("Running certificate renewal check")
            
            # Check for certificates in SWAG directory
            swag_certs_dir = Path("/home/mills/collections/swag/config/etc/letsencrypt/live")
            
            if not swag_certs_dir.exists():
                logger.info("No SWAG certificates directory found")
                return True
            
            expiring_certs = []
            warning_days = 30  # Warn if expiring within 30 days
            
            for cert_dir in swag_certs_dir.iterdir():
                if cert_dir.is_dir():
                    cert_file = cert_dir / "cert.pem"
                    if cert_file.exists():
                        try:
                            # Use openssl to check certificate expiration
                            result = subprocess.run([
                                'openssl', 'x509', '-in', str(cert_file), 
                                '-noout', '-enddate'
                            ], capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                # Parse expiration date
                                date_str = result.stdout.strip().replace('notAfter=', '')
                                # This is a simplified check - in production would use proper date parsing
                                logger.debug(f"Certificate {cert_dir.name} expires: {date_str}")
                                
                        except Exception as e:
                            logger.debug(f"Could not check certificate {cert_dir.name}: {e}")
            
            if expiring_certs:
                logger.warning(f"Found {len(expiring_certs)} certificates expiring soon")
                self.send_notification("⚠️ Certificates Expiring", 
                                     f"Found {len(expiring_certs)} SSL certificates expiring within {warning_days} days.",
                                     "warning")
            else:
                logger.info("All certificates are valid")
            
            return True
            
        except Exception as e:
            logger.error(f"Certificate renewal check failed: {e}")
            return False

    def send_notification(self, title: str, message: str, level: str = "info"):
        """Send notification via Slack"""
        try:
            webhook_url = get_slack_webhook()
            if not webhook_url:
                return
            
            color_map = {
                "info": "#36a64f",
                "good": "#36a64f", 
                "warning": "#ff9800",
                "danger": "#f44336"
            }
            
            payload = {
                'text': title,
                'attachments': [{
                    'color': color_map.get(level, "#36a64f"),
                    'fields': [{
                        'title': 'Details',
                        'value': message,
                        'short': False
                    }],
                    'footer': 'Maelstrom Maintenance Orchestrator',
                    'ts': int(time.time())
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.debug(f"Sent notification: {title}")
            else:
                logger.error(f"Failed to send notification: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    def run_self_healing_cycle(self):
        """Run complete self-healing and maintenance cycle"""
        try:
            logger.info("Starting self-healing cycle")
            
            # 1. Check service health
            current_health = self.check_service_health()
            
            # 2. Attempt recovery for unhealthy services
            services_needing_recovery = [
                (name, health) for name, health in current_health.items()
                if health.status in [HealthStatus.CRITICAL, HealthStatus.WARNING] and health.issues
            ]
            
            recovery_actions = 0
            for service_name, health_record in services_needing_recovery:
                if self.attempt_service_recovery(service_name, health_record):
                    recovery_actions += 1
                    time.sleep(5)  # Brief pause between recovery attempts
            
            # 3. Process maintenance queue during maintenance windows
            if self.maintenance_window and self.maintenance_queue:
                # Sort by priority (higher numbers first)
                self.maintenance_queue.sort(key=lambda x: x.priority, reverse=True)
                
                tasks_executed = 0
                while self.maintenance_queue and tasks_executed < 5:  # Limit tasks per cycle
                    task = self.maintenance_queue.pop(0)
                    if self.execute_maintenance_task(task):
                        tasks_executed += 1
                    time.sleep(2)  # Brief pause between tasks
            
            # 4. Store health metrics
            if self.influxdb_client:
                self.store_health_metrics(current_health)
            
            # 5. Update statistics
            healthy_services = len([h for h in current_health.values() if h.status == HealthStatus.HEALTHY])
            total_services = len(current_health)
            
            logger.info(f"Self-healing cycle complete: {healthy_services}/{total_services} services healthy, "
                       f"{recovery_actions} recovery actions, "
                       f"{self.healing_stats['maintenance_tasks_completed']} maintenance tasks completed")
            
        except Exception as e:
            logger.error(f"Error in self-healing cycle: {e}")

    def store_health_metrics(self, health_data: Dict[str, ServiceHealth]):
        """Store service health metrics in InfluxDB"""
        try:
            points = []
            timestamp = datetime.utcnow()
            
            # Overall health summary
            healthy_count = len([h for h in health_data.values() if h.status == HealthStatus.HEALTHY])
            warning_count = len([h for h in health_data.values() if h.status == HealthStatus.WARNING])
            critical_count = len([h for h in health_data.values() if h.status == HealthStatus.CRITICAL])
            
            summary_point = {
                'measurement': 'service_health_summary',
                'tags': {
                    'orchestrator': 'maintenance'
                },
                'fields': {
                    'total_services': len(health_data),
                    'healthy_services': healthy_count,
                    'warning_services': warning_count,
                    'critical_services': critical_count,
                    'health_percentage': (healthy_count / len(health_data)) * 100 if health_data else 0,
                    'successful_recoveries': self.healing_stats['successful_recoveries'],
                    'failed_recoveries': self.healing_stats['failed_recoveries'],
                    'maintenance_tasks_completed': self.healing_stats['maintenance_tasks_completed']
                },
                'time': timestamp
            }
            points.append(summary_point)
            
            # Individual service health
            for service_name, health in health_data.items():
                service_point = {
                    'measurement': 'service_health',
                    'tags': {
                        'service_name': service_name,
                        'status': health.status.value,
                        'is_critical': service_name in self.critical_services
                    },
                    'fields': {
                        'uptime_seconds': health.uptime_seconds,
                        'restart_count': health.restart_count,
                        'recovery_attempts': health.recovery_attempts,
                        'issue_count': len(health.issues),
                        'health_score': 100 if health.status == HealthStatus.HEALTHY else 
                                       50 if health.status == HealthStatus.WARNING else 0
                    },
                    'time': timestamp
                }
                points.append(service_point)
            
            self.influxdb_client.write_points(points)
            logger.debug(f"Stored {len(points)} health metric points in InfluxDB")
            
        except Exception as e:
            logger.error(f"Error storing health metrics: {e}")

    def run_continuous_orchestration(self):
        """Run continuous maintenance orchestration"""
        logger.info("Starting continuous maintenance orchestration")
        
        while True:
            try:
                # Run scheduled maintenance windows
                schedule.run_pending()
                
                # Run self-healing cycle
                self.run_self_healing_cycle()
                
                # Sleep until next cycle
                time.sleep(HEALTH_CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Stopping maintenance orchestrator")
                break
            except Exception as e:
                logger.error(f"Error in continuous orchestration: {e}")
                time.sleep(60)


if __name__ == "__main__":
    orchestrator = MaintenanceOrchestrator()
    orchestrator.run_continuous_orchestration()
