#!/usr/bin/env python3
"""
Comprehensive Disaster Recovery Orchestrator
Advanced backup, recovery, and business continuity system for the Maelstrom infrastructure
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tarfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from collections import deque
import threading
from enum import Enum
import hashlib
import gzip

import requests
from influxdb import InfluxDBClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BackupType(Enum):
    """Backup operation types"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"

class BackupStatus(Enum):
    """Backup operation status"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"

class RecoveryType(Enum):
    """Recovery operation types"""
    POINT_IN_TIME = "point_in_time"
    FULL_RESTORE = "full_restore"
    SELECTIVE_RESTORE = "selective_restore"
    DISASTER_RECOVERY = "disaster_recovery"

class BackupRetentionPolicy(Enum):
    """Backup retention policies"""
    DAILY_7_WEEKLY_4_MONTHLY_12 = "daily_7_weekly_4_monthly_12"
    DAILY_30_WEEKLY_8_MONTHLY_6 = "daily_30_weekly_8_monthly_6"
    HOURLY_24_DAILY_7_WEEKLY_4 = "hourly_24_daily_7_weekly_4"

@dataclass
class BackupTarget:
    """Backup target specification"""
    target_id: str
    name: str
    description: str
    source_paths: List[str]
    backup_type: BackupType
    schedule_cron: str
    retention_policy: BackupRetentionPolicy
    compression: bool = True
    encryption: bool = True
    verification: bool = True
    exclude_patterns: List[str] = None
    pre_backup_commands: List[str] = None
    post_backup_commands: List[str] = None
    priority: int = 100  # Lower number = higher priority
    metadata: Dict[str, Any] = None

@dataclass
class BackupOperation:
    """Backup operation record"""
    operation_id: str
    target_id: str
    backup_type: BackupType
    status: BackupStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    source_size: int = 0
    backup_size: int = 0
    compression_ratio: float = 0.0
    file_count: int = 0
    backup_path: str = ""
    checksum: str = ""
    error_message: str = ""
    verification_result: bool = False
    metadata: Dict[str, Any] = None

@dataclass
class RecoveryPlan:
    """Disaster recovery plan"""
    plan_id: str
    name: str
    description: str
    recovery_type: RecoveryType
    target_systems: List[str]
    recovery_steps: List[Dict[str, Any]]
    estimated_rto: int  # Recovery Time Objective in minutes
    estimated_rpo: int  # Recovery Point Objective in minutes
    dependencies: List[str] = None
    validation_tests: List[str] = None
    notification_contacts: List[str] = None
    metadata: Dict[str, Any] = None

class BackupStorageManager:
    """Manages backup storage across multiple destinations"""
    
    def __init__(self):
        self.storage_locations = {}
        self.default_location = None
        self.encryption_key = None
        
        # Initialize storage locations
        self.setup_storage_locations()
    
    def setup_storage_locations(self):
        """Setup backup storage locations"""
        # Local storage
        local_backup_path = Path("/home/mills/backups")
        local_backup_path.mkdir(parents=True, exist_ok=True)
        
        self.storage_locations['local'] = {
            'type': 'local',
            'path': str(local_backup_path),
            'available_space': self.get_available_space(local_backup_path),
            'priority': 1
        }
        
        # Network storage (if configured)
        network_backup_path = os.environ.get('NETWORK_BACKUP_PATH')
        if network_backup_path and Path(network_backup_path).exists():
            self.storage_locations['network'] = {
                'type': 'network',
                'path': network_backup_path,
                'available_space': self.get_available_space(Path(network_backup_path)),
                'priority': 2
            }
        
        # Cloud storage (placeholder for future implementation)
        cloud_config = os.environ.get('CLOUD_BACKUP_CONFIG')
        if cloud_config:
            self.storage_locations['cloud'] = {
                'type': 'cloud',
                'config': cloud_config,
                'priority': 3
            }
        
        self.default_location = 'local'
        logger.info(f"Initialized {len(self.storage_locations)} backup storage locations")
    
    def get_available_space(self, path: Path) -> int:
        """Get available space in bytes"""
        try:
            if path.exists():
                stat = shutil.disk_usage(path)
                return stat.free
            return 0
        except Exception as e:
            logger.error(f"Error getting available space for {path}: {e}")
            return 0
    
    def get_optimal_storage_location(self, backup_size_estimate: int) -> str:
        """Get optimal storage location for backup"""
        # Sort by priority and available space
        viable_locations = []
        
        for location_id, config in self.storage_locations.items():
            available_space = config.get('available_space', 0)
            if available_space > backup_size_estimate * 1.2:  # 20% buffer
                viable_locations.append((location_id, config['priority'], available_space))
        
        if not viable_locations:
            logger.warning("No viable storage location found, using default")
            return self.default_location
        
        # Sort by priority (lower number = higher priority)
        viable_locations.sort(key=lambda x: x[1])
        return viable_locations[0][0]
    
    def create_backup_path(self, target_id: str, backup_type: BackupType, 
                          timestamp: datetime, location_id: str = None) -> str:
        """Create backup file path"""
        if not location_id:
            location_id = self.default_location
        
        location_config = self.storage_locations[location_id]
        base_path = Path(location_config['path'])
        
        # Create organized directory structure
        date_dir = timestamp.strftime('%Y/%m/%d')
        backup_dir = base_path / target_id / date_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        filename = f"{target_id}_{backup_type.value}_{timestamp_str}.tar.gz"
        
        return str(backup_dir / filename)

class DatabaseBackupManager:
    """Specialized backup manager for databases"""
    
    def __init__(self):
        self.supported_databases = ['influxdb', 'mysql']
    
    async def backup_influxdb(self, backup_path: str) -> Dict[str, Any]:
        """Backup InfluxDB databases"""
        try:
            # Create backup directory
            influx_backup_dir = Path(backup_path) / "influxdb_backup"
            influx_backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Get list of databases
            from collections.ml_analytics.secrets_helper import get_database_url
            db_url = get_database_url('influxdb')
            
            if '@' in db_url:
                auth_part = db_url.split('//')[1].split('@')[0]
                username, password = auth_part.split(':')
                host_part = db_url.split('@')[1].split(':')[0]
            else:
                username, password = None, None
                host_part = 'influxdb'
            
            client = InfluxDBClient(host=host_part, port=8086, username=username, password=password)
            databases = client.get_list_database()
            
            backup_results = {}
            
            for db in databases:
                db_name = db['name']
                if db_name.startswith('_'):  # Skip system databases
                    continue
                
                # Create database backup
                db_backup_path = influx_backup_dir / f"{db_name}_backup"
                db_backup_path.mkdir(exist_ok=True)
                
                # Use InfluxDB backup command
                backup_cmd = [
                    'docker', 'exec', 'influxdb',
                    'influxd', 'backup', '-portable',
                    '-database', db_name,
                    f'/tmp/{db_name}_backup'
                ]
                
                result = await asyncio.create_subprocess_exec(
                    *backup_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    # Copy backup from container
                    copy_cmd = [
                        'docker', 'cp',
                        f'influxdb:/tmp/{db_name}_backup',
                        str(db_backup_path)
                    ]
                    
                    copy_result = subprocess.run(copy_cmd, capture_output=True, text=True)
                    
                    backup_results[db_name] = {
                        'status': 'success' if copy_result.returncode == 0 else 'failed',
                        'path': str(db_backup_path),
                        'size': self.get_directory_size(db_backup_path)
                    }
                else:
                    backup_results[db_name] = {
                        'status': 'failed',
                        'error': stderr.decode() if stderr else 'Unknown error'
                    }
            
            return backup_results
            
        except Exception as e:
            logger.error(f"InfluxDB backup failed: {e}")
            return {'error': str(e)}
    
    async def backup_mysql(self, backup_path: str) -> Dict[str, Any]:
        """Backup MySQL databases"""
        try:
            mysql_backup_dir = Path(backup_path) / "mysql_backup"
            mysql_backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Get MySQL credentials
            from collections.ml_analytics.secrets_helper import get_database_url
            db_url = get_database_url('mysql')
            
            if '@' in db_url:
                auth_part = db_url.split('//')[1].split('@')[0]
                username, password = auth_part.split(':')
            else:
                username, password = 'root', ''
            
            # Backup all databases
            backup_file = mysql_backup_dir / f"mysql_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            
            backup_cmd = [
                'docker', 'exec', 'zabbix-mysql',
                'mysqldump', '-u', username, f'-p{password}',
                '--all-databases', '--single-transaction'
            ]
            
            with open(backup_file, 'w') as f:
                result = await asyncio.create_subprocess_exec(
                    *backup_cmd,
                    stdout=f,
                    stderr=asyncio.subprocess.PIPE
                )
                
                _, stderr = await result.communicate()
            
            if result.returncode == 0:
                # Compress the backup
                compressed_file = f"{backup_file}.gz"
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove uncompressed file
                backup_file.unlink()
                
                return {
                    'mysql': {
                        'status': 'success',
                        'path': compressed_file,
                        'size': Path(compressed_file).stat().st_size
                    }
                }
            else:
                error_msg = stderr.decode() if stderr else 'Unknown error'
                return {'mysql': {'status': 'failed', 'error': error_msg}}
                
        except Exception as e:
            logger.error(f"MySQL backup failed: {e}")
            return {'error': str(e)}
    
    def get_directory_size(self, path: Path) -> int:
        """Get total size of directory"""
        try:
            total_size = 0
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception as e:
            logger.error(f"Error calculating directory size for {path}: {e}")
            return 0

class DisasterRecoveryOrchestrator:
    """Main disaster recovery orchestration system"""
    
    def __init__(self):
        self.running = False
        self.backup_targets = {}
        self.backup_operations = deque(maxlen=10000)
        self.recovery_plans = {}
        
        # Component managers
        self.storage_manager = BackupStorageManager()
        self.db_backup_manager = DatabaseBackupManager()
        
        # Backup scheduler
        self.backup_queue = asyncio.Queue(maxsize=100)
        self.recovery_queue = asyncio.Queue(maxlen=50)
        
        # Statistics
        self.stats = {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'total_backup_size': 0,
            'last_backup_time': None,
            'recovery_tests_performed': 0,
            'average_backup_time': 0.0
        }
        
        # Initialize system
        self.setup_database()
        self.load_default_backup_targets()
        self.load_recovery_plans()
    
    def setup_database(self):
        """Setup InfluxDB connection for backup metrics"""
        try:
            from collections.ml_analytics.secrets_helper import get_database_url
            db_url = get_database_url('influxdb')
            
            # Parse connection URL
            if '@' in db_url:
                auth_part = db_url.split('//')[1].split('@')[0]
                username, password = auth_part.split(':')
                host_part = db_url.split('@')[1].split(':')[0]
                port = 8086
            else:
                username, password = None, None
                host_part = db_url.split('//')[1].split(':')[0]
                port = 8086
            
            self.influxdb_client = InfluxDBClient(
                host=host_part,
                port=port,
                username=username,
                password=password,
                database='disaster_recovery'
            )
            
            # Create database if it doesn't exist
            try:
                databases = self.influxdb_client.get_list_database()
                if not any(db['name'] == 'disaster_recovery' for db in databases):
                    self.influxdb_client.create_database('disaster_recovery')
                    logger.info("Created disaster_recovery database")
            except Exception as e:
                logger.warning(f"Could not create database: {e}")
            
            logger.info("InfluxDB connection established for disaster recovery")
            
        except Exception as e:
            logger.error(f"Failed to setup InfluxDB connection: {e}")
            self.influxdb_client = None
    
    def load_default_backup_targets(self):
        """Load default backup targets"""
        default_targets = [
            BackupTarget(
                target_id="system_configs",
                name="System Configurations",
                description="Critical system configuration files",
                source_paths=[
                    "/home/mills/docker-compose.yml",
                    "/home/mills/.env",
                    "/home/mills/collections",
                    "/home/mills/secrets"
                ],
                backup_type=BackupType.FULL,
                schedule_cron="0 2 * * *",  # Daily at 2 AM
                retention_policy=BackupRetentionPolicy.DAILY_30_WEEKLY_8_MONTHLY_6,
                exclude_patterns=["*.log", "*.tmp", "__pycache__", "*.pyc"],
                priority=10
            ),
            BackupTarget(
                target_id="influxdb_data",
                name="InfluxDB Time-Series Data",
                description="All time-series databases and metrics",
                source_paths=["/home/mills/collections/influxdb"],
                backup_type=BackupType.FULL,
                schedule_cron="0 1 * * *",  # Daily at 1 AM
                retention_policy=BackupRetentionPolicy.DAILY_7_WEEKLY_4_MONTHLY_12,
                pre_backup_commands=[
                    "docker exec influxdb influxd backup -portable -database telegraf /tmp/telegraf_backup",
                    "docker exec influxdb influxd backup -portable -database unifi_poller /tmp/unifi_backup"
                ],
                priority=5
            ),
            BackupTarget(
                target_id="mysql_data", 
                name="MySQL/Zabbix Database",
                description="Zabbix monitoring database",
                source_paths=["/home/mills/collections/mysql-data"],
                backup_type=BackupType.FULL,
                schedule_cron="0 3 * * *",  # Daily at 3 AM
                retention_policy=BackupRetentionPolicy.DAILY_7_WEEKLY_4_MONTHLY_12,
                priority=15
            ),
            BackupTarget(
                target_id="grafana_dashboards",
                name="Grafana Dashboards and Settings",
                description="Grafana configuration and custom dashboards",
                source_paths=[
                    "/home/mills/collections/grafana",
                    "/home/mills/collections/grafana-dashboards"
                ],
                backup_type=BackupType.INCREMENTAL,
                schedule_cron="0 */6 * * *",  # Every 6 hours
                retention_policy=BackupRetentionPolicy.HOURLY_24_DAILY_7_WEEKLY_4,
                priority=25
            ),
            BackupTarget(
                target_id="security_logs",
                name="Security and Audit Logs",
                description="Wazuh SIEM and security monitoring logs",
                source_paths=[
                    "/home/mills/collections/wazuh",
                    "/home/mills/collections/suricata",
                    "/home/mills/logs"
                ],
                backup_type=BackupType.INCREMENTAL,
                schedule_cron="0 */4 * * *",  # Every 4 hours
                retention_policy=BackupRetentionPolicy.HOURLY_24_DAILY_7_WEEKLY_4,
                exclude_patterns=["*.tmp", "*.lock"],
                priority=20
            )
        ]
        
        for target in default_targets:
            self.add_backup_target(target)
        
        logger.info(f"Loaded {len(default_targets)} default backup targets")
    
    def load_recovery_plans(self):
        """Load disaster recovery plans"""
        default_plans = [
            RecoveryPlan(
                plan_id="infrastructure_recovery",
                name="Full Infrastructure Recovery",
                description="Complete recovery of monitoring infrastructure",
                recovery_type=RecoveryType.DISASTER_RECOVERY,
                target_systems=["docker", "influxdb", "grafana", "prometheus"],
                recovery_steps=[
                    {"step": 1, "action": "restore_docker_compose", "timeout": 300},
                    {"step": 2, "action": "restore_secrets", "timeout": 120},
                    {"step": 3, "action": "restore_influxdb_data", "timeout": 1800},
                    {"step": 4, "action": "restore_grafana_config", "timeout": 300},
                    {"step": 5, "action": "start_core_services", "timeout": 600},
                    {"step": 6, "action": "verify_service_health", "timeout": 300}
                ],
                estimated_rto=60,  # 1 hour
                estimated_rpo=240,  # 4 hours
                validation_tests=["health_check", "data_integrity", "service_connectivity"],
                notification_contacts=["admin@maelstrom.local"]
            ),
            RecoveryPlan(
                plan_id="data_corruption_recovery",
                name="Data Corruption Recovery",
                description="Recovery from database corruption",
                recovery_type=RecoveryType.POINT_IN_TIME,
                target_systems=["influxdb", "mysql"],
                recovery_steps=[
                    {"step": 1, "action": "identify_corruption_point", "timeout": 600},
                    {"step": 2, "action": "stop_affected_services", "timeout": 120},
                    {"step": 3, "action": "restore_from_backup", "timeout": 3600},
                    {"step": 4, "action": "verify_data_integrity", "timeout": 900},
                    {"step": 5, "action": "restart_services", "timeout": 300}
                ],
                estimated_rto=120,  # 2 hours
                estimated_rpo=60,  # 1 hour
                validation_tests=["data_consistency", "query_performance"]
            ),
            RecoveryPlan(
                plan_id="selective_service_recovery",
                name="Selective Service Recovery",
                description="Recovery of specific failed services",
                recovery_type=RecoveryType.SELECTIVE_RESTORE,
                target_systems=["configurable"],
                recovery_steps=[
                    {"step": 1, "action": "identify_failed_service", "timeout": 180},
                    {"step": 2, "action": "restore_service_config", "timeout": 300},
                    {"step": 3, "action": "restore_service_data", "timeout": 1200},
                    {"step": 4, "action": "restart_service", "timeout": 180},
                    {"step": 5, "action": "verify_service_health", "timeout": 120}
                ],
                estimated_rto=30,  # 30 minutes
                estimated_rpo=15,  # 15 minutes
                validation_tests=["service_status", "dependency_check"]
            )
        ]
        
        for plan in default_plans:
            self.recovery_plans[plan.plan_id] = plan
        
        logger.info(f"Loaded {len(default_plans)} disaster recovery plans")
    
    def add_backup_target(self, target: BackupTarget):
        """Add backup target"""
        self.backup_targets[target.target_id] = target
        logger.info(f"Added backup target: {target.name}")
    
    async def perform_backup(self, target_id: str, backup_type: BackupType = None) -> BackupOperation:
        """Perform backup operation"""
        if target_id not in self.backup_targets:
            raise ValueError(f"Unknown backup target: {target_id}")
        
        target = self.backup_targets[target_id]
        if not backup_type:
            backup_type = target.backup_type
        
        # Create backup operation record
        operation_id = f"backup-{target_id}-{int(time.time())}"
        operation = BackupOperation(
            operation_id=operation_id,
            target_id=target_id,
            backup_type=backup_type,
            status=BackupStatus.PENDING,
            start_time=datetime.utcnow()
        )
        
        self.backup_operations.append(operation)
        
        try:
            operation.status = BackupStatus.RUNNING
            logger.info(f"Starting {backup_type.value} backup for {target.name}")
            
            # Execute pre-backup commands
            if target.pre_backup_commands:
                await self.execute_commands(target.pre_backup_commands, "pre-backup")
            
            # Calculate estimated backup size
            estimated_size = await self.estimate_backup_size(target.source_paths)
            
            # Get optimal storage location
            storage_location = self.storage_manager.get_optimal_storage_location(estimated_size)
            
            # Create backup path
            backup_path = self.storage_manager.create_backup_path(
                target_id, backup_type, operation.start_time, storage_location
            )
            
            # Perform the actual backup
            if target_id in ['influxdb_data']:
                # Use database-specific backup
                backup_results = await self.db_backup_manager.backup_influxdb(backup_path)
            elif target_id in ['mysql_data']:
                backup_results = await self.db_backup_manager.backup_mysql(backup_path)
            else:
                # Standard file system backup
                backup_results = await self.perform_filesystem_backup(
                    target.source_paths, backup_path, target.exclude_patterns,
                    target.compression, target.encryption
                )
            
            # Update operation record
            operation.backup_path = backup_path
            operation.source_size = estimated_size
            operation.backup_size = backup_results.get('backup_size', 0)
            operation.file_count = backup_results.get('file_count', 0)
            operation.compression_ratio = backup_results.get('compression_ratio', 0.0)
            operation.checksum = backup_results.get('checksum', '')
            
            # Verify backup if requested
            if target.verification and backup_results.get('status') == 'success':
                verification_result = await self.verify_backup(backup_path, operation.checksum)
                operation.verification_result = verification_result
            
            # Execute post-backup commands
            if target.post_backup_commands:
                await self.execute_commands(target.post_backup_commands, "post-backup")
            
            operation.status = BackupStatus.COMPLETED if backup_results.get('status') == 'success' else BackupStatus.FAILED
            operation.end_time = datetime.utcnow()
            
            # Update statistics
            self.update_backup_statistics(operation)
            
            # Store metrics
            await self.store_backup_metrics(operation)
            
            # Send notification
            await self.send_backup_notification(operation, target)
            
            logger.info(f"Backup completed for {target.name}: {operation.status.value}")
            
            return operation
            
        except Exception as e:
            operation.status = BackupStatus.FAILED
            operation.error_message = str(e)
            operation.end_time = datetime.utcnow()
            
            logger.error(f"Backup failed for {target.name}: {e}")
            
            # Store error metrics
            await self.store_backup_metrics(operation)
            
            return operation
    
    async def estimate_backup_size(self, source_paths: List[str]) -> int:
        """Estimate backup size"""
        total_size = 0
        
        for path_str in source_paths:
            path = Path(path_str)
            if path.exists():
                if path.is_file():
                    total_size += path.stat().st_size
                elif path.is_dir():
                    for file_path in path.rglob('*'):
                        if file_path.is_file():
                            try:
                                total_size += file_path.stat().st_size
                            except (OSError, PermissionError):
                                continue
        
        return total_size
    
    async def perform_filesystem_backup(self, source_paths: List[str], backup_path: str,
                                      exclude_patterns: List[str] = None,
                                      compression: bool = True, encryption: bool = True) -> Dict[str, Any]:
        """Perform filesystem backup"""
        try:
            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create tar command
            tar_cmd = ['tar']
            
            if compression:
                tar_cmd.append('-czf')
            else:
                tar_cmd.append('-cf')
            
            tar_cmd.append(str(backup_file))
            
            # Add exclusion patterns
            if exclude_patterns:
                for pattern in exclude_patterns:
                    tar_cmd.extend(['--exclude', pattern])
            
            # Add source paths
            valid_sources = []
            for path_str in source_paths:
                if Path(path_str).exists():
                    valid_sources.append(path_str)
                else:
                    logger.warning(f"Source path does not exist: {path_str}")
            
            if not valid_sources:
                return {'status': 'failed', 'error': 'No valid source paths'}
            
            tar_cmd.extend(valid_sources)
            
            # Execute backup
            start_time = time.time()
            result = await asyncio.create_subprocess_exec(
                *tar_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            backup_duration = time.time() - start_time
            
            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else "Backup command failed"
                return {'status': 'failed', 'error': error_msg}
            
            # Get backup file info
            backup_size = backup_file.stat().st_size
            
            # Calculate checksum
            checksum = await self.calculate_file_checksum(backup_file)
            
            # Count files (estimate)
            file_count = len(list(Path(valid_sources[0]).rglob('*'))) if valid_sources else 0
            
            # Calculate compression ratio
            source_size = await self.estimate_backup_size(valid_sources)
            compression_ratio = (1 - (backup_size / source_size)) if source_size > 0 else 0
            
            return {
                'status': 'success',
                'backup_size': backup_size,
                'file_count': file_count,
                'compression_ratio': compression_ratio,
                'checksum': checksum,
                'duration': backup_duration
            }
            
        except Exception as e:
            logger.error(f"Filesystem backup failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        try:
            hash_sha256 = hashlib.sha256()
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            
            return hash_sha256.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""
    
    async def verify_backup(self, backup_path: str, expected_checksum: str) -> bool:
        """Verify backup integrity"""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                return False
            
            # Recalculate checksum
            actual_checksum = await self.calculate_file_checksum(backup_file)
            
            # Compare checksums
            if actual_checksum != expected_checksum:
                logger.error(f"Backup verification failed: checksum mismatch for {backup_path}")
                return False
            
            # Test archive integrity
            if backup_path.endswith('.tar.gz'):
                test_cmd = ['tar', '-tzf', backup_path]
                result = await asyncio.create_subprocess_exec(
                    *test_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE
                )
                
                _, stderr = await result.communicate()
                
                if result.returncode != 0:
                    logger.error(f"Archive integrity test failed for {backup_path}")
                    return False
            
            logger.info(f"Backup verification successful for {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Backup verification error for {backup_path}: {e}")
            return False
    
    async def execute_commands(self, commands: List[str], phase: str):
        """Execute pre/post backup commands"""
        for i, command in enumerate(commands):
            try:
                logger.info(f"Executing {phase} command {i+1}: {command}")
                
                result = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await result.communicate()
                
                if result.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Command failed"
                    logger.error(f"{phase} command failed: {error_msg}")
                    # Continue with other commands even if one fails
                
            except Exception as e:
                logger.error(f"Error executing {phase} command: {e}")
    
    def update_backup_statistics(self, operation: BackupOperation):
        """Update backup statistics"""
        self.stats['total_backups'] += 1
        
        if operation.status == BackupStatus.COMPLETED:
            self.stats['successful_backups'] += 1
        else:
            self.stats['failed_backups'] += 1
        
        if operation.backup_size > 0:
            self.stats['total_backup_size'] += operation.backup_size
        
        self.stats['last_backup_time'] = operation.end_time
        
        # Calculate average backup time
        if operation.end_time:
            duration = (operation.end_time - operation.start_time).total_seconds()
            current_avg = self.stats['average_backup_time']
            total_backups = self.stats['total_backups']
            
            self.stats['average_backup_time'] = ((current_avg * (total_backups - 1)) + duration) / total_backups
    
    async def store_backup_metrics(self, operation: BackupOperation):
        """Store backup metrics in InfluxDB"""
        if not self.influxdb_client:
            return
        
        try:
            duration = 0
            if operation.end_time:
                duration = (operation.end_time - operation.start_time).total_seconds()
            
            points = [{
                'measurement': 'backup_operations',
                'tags': {
                    'operation_id': operation.operation_id,
                    'target_id': operation.target_id,
                    'backup_type': operation.backup_type.value,
                    'status': operation.status.value
                },
                'fields': {
                    'duration_seconds': duration,
                    'source_size_bytes': operation.source_size,
                    'backup_size_bytes': operation.backup_size,
                    'compression_ratio': operation.compression_ratio,
                    'file_count': operation.file_count,
                    'verification_result': operation.verification_result,
                    'success': 1 if operation.status == BackupStatus.COMPLETED else 0
                },
                'time': operation.start_time
            }]
            
            self.influxdb_client.write_points(points)
            
        except Exception as e:
            logger.error(f"Failed to store backup metrics: {e}")
    
    async def send_backup_notification(self, operation: BackupOperation, target: BackupTarget):
        """Send backup completion notification"""
        try:
            from collections.ml_analytics.secrets_helper import get_slack_webhook
            webhook_url = get_slack_webhook()
            
            if webhook_url:
                # Determine color based on status
                color = 'good' if operation.status == BackupStatus.COMPLETED else 'danger'
                
                # Format backup size
                backup_size_mb = operation.backup_size / (1024 * 1024) if operation.backup_size > 0 else 0
                
                message = {
                    'text': f'📦 Backup {"Completed" if operation.status == BackupStatus.COMPLETED else "Failed"}',
                    'attachments': [
                        {
                            'color': color,
                            'fields': [
                                {'title': 'Target', 'value': target.name, 'short': True},
                                {'title': 'Type', 'value': operation.backup_type.value, 'short': True},
                                {'title': 'Status', 'value': operation.status.value.upper(), 'short': True},
                                {'title': 'Size', 'value': f'{backup_size_mb:.1f} MB', 'short': True},
                                {'title': 'Duration', 'value': f'{(operation.end_time - operation.start_time).total_seconds():.0f}s' if operation.end_time else 'N/A', 'short': True},
                                {'title': 'Verified', 'value': '✅' if operation.verification_result else '❌', 'short': True}
                            ]
                        }
                    ]
                }
                
                if operation.error_message:
                    message['attachments'][0]['fields'].append({
                        'title': 'Error',
                        'value': operation.error_message[:200],
                        'short': False
                    })
                
                await asyncio.to_thread(requests.post, webhook_url, json=message, timeout=10)
                
        except Exception as e:
            logger.error(f"Failed to send backup notification: {e}")
    
    async def cleanup_old_backups(self):
        """Clean up old backups based on retention policies"""
        logger.info("Starting backup cleanup process")
        
        for target_id, target in self.backup_targets.items():
            try:
                await self.cleanup_target_backups(target)
            except Exception as e:
                logger.error(f"Error cleaning up backups for {target_id}: {e}")
    
    async def cleanup_target_backups(self, target: BackupTarget):
        """Clean up backups for specific target based on retention policy"""
        # Implementation would depend on retention policy
        # For now, implement basic cleanup (keep last 30 backups)
        
        for location_id, location_config in self.storage_manager.storage_locations.items():
            base_path = Path(location_config['path']) / target.target_id
            if not base_path.exists():
                continue
            
            # Find all backup files for this target
            backup_files = []
            for backup_file in base_path.rglob(f"{target.target_id}_*.tar.gz"):
                backup_files.append((backup_file, backup_file.stat().st_mtime))
            
            # Sort by modification time (newest first)
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            # Keep only the most recent backups based on retention policy
            keep_count = 30  # Default retention
            
            if target.retention_policy == BackupRetentionPolicy.DAILY_7_WEEKLY_4_MONTHLY_12:
                keep_count = 7  # Simplified - keep daily for 7 days
            elif target.retention_policy == BackupRetentionPolicy.HOURLY_24_DAILY_7_WEEKLY_4:
                keep_count = 24  # Keep hourly for 24 hours
            
            # Delete old backups
            for backup_file, _ in backup_files[keep_count:]:
                try:
                    backup_file.unlink()
                    logger.info(f"Deleted old backup: {backup_file}")
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup_file}: {e}")
    
    async def run_backup_scheduler(self):
        """Run backup scheduler"""
        while self.running:
            try:
                # Check if any backups are due (simplified scheduling)
                current_time = datetime.utcnow()
                
                for target_id, target in self.backup_targets.items():
                    # Get last backup time for this target
                    last_backup = None
                    for op in reversed(self.backup_operations):
                        if op.target_id == target_id and op.status == BackupStatus.COMPLETED:
                            last_backup = op.end_time
                            break
                    
                    # Check if backup is due (simplified - check every 24 hours)
                    if not last_backup or (current_time - last_backup) > timedelta(hours=24):
                        logger.info(f"Scheduling backup for {target.name}")
                        await self.backup_queue.put(target_id)
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in backup scheduler: {e}")
                await asyncio.sleep(600)  # Wait 10 minutes before retrying
    
    async def process_backup_queue(self):
        """Process backup queue"""
        while self.running:
            try:
                # Get backup task from queue
                target_id = await self.backup_queue.get()
                
                # Perform backup
                operation = await self.perform_backup(target_id)
                
                # Mark task as done
                self.backup_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing backup queue: {e}")
                await asyncio.sleep(60)
    
    def get_backup_statistics(self) -> Dict[str, Any]:
        """Get current backup statistics"""
        return {
            'backup_targets': len(self.backup_targets),
            'recent_operations': len(self.backup_operations),
            'storage_locations': len(self.storage_manager.storage_locations),
            'recovery_plans': len(self.recovery_plans),
            'statistics': self.stats,
            'queue_size': self.backup_queue.qsize() if hasattr(self.backup_queue, 'qsize') else 0
        }
    
    async def start_disaster_recovery(self):
        """Start the disaster recovery system"""
        logger.info("Starting Disaster Recovery Orchestrator")
        self.running = True
        
        # Start processing tasks
        tasks = [
            asyncio.create_task(self.run_backup_scheduler()),
            asyncio.create_task(self.process_backup_queue())
        ]
        
        # Perform initial backup assessment
        await self.cleanup_old_backups()
        
        # Run disaster recovery tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_disaster_recovery(self):
        """Stop the disaster recovery system"""
        logger.info("Stopping Disaster Recovery Orchestrator")
        self.running = False

def main():
    """Main entry point for Disaster Recovery Orchestrator"""
    orchestrator = DisasterRecoveryOrchestrator()
    
    try:
        asyncio.run(orchestrator.start_disaster_recovery())
    except KeyboardInterrupt:
        logger.info("Disaster recovery orchestrator stopped by user")
    except Exception as e:
        logger.error(f"Disaster recovery orchestrator error: {e}")

if __name__ == "__main__":
    main()
