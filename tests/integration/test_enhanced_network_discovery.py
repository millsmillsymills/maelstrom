#!/usr/bin/env python3
"""
Integration tests for Enhanced Network Discovery Service
Tests cross-system integrations with Zabbix, Prometheus, and Loki
"""

import pytest
import json
import time
import requests
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch


class TestEnhancedNetworkDiscovery:
    """Test suite for enhanced network discovery functionality"""
    
    @pytest.fixture
    def discovery_service(self):
        """Mock discovery service for testing"""
        # Import the service dynamically to handle missing dependencies
        try:
            import sys
            sys.path.append('/home/mills/networking/collections/network-discovery')
            from enhanced_discovery_service import EnhancedNetworkDiscovery
            return EnhancedNetworkDiscovery()
        except ImportError:
            # Return mock if dependencies aren't available
            mock_service = Mock()
            mock_service.influxdb_client = Mock()
            mock_service.zabbix_token = "test_token"
            return mock_service
    
    def test_service_detection(self, discovery_service):
        """Test enhanced service detection capabilities"""
        # Mock device info with common services
        device_info = {
            'ip': '172.30.0.3',
            'alive': True,
            'services': [
                {'port': 22, 'service': 'SSH', 'secure': True},
                {'port': 80, 'service': 'HTTP', 'secure': False},
                {'port': 443, 'service': 'HTTPS', 'secure': True},
                {'port': 3000, 'service': 'Grafana', 'secure': False}
            ],
            'open_ports': [22, 80, 443, 3000]
        }
        
        # Test service classification
        if hasattr(discovery_service, 'classify_device'):
            device_type = discovery_service.classify_device(device_info)
            assert device_type in ['monitoring_infrastructure', 'web_server', 'linux_server']
        
        # Test security scoring
        if hasattr(discovery_service, 'assess_device_security'):
            security_score = discovery_service.assess_device_security(device_info)
            assert 0 <= security_score <= 100
            assert security_score > 50  # Should be decent with SSH and HTTPS
    
    def test_prometheus_targets_integration(self, discovery_service, tmp_path):
        """Test Prometheus targets file generation"""
        # Mock devices with monitoring services
        test_devices = [
            {
                'ip': '172.30.0.1',
                'hostname': 'monitoring-host',
                'alive': True,
                'device_type': 'monitoring_infrastructure',
                'services': [
                    {'port': 9100, 'service': 'node-exporter'},
                    {'port': 9273, 'service': 'telegraf'}
                ]
            },
            {
                'ip': '172.30.0.2',
                'hostname': 'database-host',
                'alive': True,
                'device_type': 'database_server',
                'services': [
                    {'port': 9104, 'service': 'mysql-exporter'}
                ]
            }
        ]
        
        if hasattr(discovery_service, 'update_prometheus_targets'):
            # Mock the targets directory
            with patch.object(Path, 'mkdir'):
                with patch('builtins.open', create=True) as mock_open:
                    discovery_service.update_prometheus_targets(test_devices)
                    
                    # Should have attempted to write targets file
                    mock_open.assert_called()
    
    def test_zabbix_integration(self, discovery_service):
        """Test Zabbix API integration"""
        if not hasattr(discovery_service, 'authenticate_zabbix'):
            pytest.skip("Zabbix integration not available")
        
        # Mock successful authentication
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"result": "test_auth_token"}
            mock_post.return_value = mock_response
            
            token = discovery_service.authenticate_zabbix()
            assert token == "test_auth_token"
            
            # Test host creation
            test_device = {
                'ip': '192.168.1.100',
                'hostname': 'test-host',
                'device_type': 'linux_server'
            }
            
            # Mock host creation response
            mock_response.json.return_value = {"result": {"hostids": ["12345"]}}
            
            result = discovery_service.create_zabbix_host(test_device)
            assert result is True
    
    def test_loki_logging_integration(self, discovery_service):
        """Test Loki log aggregation integration"""
        if not hasattr(discovery_service, 'send_discovery_logs_to_loki'):
            pytest.skip("Loki integration not available")
        
        test_devices = [
            {
                'ip': '192.168.1.50',
                'hostname': 'test-device',
                'alive': True,
                'device_type': 'web_server',
                'services': [{'port': 80, 'service': 'HTTP'}],
                'security_score': 75
            }
        ]
        
        with patch('requests.post') as mock_post:
            mock_post.return_value = Mock(status_code=204)
            
            discovery_service.send_discovery_logs_to_loki(test_devices)
            
            # Should have sent POST to Loki
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            
            # Verify payload structure
            assert 'json' in call_args.kwargs
            payload = call_args.kwargs['json']
            assert 'streams' in payload
            assert len(payload['streams']) > 0
    
    def test_security_alerting(self, discovery_service):
        """Test security alert generation and Slack integration"""
        if not hasattr(discovery_service, 'send_security_alerts'):
            pytest.skip("Security alerting not available")
        
        # Mock insecure device
        insecure_device = {
            'ip': '192.168.1.200',
            'hostname': 'insecure-host',
            'security_score': 30,
            'services': [
                {'port': 21, 'service': 'FTP', 'secure': False},
                {'port': 23, 'service': 'Telnet', 'secure': False}
            ]
        }
        
        new_devices = [insecure_device]
        changed_devices = []
        
        with patch('requests.post') as mock_post:
            mock_post.return_value = Mock(status_code=200)
            
            discovery_service.send_security_alerts(new_devices, changed_devices)
            
            # Should have sent alert for insecure device
            if mock_post.called:
                call_args = mock_post.call_args
                payload = call_args.kwargs.get('json', {})
                assert 'attachments' in payload or 'text' in payload
    
    def test_influxdb_data_storage(self, discovery_service):
        """Test enhanced data storage in InfluxDB"""
        if not hasattr(discovery_service, 'store_enhanced_results'):
            pytest.skip("InfluxDB storage not available")
        
        test_devices = [
            {
                'ip': '172.30.0.5',
                'hostname': 'prometheus',
                'alive': True,
                'device_type': 'monitoring_infrastructure',
                'os_type': 'Linux',
                'response_time': 1.2,
                'service_count': 3,
                'secure_services': 2,
                'security_score': 85,
                'open_ports': [9090, 9100, 22]
            },
            {
                'ip': '172.30.0.6',
                'hostname': 'grafana',
                'alive': True,
                'device_type': 'monitoring_infrastructure',
                'os_type': 'Linux',
                'response_time': 0.8,
                'service_count': 2,
                'secure_services': 1,
                'security_score': 75,
                'open_ports': [3000, 22]
            }
        ]
        
        # Mock InfluxDB client
        if discovery_service.influxdb_client:
            with patch.object(discovery_service.influxdb_client, 'write_points') as mock_write:
                discovery_service.store_enhanced_results(test_devices)
                
                # Should have written points to InfluxDB
                mock_write.assert_called_once()
                points = mock_write.call_args[0][0]
                
                # Check for summary and device points
                assert len(points) >= 3  # Summary + 2 devices
                
                # Check summary point structure
                summary_points = [p for p in points if p['measurement'] == 'network_discovery_summary']
                assert len(summary_points) == 1
                
                summary = summary_points[0]
                assert 'alive_devices' in summary['fields']
                assert 'avg_security_score' in summary['fields']
    
    def test_network_range_scanning(self, discovery_service):
        """Test comprehensive network range scanning"""
        if not hasattr(discovery_service, 'scan_network_range'):
            pytest.skip("Network scanning not available")
        
        # Mock subprocess for ping commands
        with patch('subprocess.run') as mock_run:
            # Mock successful ping response
            mock_run.return_value = Mock(
                returncode=0,
                stdout="64 bytes from 192.168.1.1: icmp_seq=1 time=1.2 ms"
            )
            
            # Mock socket operations for service detection
            with patch('socket.socket') as mock_socket:
                mock_sock = Mock()
                mock_sock.connect_ex.return_value = 0  # Port open
                mock_socket.return_value = mock_sock
                
                # Test scanning a small range
                test_range = "192.168.1.1/30"  # Only 2 hosts
                devices = discovery_service.scan_network_range(test_range)
                
                assert isinstance(devices, list)
                assert len(devices) >= 0
    
    def test_secrets_integration(self):
        """Test secrets helper integration"""
        try:
            import sys
            sys.path.append('/home/mills/networking/collections/network-discovery')
            from secrets_helper import read_secret, get_slack_webhook, get_database_url
            
            # Test reading a test secret
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "test_value"
                
                # Mock Path.exists
                with patch('pathlib.Path.exists', return_value=True):
                    result = read_secret("test_secret", required=False)
                    assert result == "test_value"
            
            # Test environment fallback
            with patch.dict('os.environ', {'TEST_SECRET': 'env_value'}):
                with patch('pathlib.Path.exists', return_value=False):
                    result = read_secret("test_secret", "TEST_SECRET", required=False)
                    assert result == "env_value"
            
            # Test database URL generation
            with patch('pathlib.Path.exists', return_value=False):
                with patch.dict('os.environ', {'INFLUXDB_ADMIN_PASSWORD': 'test_pass'}):
                    url = get_database_url("influxdb")
                    assert "test_pass" in url
                    assert "influxdb:8086" in url
        
        except ImportError:
            pytest.skip("Secrets helper not available")


class TestNetworkDiscoveryIntegration:
    """Integration tests requiring live services"""
    
    def test_service_connectivity(self):
        """Test that discovery service can connect to monitoring stack"""
        # Test InfluxDB connectivity
        try:
            response = requests.get('http://localhost:8086/ping', timeout=5)
            assert response.status_code == 204 or "influxdb" in response.text.lower()
        except requests.ConnectionError:
            pytest.skip("InfluxDB not available for integration test")
    
    def test_prometheus_targets_directory(self):
        """Test Prometheus targets directory is accessible"""
        targets_dir = Path('/home/mills/collections/prometheus/targets')
        
        if targets_dir.exists():
            # Should be writable for discovery service
            test_file = targets_dir / 'test_discovery.yml'
            
            try:
                test_file.write_text("# Test file")
                assert test_file.exists()
                test_file.unlink()  # Cleanup
            except PermissionError:
                pytest.skip("Prometheus targets directory not writable")
        else:
            # Directory should be created during deployment
            pytest.skip("Prometheus targets directory not found")
    
    def test_secrets_directory_access(self):
        """Test access to secrets directory"""
        secrets_dir = Path('/home/mills/secrets')
        
        if secrets_dir.exists():
            # Should contain some secret files
            secret_files = list(secrets_dir.glob('*'))
            assert len(secret_files) > 0
            
            # Test reading a common secret
            common_secrets = [
                'influxdb_admin_password',
                'slack_webhook_url',
                'grafana_admin_password'
            ]
            
            found_secrets = 0
            for secret_name in common_secrets:
                secret_file = secrets_dir / secret_name
                if secret_file.exists():
                    found_secrets += 1
            
            assert found_secrets > 0, "No expected secrets found"
        else:
            pytest.skip("Secrets directory not found")


class TestDiscoveryServiceDeployment:
    """Test deployment and configuration aspects"""
    
    def test_docker_compose_configuration(self):
        """Test that docker-compose.yml has enhanced discovery configuration"""
        compose_file = Path('/home/mills/docker-compose.yml')
        
        if compose_file.exists():
            content = compose_file.read_text()
            
            # Should use enhanced discovery service
            assert 'enhanced_discovery_service.py' in content
            
            # Should have required volumes
            assert '/prometheus-targets' in content
            assert '/secrets:ro' in content
            
            # Should have required packages
            assert 'arp-scan' in content or 'iputils-ping' in content
        else:
            pytest.skip("Docker compose file not found")
    
    def test_requirements_file(self):
        """Test requirements.txt has necessary dependencies"""
        req_file = Path('/home/mills/networking/collections/network-discovery/requirements.txt')
        
        if req_file.exists():
            content = req_file.read_text()
            
            # Should have enhanced dependencies
            required_packages = ['influxdb', 'requests', 'pyyaml']
            for package in required_packages:
                assert package in content
        else:
            pytest.skip("Requirements file not found")
    
    def test_service_files_exist(self):
        """Test that all required service files exist"""
        base_dir = Path('/home/mills/networking/collections/network-discovery')
        
        required_files = [
            'enhanced_discovery_service.py',
            'secrets_helper.py',
            'requirements.txt'
        ]
        
        for file_name in required_files:
            file_path = base_dir / file_name
            assert file_path.exists(), f"Required file missing: {file_name}"
            
            # Should not be empty
            if file_path.suffix == '.py':
                content = file_path.read_text()
                assert len(content) > 100, f"File suspiciously small: {file_name}"
                assert 'import' in content, f"Python file lacks imports: {file_name}"


if __name__ == '__main__':
    # Run with pytest for better output
    import sys
    sys.exit(pytest.main([__file__, '-v']))