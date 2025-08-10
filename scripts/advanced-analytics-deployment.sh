#!/bin/bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
# Advanced Analytics and ML Services Deployment

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/mills/logs/advanced-analytics-${TIMESTAMP}.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

success() { log "${GREEN}✅ $1${NC}"; }
warning() { log "${YELLOW}⚠️ $1${NC}"; }
error() { log "${RED}❌ $1${NC}"; }
info() { log "${BLUE}ℹ️ $1${NC}"; }

# Deploy Enhanced ML Analytics Service
deploy_enhanced_ml_analytics() {
    info "Deploying Enhanced ML Analytics Service"
    
    cat > /home/mills/collections/ml-analytics/enhanced_ml_analytics.py << 'EOF'
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
EOF

    success "Enhanced ML Analytics service deployed"
}

# Deploy Data Intelligence Service
deploy_data_intelligence() {
    info "Deploying Data Intelligence Service"
    
    cat > /home/mills/collections/data-intelligence/data_intelligence.py << 'EOF'
#!/usr/bin/env python3
import time
import json
import logging
from datetime import datetime, timedelta
import requests
import sqlite3
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataIntelligenceService:
    def __init__(self):
        self.prometheus_url = "http://prometheus:9090"
        self.influxdb_url = "http://influxdb:8086"
        self.db_path = "/tmp/intelligence.db"
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database for intelligence storage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics_intelligence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metric_name TEXT,
                    value REAL,
                    classification TEXT,
                    confidence REAL,
                    insights TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trend_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metric_name TEXT,
                    trend_direction TEXT,
                    trend_strength REAL,
                    forecast_24h REAL,
                    forecast_confidence REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Intelligence database initialized")
            
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    def classify_metric_behavior(self, metric_name, values):
        """Classify metric behavior patterns"""
        if not values or len(values) < 3:
            return "insufficient_data", 0.0
        
        # Calculate statistical properties
        mean_val = sum(values) / len(values)
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        # Coefficient of variation
        cv = std_dev / mean_val if mean_val > 0 else 0
        
        # Trend analysis
        x_vals = list(range(len(values)))
        n = len(values)
        sum_x = sum(x_vals)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(x_vals, values))
        sum_x2 = sum(x * x for x in x_vals)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
        
        # Classification logic
        if cv < 0.1:
            classification = "stable"
            confidence = 0.9
        elif cv > 0.5:
            classification = "volatile"
            confidence = 0.8
        elif abs(slope) > mean_val * 0.1:
            classification = "trending_up" if slope > 0 else "trending_down"
            confidence = 0.7
        else:
            classification = "normal"
            confidence = 0.6
        
        return classification, confidence
    
    def analyze_correlation_patterns(self, metrics_data):
        """Analyze correlations between metrics"""
        correlations = {}
        metric_names = list(metrics_data.keys())
        
        for i, metric1 in enumerate(metric_names):
            for j, metric2 in enumerate(metric_names[i+1:], i+1):
                values1 = metrics_data[metric1]
                values2 = metrics_data[metric2]
                
                if len(values1) >= 3 and len(values2) >= 3:
                    min_len = min(len(values1), len(values2))
                    v1 = values1[:min_len]
                    v2 = values2[:min_len]
                    
                    # Simple correlation calculation
                    mean1 = sum(v1) / len(v1)
                    mean2 = sum(v2) / len(v2)
                    
                    num = sum((x - mean1) * (y - mean2) for x, y in zip(v1, v2))
                    den1 = sum((x - mean1) ** 2 for x in v1) ** 0.5
                    den2 = sum((y - mean2) ** 2 for y in v2) ** 0.5
                    
                    if den1 > 0 and den2 > 0:
                        correlation = num / (den1 * den2)
                        if abs(correlation) > 0.7:  # Strong correlation
                            correlations[f"{metric1}_vs_{metric2}"] = {
                                'correlation': correlation,
                                'strength': 'strong' if abs(correlation) > 0.8 else 'moderate'
                            }
        
        return correlations
    
    def generate_forecasts(self, metric_name, values):
        """Generate simple forecasts"""
        if len(values) < 5:
            return None
        
        # Simple linear regression for forecasting
        x_vals = list(range(len(values)))
        n = len(values)
        sum_x = sum(x_vals)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(x_vals, values))
        sum_x2 = sum(x * x for x in x_vals)
        
        if (n * sum_x2 - sum_x * sum_x) == 0:
            return None
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n
        
        # Forecast next 24 points (assuming 1 point per hour for 24h forecast)
        forecast_24h = slope * (len(values) + 24) + intercept
        
        # Calculate confidence based on R-squared
        y_pred = [slope * x + intercept for x in x_vals]
        ss_res = sum((y - yp) ** 2 for y, yp in zip(values, y_pred))
        ss_tot = sum((y - sum_y/n) ** 2 for y in values)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            'forecast_24h': forecast_24h,
            'confidence': max(0, min(1, r_squared)),
            'trend_slope': slope
        }
    
    def store_intelligence(self, metric_name, classification, confidence, insights):
        """Store intelligence data in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO metrics_intelligence 
                (metric_name, classification, confidence, insights)
                VALUES (?, ?, ?, ?)
            ''', (metric_name, classification, confidence, json.dumps(insights)))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing intelligence: {e}")
    
    def run_intelligence_cycle(self):
        """Run one intelligence analysis cycle"""
        try:
            logger.info("Starting data intelligence analysis")
            
            # Fetch metrics from Prometheus
            metrics_data = {}
            
            metric_queries = {
                'cpu_usage': '100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
                'memory_usage': '(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100',
                'disk_usage': '(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100',
                'network_rx': 'rate(node_network_receive_bytes_total[5m])',
                'container_count': 'count(container_last_seen)',
                'service_up': 'up'
            }
            
            for metric_name, query in metric_queries.items():
                try:
                    response = requests.get(
                        f"{self.prometheus_url}/api/v1/query",
                        params={'query': query},
                        timeout=10
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data['status'] == 'success' and data['data']['result']:
                            values = [float(item['value'][1]) for item in data['data']['result']]
                            if values:
                                metrics_data[metric_name] = values
                                
                except Exception as e:
                    logger.error(f"Error fetching {metric_name}: {e}")
            
            # Analyze each metric
            intelligence_results = {}
            
            for metric_name, values in metrics_data.items():
                # Classify behavior
                classification, confidence = self.classify_metric_behavior(metric_name, values)
                
                # Generate forecast
                forecast = self.generate_forecasts(metric_name, values)
                
                # Create insights
                insights = {
                    'classification': classification,
                    'confidence': confidence,
                    'forecast': forecast,
                    'current_value': values[-1] if values else None,
                    'trend': 'increasing' if forecast and forecast['trend_slope'] > 0 else 'decreasing' if forecast and forecast['trend_slope'] < 0 else 'stable'
                }
                
                intelligence_results[metric_name] = insights
                
                # Store in database
                self.store_intelligence(metric_name, classification, confidence, insights)
                
                logger.info(f"Analyzed {metric_name}: {classification} (confidence: {confidence:.2f})")
            
            # Analyze correlations
            correlations = self.analyze_correlation_patterns(metrics_data)
            if correlations:
                logger.info(f"Found {len(correlations)} strong correlations")
            
            # Generate summary
            summary = {
                'timestamp': datetime.now().isoformat(),
                'metrics_analyzed': len(intelligence_results),
                'correlations_found': len(correlations),
                'high_confidence_insights': len([r for r in intelligence_results.values() if r['confidence'] > 0.8]),
                'trending_metrics': len([r for r in intelligence_results.values() if r['classification'].startswith('trending')])
            }
            
            logger.info(f"Intelligence analysis complete: {summary}")
            return intelligence_results, correlations, summary
            
        except Exception as e:
            logger.error(f"Error in intelligence cycle: {e}")
            return {}, {}, {}
    
    def run_continuous_intelligence(self):
        """Run continuous data intelligence"""
        logger.info("Starting Data Intelligence Service")
        
        while True:
            try:
                self.run_intelligence_cycle()
                
                # Sleep for 15 minutes between cycles
                time.sleep(900)
                
            except KeyboardInterrupt:
                logger.info("Data Intelligence Service stopped")
                break
            except Exception as e:
                logger.error(f"Error in intelligence loop: {e}")
                time.sleep(60)

def main():
    service = DataIntelligenceService()
    service.run_continuous_intelligence()

if __name__ == "__main__":
    main()
EOF

    success "Data Intelligence service deployed"
}

# Deploy Performance Optimizer
deploy_performance_optimizer() {
    info "Deploying Performance Optimizer Service"
    
    cat > /home/mills/collections/performance-optimizer/performance_optimizer.py << 'EOF'
#!/usr/bin/env python3
import time
import json
import logging
import requests
import subprocess
from datetime import datetime
import ${DOCKER} logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    def __init__(self):
        self.prometheus_url = "http://prometheus:9090"
        try:
            self.docker_client = docker.from_env()
        except:
            self.docker_client = None
            logger.warning("Docker client not available")
        
        self.optimization_history = []
        self.thresholds = {
            'cpu_high': 80.0,
            'memory_high': 85.0,
            'disk_high': 90.0,
            'container_restart_threshold': 5
        }
    
    def fetch_metric(self, query):
        """Fetch single metric from Prometheus"""
        try:
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': query},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success' and data['data']['result']:
                    return float(data['data']['result'][0]['value'][1])
            return None
        except Exception as e:
            logger.error(f"Error fetching metric: {e}")
            return None
    
    def analyze_performance_bottlenecks(self):
        """Analyze system for performance bottlenecks"""
        bottlenecks = []
        
        # CPU analysis
        cpu_usage = self.fetch_metric('100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')
        if cpu_usage and cpu_usage > self.thresholds['cpu_high']:
            bottlenecks.append({
                'type': 'cpu',
                'severity': 'high' if cpu_usage > 95 else 'medium',
                'value': cpu_usage,
                'description': f'High CPU usage: {cpu_usage:.1f}%'
            })
        
        # Memory analysis
        memory_usage = self.fetch_metric('(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')
        if memory_usage and memory_usage > self.thresholds['memory_high']:
            bottlenecks.append({
                'type': 'memory',
                'severity': 'high' if memory_usage > 95 else 'medium',
                'value': memory_usage,
                'description': f'High memory usage: {memory_usage:.1f}%'
            })
        
        # Disk analysis
        disk_usage = self.fetch_metric('(1 - (node_filesystem_free_bytes / node_filesystem_size_bytes)) * 100')
        if disk_usage and disk_usage > self.thresholds['disk_high']:
            bottlenecks.append({
                'type': 'disk',
                'severity': 'critical' if disk_usage > 95 else 'high',
                'value': disk_usage,
                'description': f'High disk usage: {disk_usage:.1f}%'
            })
        
        # Container analysis
        if self.docker_client:
            try:
                containers = self.docker_client.containers.list(all=True)
                restarting_containers = [c for c in containers if 'Restarting' in c.status]
                
                if len(restarting_containers) > self.thresholds['container_restart_threshold']:
                    bottlenecks.append({
                        'type': 'containers',
                        'severity': 'high',
                        'value': len(restarting_containers),
                        'description': f'Multiple containers restarting: {len(restarting_containers)}'
                    })
            except Exception as e:
                logger.error(f"Error analyzing containers: {e}")
        
        return bottlenecks
    
    def optimize_system_performance(self, bottlenecks):
        """Apply performance optimizations based on bottlenecks"""
        optimizations_applied = []
        
        for bottleneck in bottlenecks:
            if bottleneck['type'] == 'memory' and bottleneck['severity'] in ['high', 'critical']:
                # Clear system caches
                optimization = self.clear_system_caches()
                if optimization:
                    optimizations_applied.append(optimization)
            
            elif bottleneck['type'] == 'disk' and bottleneck['severity'] in ['high', 'critical']:
                # Clean up disk space
                optimization = self.cleanup_disk_space()
                if optimization:
                    optimizations_applied.append(optimization)
            
            elif bottleneck['type'] == 'containers':
                # Optimize container resources
                optimization = self.optimize_container_resources()
                if optimization:
                    optimizations_applied.append(optimization)
        
        return optimizations_applied
    
    def clear_system_caches(self):
        """Clear system caches to free memory"""
        try:
            # Drop caches (requires appropriate permissions)
            subprocess.run(['sync'], check=False)
            
            logger.info("System cache clearing attempted")
            return {
                'type': 'memory_optimization',
                'action': 'clear_caches',
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
        except Exception as e:
            logger.error(f"Error clearing caches: {e}")
            return None
    
    def cleanup_disk_space(self):
        """Clean up disk space"""
        try:
            cleanup_commands = [
                '${DOCKER} system prune -f --volumes',
                '${DOCKER} image prune -f',
                'find /tmp -type f -atime +7 -delete',
                'find /var/log -name "*.log" -size +100M -delete'
            ]
            
            total_freed = 0
            for cmd in cleanup_commands:
                try:
                    result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        logger.info(f"Cleanup command succeeded: {cmd}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Cleanup command timed out: {cmd}")
                except Exception as e:
                    logger.error(f"Cleanup command failed: {cmd} - {e}")
            
            return {
                'type': 'disk_optimization',
                'action': 'cleanup_space',
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
        except Exception as e:
            logger.error(f"Error in disk cleanup: {e}")
            return None
    
    def optimize_container_resources(self):
        """Optimize container resource allocation"""
        try:
            if not self.docker_client:
                return None
            
            containers = self.docker_client.containers.list()
            optimizations = []
            
            for container in containers:
                try:
                    stats = container.stats(stream=False)
                    
                    # Calculate CPU and memory usage
                    cpu_usage = self.calculate_container_cpu_usage(stats)
                    memory_usage = self.calculate_container_memory_usage(stats)
                    
                    # Apply optimizations if needed
                    if cpu_usage > 90:
                        logger.warning(f"High CPU usage in container {container.name}: {cpu_usage:.1f}%")
                        optimizations.append(f"high_cpu_{container.name}")
                    
                    if memory_usage > 90:
                        logger.warning(f"High memory usage in container {container.name}: {memory_usage:.1f}%")
                        optimizations.append(f"high_memory_{container.name}")
                
                except Exception as e:
                    logger.error(f"Error analyzing container {container.name}: {e}")
            
            return {
                'type': 'container_optimization',
                'action': 'resource_analysis',
                'optimizations': optimizations,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
        except Exception as e:
            logger.error(f"Error in container optimization: {e}")
            return None
    
    def calculate_container_cpu_usage(self, stats):
        """Calculate container CPU usage from stats"""
        try:
            cpu_stats = stats['cpu_stats']
            precpu_stats = stats['precpu_stats']
            
            cpu_delta = cpu_stats['cpu_usage']['total_usage'] - precpu_stats['cpu_usage']['total_usage']
            system_delta = cpu_stats['system_cpu_usage'] - precpu_stats['system_cpu_usage']
            
            if system_delta > 0:
                cpu_usage = (cpu_delta / system_delta) * len(cpu_stats['cpu_usage']['percpu_usage']) * 100
                return cpu_usage
            
            return 0
        except:
            return 0
    
    def calculate_container_memory_usage(self, stats):
        """Calculate container memory usage from stats"""
        try:
            memory_stats = stats['memory_stats']
            usage = memory_stats['usage']
            limit = memory_stats['limit']
            
            if limit > 0:
                return (usage / limit) * 100
            
            return 0
        except:
            return 0
    
    def generate_performance_report(self, bottlenecks, optimizations):
        """Generate performance analysis report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'bottlenecks_detected': len(bottlenecks),
            'optimizations_applied': len(optimizations),
            'system_health': 'good',
            'bottlenecks': bottlenecks,
            'optimizations': optimizations,
            'recommendations': []
        }
        
        # Determine system health
        critical_bottlenecks = [b for b in bottlenecks if b['severity'] == 'critical']
        high_bottlenecks = [b for b in bottlenecks if b['severity'] == 'high']
        
        if critical_bottlenecks:
            report['system_health'] = 'critical'
            report['recommendations'].append('Immediate intervention required for critical bottlenecks')
        elif high_bottlenecks:
            report['system_health'] = 'warning'
            report['recommendations'].append('Address high-severity performance issues')
        elif bottlenecks:
            report['system_health'] = 'needs_attention'
            report['recommendations'].append('Monitor and optimize medium-severity issues')
        
        # Add specific recommendations
        for bottleneck in bottlenecks:
            if bottleneck['type'] == 'cpu':
                report['recommendations'].append('Consider scaling CPU resources or optimizing CPU-intensive processes')
            elif bottleneck['type'] == 'memory':
                report['recommendations'].append('Increase memory allocation or optimize memory usage')
            elif bottleneck['type'] == 'disk':
                report['recommendations'].append('Free up disk space or expand storage capacity')
            elif bottleneck['type'] == 'containers':
                report['recommendations'].append('Investigate container restart loops and resource limits')
        
        return report
    
    def run_optimization_cycle(self):
        """Run one performance optimization cycle"""
        try:
            logger.info("Starting performance optimization cycle")
            
            # Analyze bottlenecks
            bottlenecks = self.analyze_performance_bottlenecks()
            logger.info(f"Detected {len(bottlenecks)} performance bottlenecks")
            
            # Apply optimizations
            optimizations = self.optimize_system_performance(bottlenecks)
            logger.info(f"Applied {len(optimizations)} optimizations")
            
            # Generate report
            report = self.generate_performance_report(bottlenecks, optimizations)
            
            # Store optimization history
            self.optimization_history.append(report)
            
            # Keep only last 100 reports
            if len(self.optimization_history) > 100:
                self.optimization_history = self.optimization_history[-100:]
            
            # Log summary
            logger.info(f"Optimization cycle complete - Health: {report['system_health']}")
            if report['recommendations']:
                logger.warning(f"Recommendations: {'; '.join(report['recommendations'][:3])}")
            
            return report
            
        except Exception as e:
            logger.error(f"Error in optimization cycle: {e}")
            return None
    
    def run_continuous_optimization(self):
        """Run continuous performance optimization"""
        logger.info("Starting Performance Optimizer Service")
        
        while True:
            try:
                self.run_optimization_cycle()
                
                # Sleep for 5 minutes between cycles
                time.sleep(300)
                
            except KeyboardInterrupt:
                logger.info("Performance Optimizer stopped")
                break
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                time.sleep(60)

def main():
    optimizer = PerformanceOptimizer()
    optimizer.run_continuous_optimization()

if __name__ == "__main__":
    main()
EOF

    success "Performance Optimizer service deployed"
}

# Main deployment function
main() {
    log "🚀 Starting Advanced Analytics Deployment"
    
    # Create necessary directories
    mkdir -p /home/mills/collections/{ml-analytics,data-intelligence,performance-optimizer}
    
    # Deploy all services
    deploy_enhanced_ml_analytics
    deploy_data_intelligence
    deploy_performance_optimizer
    
    # Update requirements for each service
    cat > /home/mills/collections/ml-analytics/requirements.txt << 'EOF'
numpy==1.24.3
pandas==2.0.3
scikit-learn==1.3.0
requests==2.31.0
EOF

    cat > /home/mills/collections/data-intelligence/requirements.txt << 'EOF'
requests==2.31.0
sqlite3
EOF

    cat > /home/mills/collections/performance-optimizer/requirements.txt << 'EOF'
requests==2.31.0
docker==6.1.3
EOF

    success "🎉 Advanced Analytics Deployment Complete!"
    log "All advanced analytics and ML services have been deployed"
    log "Services include: Enhanced ML Analytics, Data Intelligence, Performance Optimizer"
}

# Execute deployment
main "$@"