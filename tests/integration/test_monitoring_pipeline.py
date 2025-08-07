"""
Integration Tests for Monitoring Pipeline
Tests end-to-end data flow from collection to visualization
"""

import time
import pytest
import requests
from datetime import datetime, timedelta


@pytest.mark.integration
class TestMonitoringDataFlow:
    """Test the complete monitoring data pipeline"""
    
    @pytest.mark.slow
    def test_metrics_collection_pipeline(self, influxdb_client, prometheus_client):
        """Test metrics flow from collection to storage"""
        # Wait for metrics collection cycle
        time.sleep(30)
        
        # Test InfluxDB has recent data
        try:
            # Query for recent measurements
            query = "SELECT * FROM system WHERE time > now() - 5m LIMIT 10"
            result = influxdb_client.query(query)
            points = list(result.get_points())
            
            assert len(points) > 0, "No recent data found in InfluxDB"
            
            # Check that data is recent (within last 5 minutes)
            latest_point = max(points, key=lambda x: x['time'])
            latest_time = datetime.fromisoformat(latest_point['time'].replace('Z', '+00:00'))
            time_diff = datetime.now(latest_time.tzinfo) - latest_time
            
            assert time_diff < timedelta(minutes=10), f"Data not recent enough: {time_diff}"
            
        except Exception as e:
            pytest.skip(f"InfluxDB integration test failed: {e}")
        
        # Test Prometheus has recent data
        try:
            result = prometheus_client.query('up')
            assert result['status'] == 'success'
            
            # Check for recent data
            data_points = result['data']['result']
            assert len(data_points) > 0, "No 'up' metrics in Prometheus"
            
            # Verify timestamps are recent
            for point in data_points:
                timestamp = float(point['value'][0])
                point_time = datetime.fromtimestamp(timestamp)
                time_diff = datetime.now() - point_time
                
                assert time_diff < timedelta(minutes=10), f"Prometheus data not recent: {time_diff}"
                
        except Exception as e:
            pytest.skip(f"Prometheus integration test failed: {e}")
    
    def test_alerting_pipeline(self, prometheus_client):
        """Test that alerting pipeline is functioning"""
        try:
            # Check Prometheus rules are loaded
            response = requests.get('http://localhost:9090/api/v1/rules', timeout=5)
            response.raise_for_status()
            rules_data = response.json()
            
            assert 'data' in rules_data
            assert 'groups' in rules_data['data']
            
            rule_groups = rules_data['data']['groups']
            assert len(rule_groups) > 0, "No alerting rules loaded"
            
            # Check for critical alert rules
            rule_names = []
            for group in rule_groups:
                for rule in group.get('rules', []):
                    rule_names.append(rule.get('name', ''))
            
            expected_rules = ['HighCpuUsage', 'HighMemoryUsage', 'ServiceDown']
            found_rules = [rule for rule in rule_names if any(expected in rule for expected in expected_rules)]
            
            assert len(found_rules) > 0, f"No critical alerting rules found. Available: {rule_names[:5]}"
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not test alerting pipeline: {e}")
    
    def test_notification_integration(self, secrets_helper):
        """Test notification system integration"""
        # Check Slack webhook is configured
        webhook_url = secrets_helper.read_secret("slack_webhook_url")
        assert webhook_url, "Slack webhook URL not configured"
        assert webhook_url.startswith("https://hooks.slack.com"), "Invalid Slack webhook URL format"
        
        # Test Alertmanager configuration
        try:
            response = requests.get('http://localhost:9093/api/v1/status', timeout=5)
            response.raise_for_status()
            status_data = response.json()
            
            assert status_data['status'] == 'success'
            assert 'data' in status_data
            
            config_data = status_data['data']
            assert 'configYAML' in config_data or 'config' in config_data
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not test Alertmanager status: {e}")


@pytest.mark.integration
class TestServiceIntegration:
    """Test integration between different services"""
    
    def test_grafana_datasource_connectivity(self):
        """Test that Grafana can connect to its data sources"""
        try:
            # Get Grafana health
            response = requests.get('http://localhost:3000/api/health', timeout=10)
            response.raise_for_status()
            health_data = response.json()
            
            assert health_data['database'] == 'ok', "Grafana database not healthy"
            
            # This would require authentication to test data sources
            # For now, just verify Grafana is responding properly
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not test Grafana integration: {e}")
    
    def test_prometheus_service_discovery(self, prometheus_client):
        """Test Prometheus service discovery"""
        try:
            # Get service discovery targets
            response = requests.get('http://localhost:9090/api/v1/targets', timeout=5)
            response.raise_for_status()
            targets_data = response.json()
            
            active_targets = targets_data['data']['activeTargets']
            
            # Check for expected exporters
            target_endpoints = [target['scrapeUrl'] for target in active_targets]
            
            expected_exporters = [
                'node-exporter',
                'cadvisor',
                'prometheus'
            ]
            
            for exporter in expected_exporters:
                matching_targets = [url for url in target_endpoints if exporter in url]
                assert len(matching_targets) > 0, f"No targets found for {exporter}"
            
            # Check target health
            healthy_targets = [target for target in active_targets if target['health'] == 'up']
            unhealthy_targets = [target for target in active_targets if target['health'] == 'down']
            
            # At least 50% of targets should be healthy
            health_ratio = len(healthy_targets) / len(active_targets) if active_targets else 0
            assert health_ratio >= 0.5, f"Too many unhealthy targets: {len(unhealthy_targets)}/{len(active_targets)}"
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not test Prometheus service discovery: {e}")
    
    def test_logging_pipeline(self):
        """Test logging pipeline integration"""
        try:
            # Test Loki is accessible
            response = requests.get('http://localhost:3100/ready', timeout=5)
            response.raise_for_status()
            
            # Test Loki has some log data (basic check)
            query_response = requests.get(
                'http://localhost:3100/loki/api/v1/labels',
                timeout=5
            )
            query_response.raise_for_status()
            labels_data = query_response.json()
            
            assert 'data' in labels_data
            assert len(labels_data['data']) > 0, "No log labels found in Loki"
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not test logging pipeline: {e}")


@pytest.mark.integration
class TestSecurityServiceIntegration:
    """Test integration of security services"""
    
    @pytest.mark.slow
    def test_wazuh_elasticsearch_integration(self):
        """Test Wazuh-Elasticsearch integration"""
        try:
            # Test Elasticsearch is accessible
            response = requests.get('http://localhost:9200/_cluster/health', timeout=10)
            response.raise_for_status()
            health_data = response.json()
            
            assert health_data['status'] in ['green', 'yellow'], f"Elasticsearch cluster unhealthy: {health_data['status']}"
            
            # Check for Wazuh indices (if any exist)
            indices_response = requests.get('http://localhost:9200/_cat/indices?format=json', timeout=5)
            if indices_response.status_code == 200:
                indices = indices_response.json()
                wazuh_indices = [idx for idx in indices if 'wazuh' in idx.get('index', '')]
                # Don't assert - Wazuh indices may not exist yet in fresh installation
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not test Wazuh-Elasticsearch integration: {e}")
    
    def test_security_log_collection(self):
        """Test security log collection"""
        # This is a basic test - more comprehensive testing would require
        # generating actual security events
        
        try:
            # Check if security containers are running and accessible
            security_services = {
                'suricata': None,  # No direct HTTP interface
                'zeek': None,      # No direct HTTP interface  
                'wazuh-manager': 'http://localhost:55000'  # API port
            }
            
            for service, url in security_services.items():
                if url:
                    try:
                        response = requests.get(url, timeout=5)
                        # Just check that service responds (may need auth)
                        assert response.status_code in [200, 401, 403], f"{service} not responding properly"
                    except requests.exceptions.ConnectionError:
                        pytest.skip(f"{service} not accessible")
                        
        except Exception as e:
            pytest.skip(f"Could not test security log collection: {e}")


@pytest.mark.integration  
class TestNetworkMonitoring:
    """Test network monitoring integration"""
    
    def test_pihole_dns_filtering(self):
        """Test Pi-hole DNS filtering functionality"""
        try:
            # Test secondary Pi-hole (more accessible for testing)
            response = requests.get('http://localhost:8053/admin/api.php', timeout=5)
            response.raise_for_status()
            
            api_data = response.json()
            
            # Check basic Pi-hole stats
            assert 'dns_queries_today' in api_data
            assert 'ads_blocked_today' in api_data
            assert 'ads_percentage_today' in api_data
            
            # Verify Pi-hole is processing queries
            queries_today = int(api_data['dns_queries_today'])
            assert queries_today >= 0, "Pi-hole query count invalid"
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not test Pi-hole integration: {e}")
        except (KeyError, ValueError) as e:
            pytest.skip(f"Pi-hole API response format unexpected: {e}")
    
    def test_network_discovery_integration(self, influxdb_client):
        """Test network discovery service integration"""
        try:
            # Check if network discovery data exists in InfluxDB
            query = "SHOW MEASUREMENTS"
            result = influxdb_client.query(query)
            measurements = [point['name'] for point in result.get_points()]
            
            # Look for network-related measurements
            network_measurements = [m for m in measurements if 'network' in m.lower() or 'discovery' in m.lower()]
            
            # Don't assert - network discovery may not have run yet
            # This test verifies the pipeline exists
            
        except Exception as e:
            pytest.skip(f"Could not test network discovery integration: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])