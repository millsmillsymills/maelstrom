#!/usr/bin/env python3
import time
import logging
import json
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LightweightMLAnalytics:
    def __init__(self):
        self.prometheus_url = "http://prometheus:9090"
        
    def simple_anomaly_detection(self, values):
        """Simple statistical anomaly detection"""
        if len(values) < 3:
            return []
        
        mean_val = sum(values) / len(values)
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        anomalies = []
        for i, val in enumerate(values):
            if abs(val - mean_val) > 2 * std_dev:  # 2-sigma rule
                anomalies.append(i)
        
        return anomalies
    
    def collect_basic_metrics(self):
        """Collect basic metrics from Prometheus"""
        try:
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': 'up'},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return len(data['data']['result'])
            return 0
        except:
            return 0
    
    def run_analysis(self):
        """Run lightweight analysis"""
        logger.info("Starting lightweight ML analytics")
        
        while True:
            try:
                metrics_count = self.collect_basic_metrics()
                logger.info(f"Monitoring {metrics_count} services")
                
                # Sleep for 15 minutes
                time.sleep(900)
                
            except KeyboardInterrupt:
                logger.info("ML Analytics stopped")
                break
            except Exception as e:
                logger.error(f"Analysis error: {e}")
                time.sleep(300)

if __name__ == "__main__":
    analytics = LightweightMLAnalytics()
    analytics.run_analysis()
