#!/usr/bin/env python3
import time
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
import json
import requests
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedMLAnalytics:
    def __init__(self):
        self.prometheus_url = "http://prometheus:9090"
        self.influxdb_url = "http://influxdb:8086"
        self.slack_webhook = None  # Configure if needed
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.scaler = StandardScaler()
        self.baseline_metrics = {}
        self.prediction_history = []
        
    def fetch_prometheus_metrics(self, query):
        """Fetch metrics from Prometheus"""
        try:
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': query},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return data['data']['result']
            return []
        except Exception as e:
            logger.error(f"Error fetching Prometheus metrics: {e}")
            return []
    
    def collect_system_metrics(self):
        """Collect comprehensive system metrics"""
        metrics = {}
        
        # CPU metrics
        cpu_data = self.fetch_prometheus_metrics('100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')
        if cpu_data:
            metrics['cpu_usage'] = [float(item['value'][1]) for item in cpu_data]
        
        # Memory metrics
        memory_data = self.fetch_prometheus_metrics('(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100')
        if memory_data:
            metrics['memory_usage'] = [float(item['value'][1]) for item in memory_data]
        
        # Disk metrics
        disk_data = self.fetch_prometheus_metrics('(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100')
        if disk_data:
            metrics['disk_usage'] = [float(item['value'][1]) for item in disk_data]
        
        # Network metrics
        network_data = self.fetch_prometheus_metrics('rate(node_network_receive_bytes_total[5m])')
        if network_data:
            metrics['network_rx'] = [float(item['value'][1]) for item in network_data]
        
        # Container metrics
        container_data = self.fetch_prometheus_metrics('rate(container_cpu_usage_seconds_total[5m]) * 100')
        if container_data:
            metrics['container_cpu'] = [float(item['value'][1]) for item in container_data]
        
        return metrics
    
    def perform_anomaly_detection(self, metrics):
        """Perform ML-based anomaly detection"""
        anomalies = {}
        
        for metric_name, values in metrics.items():
            if values and len(values) > 1:
                try:
                    # Prepare data for anomaly detection
                    data = np.array(values).reshape(-1, 1)
                    
                    # Fit and predict anomalies
                    anomaly_scores = self.anomaly_detector.fit_predict(data)
                    anomaly_indices = np.where(anomaly_scores == -1)[0]
                    
                    if len(anomaly_indices) > 0:
                        anomalies[metric_name] = {
                            'anomaly_count': len(anomaly_indices),
                            'anomaly_values': [values[i] for i in anomaly_indices],
                            'anomaly_severity': self.calculate_severity(values, anomaly_indices)
                        }
                        
                        logger.warning(f"Anomalies detected in {metric_name}: {len(anomaly_indices)} anomalies")
                    
                except Exception as e:
                    logger.error(f"Error in anomaly detection for {metric_name}: {e}")
        
        return anomalies
    
    def calculate_severity(self, values, anomaly_indices):
        """Calculate anomaly severity"""
        if not values or not anomaly_indices:
            return 'low'
        
        mean_val = np.mean(values)
        anomaly_values = [values[i] for i in anomaly_indices]
        max_deviation = max([abs(val - mean_val) for val in anomaly_values])
        
        if max_deviation > mean_val * 0.5:
            return 'high'
        elif max_deviation > mean_val * 0.2:
            return 'medium'
        else:
            return 'low'
    
    def predict_resource_exhaustion(self, metrics):
        """Predict potential resource exhaustion"""
        predictions = {}
        
        for metric_name, values in metrics.items():
            if values and len(values) >= 3:
                try:
                    # Simple linear trend analysis
                    x = np.arange(len(values))
                    y = np.array(values)
                    
                    # Calculate trend
                    trend = np.polyfit(x, y, 1)[0]
                    current_value = values[-1]
                    
                    if trend > 0 and current_value > 70:  # Increasing trend and high usage
                        # Predict when it might reach 95%
                        time_to_exhaustion = (95 - current_value) / trend if trend > 0 else float('inf')
                        
                        if time_to_exhaustion < 60:  # Less than 60 time units
                            predictions[metric_name] = {
                                'current_value': current_value,
                                'trend': trend,
                                'time_to_exhaustion': time_to_exhaustion,
                                'severity': 'critical' if time_to_exhaustion < 20 else 'warning'
                            }
                            
                            logger.warning(f"Resource exhaustion prediction for {metric_name}: {time_to_exhaustion:.1f} units")
                
                except Exception as e:
                    logger.error(f"Error in prediction for {metric_name}: {e}")
        
        return predictions
    
    def generate_insights(self, metrics, anomalies, predictions):
        """Generate actionable insights"""
        insights = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'metrics_collected': len(metrics),
                'anomalies_detected': len(anomalies),
                'predictions_made': len(predictions),
                'overall_health': 'healthy'
            },
            'anomalies': anomalies,
            'predictions': predictions,
            'recommendations': []
        }
        
        # Generate recommendations
        if anomalies:
            insights['summary']['overall_health'] = 'needs_attention'
            insights['recommendations'].append("Investigate detected anomalies immediately")
        
        if predictions:
            critical_predictions = [p for p in predictions.values() if p.get('severity') == 'critical']
            if critical_predictions:
                insights['summary']['overall_health'] = 'critical'
                insights['recommendations'].append("Take immediate action to prevent resource exhaustion")
        
        # Add specific recommendations
        for metric_name, anomaly in anomalies.items():
            if anomaly.get('anomaly_severity') == 'high':
                insights['recommendations'].append(f"High severity anomaly in {metric_name} - investigate infrastructure")
        
        for metric_name, prediction in predictions.items():
            if prediction.get('severity') == 'critical':
                insights['recommendations'].append(f"Critical: {metric_name} may exhaust in {prediction['time_to_exhaustion']:.1f} units")
        
        return insights
    
    def store_insights(self, insights):
        """Store insights for historical analysis"""
        try:
            # Store in local file for persistence
            insights_file = f"/tmp/ml_insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(insights_file, 'w') as f:
                json.dump(insights, f, indent=2)
            
            logger.info(f"Insights stored to {insights_file}")
            
            # Keep only last 100 insight files
            import glob
            import os
            insight_files = glob.glob('/tmp/ml_insights_*.json')
            if len(insight_files) > 100:
                # Remove oldest files
                insight_files.sort()
                for old_file in insight_files[:-100]:
                    os.remove(old_file)
            
        except Exception as e:
            logger.error(f"Error storing insights: {e}")
    
    def run_analysis_cycle(self):
        """Run one complete analysis cycle"""
        try:
            info("Starting ML analysis cycle")
            
            # Collect metrics
            metrics = self.collect_system_metrics()
            logger.info(f"Collected {len(metrics)} metric types")
            
            # Perform anomaly detection
            anomalies = self.perform_anomaly_detection(metrics)
            logger.info(f"Detected {len(anomalies)} metric types with anomalies")
            
            # Generate predictions
            predictions = self.predict_resource_exhaustion(metrics)
            logger.info(f"Generated {len(predictions)} resource exhaustion predictions")
            
            # Generate insights
            insights = self.generate_insights(metrics, anomalies, predictions)
            
            # Store insights
            self.store_insights(insights)
            
            # Log summary
            logger.info(f"Analysis complete - Health: {insights['summary']['overall_health']}")
            if insights['recommendations']:
                logger.warning(f"Recommendations: {'; '.join(insights['recommendations'])}")
            
            return insights
            
        except Exception as e:
            logger.error(f"Error in analysis cycle: {e}")
            return None
    
    def run_continuous_monitoring(self):
        """Run continuous ML monitoring"""
        logger.info("Starting Enhanced ML Analytics Service")
        
        cycle_count = 0
        while True:
            try:
                cycle_count += 1
                logger.info(f"Starting analysis cycle #{cycle_count}")
                
                insights = self.run_analysis_cycle()
                
                if insights and insights['summary']['overall_health'] == 'critical':
                    logger.critical("CRITICAL health status detected - immediate attention required")
                
                # Sleep for 10 minutes between cycles
                logger.info("Analysis cycle complete, sleeping for 10 minutes")
                time.sleep(600)
                
            except KeyboardInterrupt:
                logger.info("ML Analytics monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Sleep 1 minute before retry

def main():
    logger.info("Initializing Enhanced ML Analytics Service")
    analytics = EnhancedMLAnalytics()
    analytics.run_continuous_monitoring()

if __name__ == "__main__":
    main()
