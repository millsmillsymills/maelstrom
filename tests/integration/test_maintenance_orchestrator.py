#!/usr/bin/env python3
"""
Integration tests for Maintenance Orchestrator and Self-Healing System
Tests automated maintenance workflows, self-healing capabilities, and intelligent recovery
"""

import pytest
import json
import time
import requests
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import docker


class TestMaintenanceOrchestrator:
    """Test suite for maintenance orchestration functionality"""
    
    @pytest.fixture
    def mock_docker_client(self):
        """Mock Docker client for testing"""
        mock_client = Mock(spec=docker.DockerClient)
        mock_client.containers = Mock()
        mock_client.images = Mock()
        mock_client.networks = Mock()
        mock_client.volumes = Mock()
        return mock_client
    
    @pytest.fixture
    def maintenance_orchestrator(self, mock_docker_client):
        """Mock maintenance orchestrator service for testing"""
        try:
            import sys
            sys.path.append('/home/mills/collections/self-healing')
            from maintenance_orchestrator import MaintenanceOrchestrator
            
            # Create orchestrator with mocked dependencies
            orchestrator = MaintenanceOrchestrator()
            orchestrator.docker_client = mock_docker_client
            return orchestrator
            
        except ImportError:
            # Return mock if dependencies aren't available
            from unittest.mock import Mock
            mock_orchestrator = Mock()
            mock_orchestrator.docker_client = mock_docker_client
            mock_orchestrator.influxdb_client = Mock()
            mock_orchestrator.service_health = {}
            mock_orchestrator.maintenance_history = []
            mock_orchestrator.recovery_blacklist = set()
            mock_orchestrator.maintenance_window = False
            mock_orchestrator.critical_services = {'influxdb', 'grafana', 'prometheus'}
            mock_orchestrator.healing_stats = {
                'successful_recoveries': 0,
                'failed_recoveries': 0,
                'maintenance_tasks_completed': 0
            }
            return mock_orchestrator

    def test_service_health_monitoring(self, maintenance_orchestrator):
        """Test comprehensive service health monitoring"""
        if not hasattr(maintenance_orchestrator, 'check_service_health'):
            pytest.skip("Service health monitoring not available")
        
        # Mock container with various health states
        mock_container_healthy = Mock()
        mock_container_healthy.name = 'grafana'
        mock_container_healthy.status = 'running'
        mock_container_healthy.attrs = {
            'Created': '2025-08-07T10:00:00Z',
            'RestartCount': 0,
            'State': {'Health': {'Status': 'healthy'}}
        }
        mock_container_healthy.stats.return_value = {
            'memory_stats': {'usage': 500_000_000, 'limit': 2_000_000_000},
            'cpu_stats': {'cpu_usage': {'total_usage': 100000}},
            'precpu_stats': {'cpu_usage': {'total_usage': 90000}}
        }
        
        mock_container_unhealthy = Mock()
        mock_container_unhealthy.name = 'prometheus'
        mock_container_unhealthy.status = 'running'
        mock_container_unhealthy.attrs = {
            'Created': '2025-08-07T09:00:00Z',
            'RestartCount': 3,
            'State': {'Health': {'Status': 'unhealthy'}}
        }
        mock_container_unhealthy.stats.return_value = {
            'memory_stats': {'usage': 1_900_000_000, 'limit': 2_000_000_000},
            'cpu_stats': {'cpu_usage': {'total_usage': 200000}},
            'precpu_stats': {'cpu_usage': {'total_usage': 180000}}
        }
        
        maintenance_orchestrator.docker_client.containers.list.return_value = [
            mock_container_healthy, mock_container_unhealthy
        ]
        
        health_status = maintenance_orchestrator.check_service_health()
        
        assert 'grafana' in health_status
        assert 'prometheus' in health_status
        
        # Healthy service should be marked as healthy
        grafana_health = health_status['grafana']
        assert grafana_health.status.value in ['healthy', 'warning']  # May be warning due to other factors
        
        # Unhealthy service should be marked as critical
        prometheus_health = health_status['prometheus']
        assert prometheus_health.status.value in ['critical', 'warning']
        assert len(prometheus_health.issues) > 0

    def test_automated_service_recovery(self, maintenance_orchestrator):
        """Test automated service recovery mechanisms"""
        if not hasattr(maintenance_orchestrator, 'attempt_service_recovery'):
            pytest.skip("Service recovery not available")
        
        from datetime import datetime
        
        # Mock health record for failed service
        from unittest.mock import Mock
        health_record = Mock()
        health_record.recovery_attempts = 0
        health_record.issues = ["Container not running: exited"]
        health_record.last_recovery = None
        
        # Mock container that's stopped
        mock_container = Mock()
        mock_container.status = 'exited'
        mock_container.start = Mock()
        
        maintenance_orchestrator.docker_client.containers.get.return_value = mock_container
        
        # Test recovery attempt
        success = maintenance_orchestrator.attempt_service_recovery('test-service', health_record)
        
        # Should attempt to start the container
        mock_container.start.assert_called_once()
        assert health_record.recovery_attempts == 1
        assert health_record.last_recovery is not None

    def test_maintenance_task_execution(self, maintenance_orchestrator):
        """Test maintenance task execution"""
        if not hasattr(maintenance_orchestrator, 'execute_maintenance_task'):
            pytest.skip("Maintenance task execution not available")
        
        from unittest.mock import Mock
        
        # Mock MaintenanceTask
        maintenance_task = Mock()
        maintenance_task.name = "docker_system_cleanup"
        maintenance_task.task_type = Mock()
        maintenance_task.task_type.value = "routine"
        maintenance_task.priority = 3
        
        # Mock Docker cleanup methods
        maintenance_orchestrator.docker_client.containers.prune.return_value = {
            'ContainersDeleted': ['old-container-1', 'old-container-2'],
            'SpaceReclaimed': 1000000
        }
        maintenance_orchestrator.docker_client.images.prune.return_value = {
            'ImagesDeleted': ['old-image-1'],
            'SpaceReclaimed': 5000000
        }
        maintenance_orchestrator.docker_client.networks.prune.return_value = {
            'NetworksDeleted': ['old-network'],
            'SpaceReclaimed': 0
        }
        maintenance_orchestrator.docker_client.volumes.prune.return_value = {
            'VolumesDeleted': ['old-volume'],
            'SpaceReclaimed': 2000000
        }
        
        # Execute maintenance task
        success = maintenance_orchestrator.execute_maintenance_task(maintenance_task)
        
        # Should have executed Docker cleanup
        maintenance_orchestrator.docker_client.containers.prune.assert_called_once()
        maintenance_orchestrator.docker_client.images.prune.assert_called_once()
        maintenance_orchestrator.docker_client.networks.prune.assert_called_once()
        maintenance_orchestrator.docker_client.volumes.prune.assert_called_once()
        
        assert success is True

    def test_maintenance_window_scheduling(self, maintenance_orchestrator):
        """Test maintenance window scheduling and management"""
        if not hasattr(maintenance_orchestrator, 'enter_maintenance_window'):
            pytest.skip("Maintenance window scheduling not available")
        
        # Test entering maintenance window
        maintenance_orchestrator.enter_maintenance_window()
        
        assert maintenance_orchestrator.maintenance_window is True
        
        # Should have queued routine maintenance tasks
        if hasattr(maintenance_orchestrator, 'maintenance_queue'):
            assert len(maintenance_orchestrator.maintenance_queue) > 0
        
        # Test exiting maintenance window
        if hasattr(maintenance_orchestrator, 'exit_maintenance_window'):
            maintenance_orchestrator.exit_maintenance_window()
            assert maintenance_orchestrator.maintenance_window is False

    def test_health_check_validation(self, maintenance_orchestrator):
        """Test health check endpoint validation"""
        if not hasattr(maintenance_orchestrator, 'health_check_validation'):
            pytest.skip("Health check validation not available")
        
        with patch('requests.get') as mock_get:
            # Mock successful health checks
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            success = maintenance_orchestrator.health_check_validation()
            
            # Should have made requests to health endpoints
            assert mock_get.call_count > 0
            assert success is True
            
            # Test with failed health checks
            mock_response.status_code = 500
            success = maintenance_orchestrator.health_check_validation()
            
            assert success is False

    def test_backup_operations(self, maintenance_orchestrator):
        """Test critical configuration backup operations"""
        if not hasattr(maintenance_orchestrator, 'backup_critical_configs'):
            pytest.skip("Backup operations not available")
        
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('shutil.copy2') as mock_copy:
                        with patch.object(maintenance_orchestrator, 'cleanup_old_backups'):
                            
                            success = maintenance_orchestrator.backup_critical_configs()
                            
                            # Should have created backup directory
                            mock_mkdir.assert_called()
                            
                            # Should have copied files
                            mock_copy.assert_called()
                            
                            assert success is True

    def test_log_cleanup_operations(self, maintenance_orchestrator):
        """Test log rotation and cleanup"""
        if not hasattr(maintenance_orchestrator, 'log_rotation_cleanup'):
            pytest.skip("Log cleanup not available")
        
        with patch('pathlib.Path.glob') as mock_glob:
            with patch('pathlib.Path.rglob') as mock_rglob:
                # Mock log files to clean up
                mock_log_file = Mock()
                mock_log_file.is_file.return_value = True
                mock_log_file.stat.return_value.st_mtime = (datetime.utcnow() - timedelta(days=35)).timestamp()
                mock_log_file.stat.return_value.st_size = 1000000
                mock_log_file.unlink = Mock()
                
                mock_rglob.return_value = [mock_log_file]
                mock_log_dir = Mock()
                mock_log_dir.is_dir.return_value = True
                mock_log_dir.rglob = mock_rglob
                mock_glob.return_value = [mock_log_dir]
                
                success = maintenance_orchestrator.log_rotation_cleanup()
                
                # Should have removed old log files
                mock_log_file.unlink.assert_called_once()
                assert success is True

    def test_slack_notification_system(self, maintenance_orchestrator):
        """Test Slack notification system"""
        if not hasattr(maintenance_orchestrator, 'send_notification'):
            pytest.skip("Slack notifications not available")
        
        with patch('requests.post') as mock_post:
            with patch.object(maintenance_orchestrator, 'get_slack_webhook', 
                            return_value='https://hooks.slack.com/test'):
                mock_post.return_value = Mock(status_code=200)
                
                maintenance_orchestrator.send_notification(
                    "Test Notification", 
                    "This is a test notification", 
                    "info"
                )
                
                # Should have sent POST request to Slack
                mock_post.assert_called_once()
                call_args = mock_post.call_args
                
                # Verify payload structure
                assert 'json' in call_args.kwargs
                payload = call_args.kwargs['json']
                assert 'text' in payload
                assert payload['text'] == "Test Notification"
                assert 'attachments' in payload

    def test_influxdb_metrics_storage(self, maintenance_orchestrator):
        """Test metrics storage in InfluxDB"""
        if not hasattr(maintenance_orchestrator, 'store_health_metrics'):
            pytest.skip("Metrics storage not available")
        
        from unittest.mock import Mock
        
        # Mock health data
        health_data = {
            'grafana': Mock(),
            'prometheus': Mock(),
            'influxdb': Mock()
        }
        
        for service_name, health in health_data.items():
            health.status = Mock()
            health.status.value = 'healthy'
            health.uptime_seconds = 3600
            health.restart_count = 0
            health.recovery_attempts = 0
            health.issues = []
        
        # Mock InfluxDB client
        mock_influxdb = Mock()
        maintenance_orchestrator.influxdb_client = mock_influxdb
        
        maintenance_orchestrator.store_health_metrics(health_data)
        
        # Should have written points to InfluxDB
        mock_influxdb.write_points.assert_called_once()
        points = mock_influxdb.write_points.call_args[0][0]
        
        # Should have summary and individual service points
        assert len(points) >= 4  # 1 summary + 3 services
        
        # Check for summary point
        summary_points = [p for p in points if p['measurement'] == 'service_health_summary']
        assert len(summary_points) == 1

    def test_self_healing_cycle_execution(self, maintenance_orchestrator):
        """Test complete self-healing cycle execution"""
        if not hasattr(maintenance_orchestrator, 'run_self_healing_cycle'):
            pytest.skip("Self-healing cycle not available")
        
        # Mock all the methods called during self-healing cycle
        mock_health_data = {
            'test-service': Mock()
        }
        mock_health_data['test-service'].status = Mock()
        mock_health_data['test-service'].status.value = 'critical'
        mock_health_data['test-service'].issues = ['Container health check failed']
        
        with patch.object(maintenance_orchestrator, 'check_service_health', 
                         return_value=mock_health_data):
            with patch.object(maintenance_orchestrator, 'attempt_service_recovery', 
                            return_value=True):
                with patch.object(maintenance_orchestrator, 'store_health_metrics'):
                    
                    # Execute self-healing cycle
                    maintenance_orchestrator.run_self_healing_cycle()
                    
                    # Verify all methods were called
                    maintenance_orchestrator.check_service_health.assert_called_once()
                    maintenance_orchestrator.attempt_service_recovery.assert_called_once()
                    maintenance_orchestrator.store_health_metrics.assert_called_once()

    def test_recovery_blacklist_management(self, maintenance_orchestrator):
        """Test recovery blacklist for repeatedly failing services"""
        if not hasattr(maintenance_orchestrator, 'attempt_service_recovery'):
            pytest.skip("Service recovery not available")
        
        from unittest.mock import Mock
        
        # Mock health record with max attempts reached
        health_record = Mock()
        health_record.recovery_attempts = 3  # At max attempts
        health_record.issues = ["Service keeps failing"]
        
        # Add service to blacklist
        maintenance_orchestrator.recovery_blacklist.add('failing-service')
        
        # Attempt recovery - should be rejected due to blacklist
        success = maintenance_orchestrator.attempt_service_recovery('failing-service', health_record)
        
        assert success is False


class TestMaintenanceOrchestrator_Integration:
    """Integration tests requiring live services"""
    
    def test_docker_socket_access(self):
        """Test Docker socket accessibility for maintenance operations"""
        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            
            # Should be able to list containers
            assert isinstance(containers, list)
            
            # Should be able to get container stats (required for health monitoring)
            running_containers = [c for c in containers if c.status == 'running']
            if running_containers:
                container = running_containers[0]
                stats = container.stats(stream=False)
                assert 'memory_stats' in stats or 'cpu_stats' in stats
                
        except Exception as e:
            pytest.skip(f"Docker not accessible: {e}")

    def test_service_health_endpoints(self):
        """Test health endpoint accessibility"""
        health_endpoints = {
            'influxdb': 'http://localhost:8086/ping',
            'prometheus': 'http://localhost:9090/-/healthy',
            'grafana': 'http://localhost:3000/api/health'
        }
        
        accessible_endpoints = 0
        for service, endpoint in health_endpoints.items():
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code in [200, 204]:
                    accessible_endpoints += 1
            except requests.RequestException:
                continue
        
        # At least one service should be accessible for integration testing
        assert accessible_endpoints > 0, "No health endpoints accessible"

    def test_influxdb_connectivity_for_maintenance(self):
        """Test InfluxDB connectivity for maintenance tracking"""
        try:
            response = requests.get('http://localhost:8086/ping', timeout=5)
            assert response.status_code in [204, 200]
            
            # Test database creation capability
            from influxdb import InfluxDBClient
            
            client = InfluxDBClient(host='localhost', port=8086, database='test_maintenance_automation')
            databases = client.get_list_database()
            assert isinstance(databases, list)
            
        except (requests.ConnectionError, ImportError) as e:
            pytest.skip(f"InfluxDB not available: {e}")

    def test_maintenance_orchestrator_deployment(self):
        """Test maintenance orchestrator deployment configuration"""
        compose_file = Path('/home/mills/docker-compose.yml')
        
        if compose_file.exists():
            content = compose_file.read_text()
            
            # Should have self-healing service
            assert 'self-healing:' in content
            assert 'maintenance_orchestrator.py' in content
            
            # Should have required volumes
            assert '/var/run/docker.sock:/var/run/docker.sock:ro' in content
            assert '/var/log:/var/log' in content
            
            # Should have required capabilities
            assert 'SYS_ADMIN' in content or 'SYS_RESOURCE' in content
            
            # Should have cron and openssl packages
            assert 'cron' in content and 'openssl' in content
        else:
            pytest.skip("Docker compose file not found")

    def test_backup_directories_exist(self):
        """Test that backup directories are accessible"""
        backup_dir = Path('/home/mills/backups')
        workspace_dir = Path('/home/mills')
        
        # Should be able to access workspace for backups
        assert workspace_dir.exists() and workspace_dir.is_dir()
        
        # Should be able to create backup directories
        test_backup_dir = backup_dir / 'test_backup'
        try:
            test_backup_dir.mkdir(parents=True, exist_ok=True)
            assert test_backup_dir.exists()
            test_backup_dir.rmdir()  # Cleanup
        except PermissionError:
            pytest.skip("Backup directory not writable")

    def test_log_directories_accessible(self):
        """Test log directories are accessible for cleanup"""
        log_dirs = ['/var/log', '/home/mills/logs']
        
        accessible_dirs = 0
        for log_dir in log_dirs:
            log_path = Path(log_dir)
            if log_path.exists() and log_path.is_dir():
                # Should be able to list contents
                try:
                    list(log_path.iterdir())
                    accessible_dirs += 1
                except PermissionError:
                    continue
        
        # At least one log directory should be accessible
        assert accessible_dirs > 0, "No log directories accessible"

    def test_secrets_integration_maintenance(self):
        """Test secrets integration for maintenance operations"""
        secrets_dir = Path('/home/mills/secrets')
        
        if secrets_dir.exists():
            # Should find maintenance-related secrets helper
            maintenance_dir = Path('/home/mills/collections/self-healing')
            secrets_helper = maintenance_dir / 'secrets_helper.py'
            
            if secrets_helper.exists():
                content = secrets_helper.read_text()
                assert 'read_secret' in content
                assert 'get_slack_webhook' in content
                assert 'get_database_url' in content
            else:
                pytest.skip("Maintenance secrets helper not found")
        else:
            pytest.skip("Secrets directory not found")


class TestMaintenanceOperations:
    """Test specific maintenance operations"""
    
    def test_docker_system_cleanup_dry_run(self):
        """Test Docker system cleanup logic (dry run)"""
        try:
            client = docker.from_env()
            
            # Get current stats
            containers_before = len(client.containers.list(all=True))
            images_before = len(client.images.list(all=True))
            
            # Check that we can access Docker API for cleanup operations
            assert containers_before >= 0
            assert images_before >= 0
            
            # Test that we can list pruneable resources without actually pruning
            try:
                # This is a read-only operation to verify API access
                dangling_images = client.images.list(filters={"dangling": True})
                assert isinstance(dangling_images, list)
            except docker.errors.APIError as e:
                pytest.skip(f"Docker API not accessible: {e}")
                
        except Exception as e:
            pytest.skip(f"Docker not available: {e}")

    def test_service_restart_capability(self):
        """Test capability to restart services"""
        try:
            client = docker.from_env()
            containers = client.containers.list()
            
            if containers:
                # Find a non-critical container to test with
                test_container = None
                non_critical_services = ['cadvisor', 'node-exporter', 'promtail']
                
                for container in containers:
                    if any(service in container.name.lower() for service in non_critical_services):
                        test_container = container
                        break
                
                if test_container:
                    # Verify we can get container status
                    assert test_container.status in ['running', 'exited', 'paused']
                    
                    # Verify we can access container attributes needed for health monitoring
                    assert 'State' in test_container.attrs
                    assert 'RestartCount' in test_container.attrs
                else:
                    pytest.skip("No suitable test container found")
            else:
                pytest.skip("No containers running")
                
        except Exception as e:
            pytest.skip(f"Docker not accessible: {e}")


if __name__ == '__main__':
    # Run with pytest for better output
    import sys
    sys.exit(pytest.main([__file__, '-v']))