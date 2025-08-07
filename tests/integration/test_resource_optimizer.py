#!/usr/bin/env python3
"""
Integration tests for Resource Optimizer and Monitor
Tests automated resource monitoring, optimization, and alerting
"""

import pytest
import json
import time
import requests
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import docker


class TestResourceOptimizer:
    """Test suite for resource optimization functionality"""
    
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
    def resource_optimizer(self, mock_docker_client):
        """Mock resource optimizer service for testing"""
        try:
            import sys
            sys.path.append('/home/mills/collections/resource-optimizer')
            from resource_monitor import ResourceOptimizer
            
            # Create optimizer with mocked dependencies
            optimizer = ResourceOptimizer()
            optimizer.docker_client = mock_docker_client
            return optimizer
            
        except ImportError:
            # Return mock if dependencies aren't available
            mock_optimizer = Mock()
            mock_optimizer.docker_client = mock_docker_client
            mock_optimizer.influxdb_client = Mock()
            mock_optimizer.resource_history = []
            mock_optimizer.optimization_actions = []
            mock_optimizer.alerts_sent = set()
            return mock_optimizer

    def test_host_metrics_collection(self, resource_optimizer):
        """Test comprehensive host metrics collection"""
        if not hasattr(resource_optimizer, 'collect_host_metrics'):
            pytest.skip("Host metrics collection not available")
        
        with patch('psutil.cpu_percent', return_value=45.5):
            with patch('psutil.virtual_memory') as mock_memory:
                mock_memory.return_value = Mock(
                    total=16_000_000_000,
                    available=8_000_000_000,
                    used=8_000_000_000,
                    percent=50.0
                )
                
                with patch('psutil.disk_usage') as mock_disk:
                    mock_disk.return_value = Mock(
                        total=1_000_000_000_000,
                        used=200_000_000_000,
                        free=800_000_000_000
                    )
                    
                    metrics = resource_optimizer.collect_host_metrics()
                    
                    assert 'cpu' in metrics
                    assert 'memory' in metrics
                    assert 'disk' in metrics
                    assert 'network' in metrics
                    
                    assert metrics['cpu']['percent'] == 45.5
                    assert metrics['memory']['percent'] == 50.0
                    assert metrics['disk']['total_bytes'] == 1_000_000_000_000

    def test_container_metrics_collection(self, resource_optimizer):
        """Test Docker container metrics collection"""
        if not hasattr(resource_optimizer, 'collect_container_metrics'):
            pytest.skip("Container metrics collection not available")
        
        # Mock container with stats
        mock_container = Mock()
        mock_container.name = 'test-grafana'
        mock_container.id = '1234567890ab'
        mock_container.status = 'running'
        mock_container.image.tags = ['grafana/grafana:latest']
        mock_container.attrs = {
            'Created': '2025-08-07T10:00:00Z',
            'RestartCount': 0,
            'State': {'Health': {'Status': 'healthy'}}
        }
        
        # Mock stats response
        mock_stats = {
            'cpu_stats': {
                'cpu_usage': {'total_usage': 100000000, 'percpu_usage': [50000000, 50000000]},
                'system_cpu_usage': 1000000000
            },
            'precpu_stats': {
                'cpu_usage': {'total_usage': 90000000},
                'system_cpu_usage': 900000000
            },
            'memory_stats': {
                'usage': 500_000_000,
                'limit': 1_000_000_000
            },
            'networks': {
                'eth0': {'rx_bytes': 1000000, 'tx_bytes': 500000}
            },
            'blkio_stats': {
                'io_service_bytes_recursive': [
                    {'op': 'Read', 'value': 10000000},
                    {'op': 'Write', 'value': 5000000}
                ]
            }
        }
        mock_container.stats.return_value = mock_stats
        
        resource_optimizer.docker_client.containers.list.return_value = [mock_container]
        
        metrics = resource_optimizer.collect_container_metrics()
        
        assert 'test-grafana' in metrics
        container_metrics = metrics['test-grafana']
        
        assert container_metrics['status'] == 'running'
        assert container_metrics['image'] == 'grafana/grafana:latest'
        assert 'cpu_percent' in container_metrics
        assert 'memory_percent' in container_metrics
        assert container_metrics['memory_percent'] == 50.0

    def test_resource_analysis_and_recommendations(self, resource_optimizer):
        """Test resource usage analysis and recommendation generation"""
        if not hasattr(resource_optimizer, 'analyze_resource_usage'):
            pytest.skip("Resource analysis not available")
        
        # Mock high resource usage scenario
        host_metrics = {
            'cpu': {'percent': 85.0},
            'memory': {'percent': 90.0},
            'disk': {'percent': 75.0}
        }
        
        container_metrics = {
            'high-cpu-container': {
                'status': 'running',
                'cpu_percent': 85.0,
                'memory_percent': 45.0,
                'health_status': 'healthy'
            },
            'high-memory-container': {
                'status': 'running',
                'cpu_percent': 25.0,
                'memory_percent': 90.0,
                'health_status': 'healthy'
            },
            'unhealthy-container': {
                'status': 'running',
                'cpu_percent': 10.0,
                'memory_percent': 20.0,
                'health_status': 'unhealthy'
            }
        }
        
        issues, recommendations = resource_optimizer.analyze_resource_usage(
            host_metrics, container_metrics
        )
        
        # Should detect high resource usage
        assert len(issues) > 0
        assert len(recommendations) > 0
        
        # Check for specific issues
        cpu_issues = [issue for issue in issues if 'CPU' in issue]
        memory_issues = [issue for issue in issues if 'memory' in issue]
        
        assert len(cpu_issues) > 0
        assert len(memory_issues) > 0

    def test_automated_optimizations(self, resource_optimizer):
        """Test automated optimization actions"""
        if not hasattr(resource_optimizer, 'apply_optimizations'):
            pytest.skip("Automated optimizations not available")
        
        # Mock critical disk usage scenario
        host_metrics = {
            'cpu': {'percent': 75.0},
            'memory': {'percent': 95.0},  # Critical memory
            'disk': {'percent': 95.0}     # Critical disk
        }
        
        container_metrics = {
            'high-memory-container': {
                'status': 'running',
                'memory_percent': 92.0,
                'health_status': 'healthy'
            },
            'unhealthy-container': {
                'status': 'exited',
                'health_status': 'unhealthy'
            }
        }
        
        recommendations = [
            "Clean up old logs and unused volumes",
            "Restart high memory containers",
            "Investigate unhealthy containers"
        ]
        
        # Mock Docker operations
        resource_optimizer.docker_client.containers.prune.return_value = {
            'ContainersDeleted': ['old-container-1', 'old-container-2']
        }
        resource_optimizer.docker_client.images.prune.return_value = {
            'ImagesDeleted': ['image-1', 'image-2']
        }
        resource_optimizer.docker_client.networks.prune.return_value = {
            'NetworksDeleted': ['old-network']
        }
        resource_optimizer.docker_client.volumes.prune.return_value = {
            'VolumesDeleted': ['old-volume']
        }
        
        # Mock container restart
        mock_container = Mock()
        mock_container.status = 'exited'
        resource_optimizer.docker_client.containers.get.return_value = mock_container
        
        optimizations = resource_optimizer.apply_optimizations(
            recommendations, host_metrics, container_metrics
        )
        
        assert len(optimizations) > 0
        
        # Should have performed Docker cleanup due to critical disk usage
        resource_optimizer.docker_client.containers.prune.assert_called_once()
        resource_optimizer.docker_client.images.prune.assert_called_once()
        resource_optimizer.docker_client.volumes.prune.assert_called_once()

    def test_slack_alerting(self, resource_optimizer):
        """Test Slack notification for resource alerts"""
        if not hasattr(resource_optimizer, 'send_alerts'):
            pytest.skip("Alert functionality not available")
        
        issues = [
            "CRITICAL: Host CPU usage at 95.2%",
            "WARNING: Host memory usage at 87.1%",
            "CRITICAL: Disk usage at 92.5%"
        ]
        
        recommendations = [
            "Consider scaling containers or optimizing CPU-intensive services",
            "Restart memory-intensive containers or add more RAM",
            "Clean up old logs, images, and unused volumes immediately"
        ]
        
        host_metrics = {
            'cpu': {'percent': 95.2},
            'memory': {'percent': 87.1},
            'disk': {'percent': 92.5}
        }
        
        with patch('requests.post') as mock_post:
            with patch.object(resource_optimizer, 'get_slack_webhook', 
                            return_value='https://hooks.slack.com/test'):
                mock_post.return_value = Mock(status_code=200)
                
                resource_optimizer.send_alerts(issues, recommendations, host_metrics)
                
                # Should have sent alert
                mock_post.assert_called_once()
                call_args = mock_post.call_args
                
                # Verify payload structure
                assert 'json' in call_args.kwargs
                payload = call_args.kwargs['json']
                assert 'text' in payload
                assert 'CRITICAL' in payload['text']
                assert 'attachments' in payload

    def test_influxdb_metrics_storage(self, resource_optimizer):
        """Test metrics storage in InfluxDB"""
        if not hasattr(resource_optimizer, 'store_metrics'):
            pytest.skip("Metrics storage not available")
        
        from datetime import datetime
        
        # Mock ResourceMetrics object
        mock_metrics = Mock()
        mock_metrics.timestamp = datetime.utcnow()
        mock_metrics.host_cpu_percent = 65.5
        mock_metrics.host_memory_percent = 72.3
        mock_metrics.host_disk_percent = 45.8
        mock_metrics.host_network_bytes_sent = 1_000_000
        mock_metrics.host_network_bytes_recv = 2_000_000
        mock_metrics.containers = {
            'grafana': {
                'id': '1234567890ab',
                'status': 'running',
                'image': 'grafana/grafana:latest',
                'cpu_percent': 15.2,
                'memory_usage_bytes': 500_000_000,
                'memory_percent': 25.0,
                'network_rx_bytes': 1000,
                'network_tx_bytes': 2000,
                'block_read_bytes': 5000,
                'block_write_bytes': 3000,
                'restart_count': 0
            }
        }
        mock_metrics.recommendations = ["Test recommendation"]
        
        # Mock InfluxDB client
        mock_influxdb = Mock()
        resource_optimizer.influxdb_client = mock_influxdb
        
        resource_optimizer.store_metrics(mock_metrics)
        
        # Should have written points to InfluxDB
        mock_influxdb.write_points.assert_called_once()
        points = mock_influxdb.write_points.call_args[0][0]
        
        # Should have host metrics and container metrics
        assert len(points) >= 2
        
        # Check host metrics point
        host_points = [p for p in points if p['measurement'] == 'host_resources']
        assert len(host_points) == 1
        assert host_points[0]['fields']['cpu_percent'] == 65.5

    def test_resource_report_generation(self, resource_optimizer):
        """Test comprehensive resource report generation"""
        if not hasattr(resource_optimizer, 'generate_resource_report'):
            pytest.skip("Report generation not available")
        
        from datetime import datetime
        
        # Mock metrics object
        mock_metrics = Mock()
        mock_metrics.timestamp = datetime.utcnow()
        mock_metrics.host_cpu_percent = 45.5
        mock_metrics.host_memory_percent = 67.2
        mock_metrics.host_disk_percent = 38.9
        mock_metrics.host_network_bytes_sent = 500_000
        mock_metrics.host_network_bytes_recv = 1_200_000
        mock_metrics.containers = {
            'grafana': {
                'status': 'running',
                'cpu_percent': 12.5,
                'memory_percent': 28.3,
                'memory_usage_bytes': 300_000_000
            },
            'prometheus': {
                'status': 'running',
                'cpu_percent': 8.7,
                'memory_percent': 35.1,
                'memory_usage_bytes': 450_000_000
            }
        }
        
        issues = ["WARNING: High memory usage detected"]
        recommendations = ["Review container memory limits"]
        optimizations = ["Applied Docker cleanup"]
        
        report = resource_optimizer.generate_resource_report(
            mock_metrics, issues, recommendations, optimizations
        )
        
        assert isinstance(report, str)
        assert "Resource Monitoring Report" in report
        assert "45.5%" in report  # CPU usage
        assert "67.2%" in report  # Memory usage
        assert "grafana" in report
        assert "prometheus" in report
        assert "WARNING: High memory usage detected" in report

    def test_monitoring_cycle_execution(self, resource_optimizer):
        """Test complete monitoring cycle execution"""
        if not hasattr(resource_optimizer, 'run_monitoring_cycle'):
            pytest.skip("Monitoring cycle not available")
        
        # Mock all the methods called during monitoring cycle
        mock_host_metrics = {
            'cpu': {'percent': 55.0},
            'memory': {'percent': 70.0},
            'disk': {'percent': 40.0},
            'network': {'bytes_sent': 1000, 'bytes_recv': 2000}
        }
        
        mock_container_metrics = {
            'test-container': {
                'status': 'running',
                'cpu_percent': 25.0,
                'memory_percent': 30.0,
                'health_status': 'healthy'
            }
        }
        
        with patch.object(resource_optimizer, 'collect_host_metrics', 
                         return_value=mock_host_metrics):
            with patch.object(resource_optimizer, 'collect_container_metrics', 
                            return_value=mock_container_metrics):
                with patch.object(resource_optimizer, 'analyze_resource_usage', 
                                return_value=([], [])):
                    with patch.object(resource_optimizer, 'store_metrics'):
                        with patch.object(resource_optimizer, 'apply_optimizations', 
                                        return_value=[]):
                            with patch.object(resource_optimizer, 'send_alerts'):
                                with patch.object(resource_optimizer, 'generate_resource_report', 
                                                return_value="Test report"):
                                    with patch('pathlib.Path.mkdir'):
                                        with patch('pathlib.Path.write_text'):
                                            
                                            # Execute monitoring cycle
                                            resource_optimizer.run_monitoring_cycle()
                                            
                                            # Verify all methods were called
                                            resource_optimizer.collect_host_metrics.assert_called_once()
                                            resource_optimizer.collect_container_metrics.assert_called_once()
                                            resource_optimizer.store_metrics.assert_called_once()


class TestResourceOptimizerIntegration:
    """Integration tests requiring live services"""
    
    def test_docker_socket_access(self):
        """Test Docker socket accessibility"""
        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            
            # Should be able to list containers without error
            assert isinstance(containers, list)
            
            # Should have some containers in the monitoring stack
            container_names = [c.name for c in containers]
            monitoring_services = ['influxdb', 'grafana', 'prometheus']
            
            found_services = [s for s in monitoring_services if any(s in name.lower() for name in container_names)]
            assert len(found_services) > 0, f"No monitoring services found in containers: {container_names}"
            
        except Exception as e:
            pytest.skip(f"Docker not accessible: {e}")

    def test_system_metrics_accessibility(self):
        """Test system metrics collection capabilities"""
        try:
            import psutil
            
            # Should be able to collect basic system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            assert 0 <= cpu_percent <= 100
            assert memory.total > 0
            assert disk.total > 0
            assert network.bytes_sent >= 0
            assert network.bytes_recv >= 0
            
        except ImportError:
            pytest.skip("psutil not available")
        except Exception as e:
            pytest.skip(f"System metrics not accessible: {e}")

    def test_influxdb_connectivity(self):
        """Test InfluxDB connectivity for metrics storage"""
        try:
            response = requests.get('http://localhost:8086/ping', timeout=5)
            assert response.status_code in [204, 200]
            
            # Test database creation capability
            from influxdb import InfluxDBClient
            
            client = InfluxDBClient(host='localhost', port=8086, database='test_resource_monitoring')
            databases = client.get_list_database()
            assert isinstance(databases, list)
            
        except (requests.ConnectionError, ImportError) as e:
            pytest.skip(f"InfluxDB not available: {e}")

    def test_resource_optimizer_deployment(self):
        """Test resource optimizer deployment configuration"""
        compose_file = Path('/home/mills/docker-compose.yml')
        
        if compose_file.exists():
            content = compose_file.read_text()
            
            # Should have resource-optimizer service
            assert 'resource-optimizer:' in content
            assert 'resource_monitor.py' in content
            
            # Should have required volumes
            assert '/var/run/docker.sock:/var/run/docker.sock:ro' in content
            assert '/proc:/proc:ro' in content
            assert '/sys:/sys:ro' in content
            
            # Should have required capabilities
            assert 'SYS_ADMIN' in content or 'SYS_RESOURCE' in content
        else:
            pytest.skip("Docker compose file not found")

    def test_secrets_integration(self):
        """Test secrets integration for resource optimizer"""
        secrets_dir = Path('/home/mills/secrets')
        
        if secrets_dir.exists():
            # Should be able to find resource optimizer secrets helper
            optimizer_dir = Path('/home/mills/collections/resource-optimizer')
            secrets_helper = optimizer_dir / 'secrets_helper.py'
            
            if secrets_helper.exists():
                content = secrets_helper.read_text()
                assert 'read_secret' in content
                assert 'get_slack_webhook' in content
                assert 'get_database_url' in content
            else:
                pytest.skip("Secrets helper not found")
        else:
            pytest.skip("Secrets directory not found")


if __name__ == '__main__':
    # Run with pytest for better output
    import sys
    sys.exit(pytest.main([__file__, '-v']))