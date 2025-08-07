#!/usr/bin/env python3
"""
Machine Learning Analytics and Anomaly Detection System
Provides predictive analytics, anomaly detection, and intelligent insights
"""

import os
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from influxdb import InfluxDBClient
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import joblib
import json
import warnings
warnings.filterwarnings('ignore')

# Configuration
INFLUXDB_CONFIG = {
    'host': 'influxdb',
    'port': 8086,
    'username': 'admin',
    'password': 'MRC1hzg2xvy8bpz*uhf'
}

ML_DATABASE = 'ml_analytics'
ANALYSIS_INTERVAL = 900  # 15 minutes
MODEL_RETRAIN_INTERVAL = 3600  # 1 hour

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLAnalytics:
    def __init__(self):
        self.client = None
        self.models = {}
        self.scalers = {}
        self.setup_influxdb()
        self.model_path = '/tmp/ml_models'
        os.makedirs(self.model_path, exist_ok=True)
        
    def setup_influxdb(self):
        """Setup InfluxDB connection and database"""
        try:
            self.client = InfluxDBClient(**INFLUXDB_CONFIG)
            
            # Create ML analytics database
            databases = self.client.get_list_database()
            if not any(db['name'] == ML_DATABASE for db in databases):
                self.client.create_database(ML_DATABASE)
                logger.info(f"Created InfluxDB database: {ML_DATABASE}")
                
        except Exception as e:
            logger.error(f"Failed to setup InfluxDB: {e}")
            self.client = None

    def get_metrics_data(self, measurement: str, time_range: str = '24h', database: str = 'telegraf'):
        """Retrieve metrics data from InfluxDB"""
        try:
            query = f"""
            SELECT * FROM "{measurement}" 
            WHERE time >= now() - {time_range}
            ORDER BY time DESC
            """
            
            self.client.switch_database(database)
            result = self.client.query(query)
            
            if result.raw and 'series' in result.raw:
                series = result.raw['series'][0]
                columns = series['columns']
                values = series['values']
                
                # Convert to pandas DataFrame
                df = pd.DataFrame(values, columns=columns)
                df['time'] = pd.to_datetime(df['time'])
                df = df.set_index('time')
                
                # Convert numeric columns
                for col in df.columns:
                    if col != 'time':
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                return df
            
        except Exception as e:
            logger.error(f"Error retrieving data for {measurement}: {e}")
            
        return pd.DataFrame()

    def detect_system_anomalies(self):
        """Detect system performance anomalies"""
        logger.info("Analyzing system performance anomalies...")
        
        anomalies = []
        
        try:
            # Analyze CPU usage
            cpu_data = self.get_metrics_data('cpu', '24h')
            if not cpu_data.empty and 'usage_idle' in cpu_data.columns:
                cpu_usage = 100 - cpu_data['usage_idle'].fillna(0)
                cpu_anomalies = self.detect_univariate_anomalies(
                    cpu_usage, 'cpu_usage', threshold=0.1
                )
                anomalies.extend(cpu_anomalies)
            
            # Analyze memory usage
            mem_data = self.get_metrics_data('mem', '24h')
            if not mem_data.empty and 'used_percent' in mem_data.columns:
                mem_anomalies = self.detect_univariate_anomalies(
                    mem_data['used_percent'], 'memory_usage', threshold=0.1
                )
                anomalies.extend(mem_anomalies)
            
            # Analyze disk usage
            disk_data = self.get_metrics_data('disk', '24h')
            if not disk_data.empty and 'used_percent' in disk_data.columns:
                disk_anomalies = self.detect_univariate_anomalies(
                    disk_data['used_percent'], 'disk_usage', threshold=0.1
                )
                anomalies.extend(disk_anomalies)
            
            # Analyze network traffic
            net_data = self.get_metrics_data('net', '24h')
            if not net_data.empty:
                if 'bytes_recv' in net_data.columns:
                    net_recv_anomalies = self.detect_univariate_anomalies(
                        net_data['bytes_recv'], 'network_recv', threshold=0.15
                    )
                    anomalies.extend(net_recv_anomalies)
                
                if 'bytes_sent' in net_data.columns:
                    net_sent_anomalies = self.detect_univariate_anomalies(
                        net_data['bytes_sent'], 'network_sent', threshold=0.15
                    )
                    anomalies.extend(net_sent_anomalies)
            
        except Exception as e:
            logger.error(f"Error detecting system anomalies: {e}")
        
        return anomalies

    def detect_univariate_anomalies(self, data: pd.Series, metric_name: str, threshold: float = 0.1):
        """Detect anomalies in univariate time series data"""
        anomalies = []
        
        try:
            if len(data) < 10:
                return anomalies
            
            # Clean data
            data = data.dropna()
            if len(data) < 10:
                return anomalies
            
            # Use Isolation Forest for anomaly detection
            model_key = f"{metric_name}_isolation"
            
            if model_key not in self.models:
                self.models[model_key] = IsolationForest(
                    contamination=threshold,
                    random_state=42,
                    n_estimators=100
                )
                
                # Fit model
                X = data.values.reshape(-1, 1)
                self.models[model_key].fit(X)
            
            # Predict anomalies
            X = data.values.reshape(-1, 1)
            predictions = self.models[model_key].predict(X)
            scores = self.models[model_key].decision_function(X)
            
            # Find anomalies (prediction = -1)
            anomaly_indices = np.where(predictions == -1)[0]
            
            for idx in anomaly_indices:
                anomaly = {
                    'metric': metric_name,
                    'timestamp': data.index[idx].isoformat(),
                    'value': float(data.iloc[idx]),
                    'anomaly_score': float(scores[idx]),
                    'severity': 'high' if scores[idx] < -0.5 else 'medium',
                    'type': 'statistical_anomaly'
                }
                anomalies.append(anomaly)
                
        except Exception as e:
            logger.error(f"Error detecting anomalies for {metric_name}: {e}")
        
        return anomalies

    def predict_resource_usage(self):
        """Predict future resource usage trends"""
        logger.info("Generating resource usage predictions...")
        
        predictions = []
        
        try:
            # Predict CPU usage
            cpu_data = self.get_metrics_data('cpu', '72h')
            if not cpu_data.empty and 'usage_idle' in cpu_data.columns:
                cpu_usage = 100 - cpu_data['usage_idle'].fillna(0)
                cpu_pred = self.create_trend_prediction(cpu_usage, 'cpu_usage', hours_ahead=24)
                if cpu_pred:
                    predictions.append(cpu_pred)
            
            # Predict memory usage
            mem_data = self.get_metrics_data('mem', '72h')
            if not mem_data.empty and 'used_percent' in mem_data.columns:
                mem_pred = self.create_trend_prediction(mem_data['used_percent'], 'memory_usage', hours_ahead=24)
                if mem_pred:
                    predictions.append(mem_pred)
            
            # Predict disk usage
            disk_data = self.get_metrics_data('disk', '72h')
            if not disk_data.empty and 'used_percent' in disk_data.columns:
                disk_pred = self.create_trend_prediction(disk_data['used_percent'], 'disk_usage', hours_ahead=24)
                if disk_pred:
                    predictions.append(disk_pred)
                
        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
        
        return predictions

    def create_trend_prediction(self, data: pd.Series, metric_name: str, hours_ahead: int = 24):
        """Create trend-based predictions using linear regression"""
        try:
            if len(data) < 50:
                return None
            
            # Prepare data
            data = data.dropna().resample('1H').mean()  # Hourly averages
            if len(data) < 20:
                return None
            
            # Create features (time-based)
            X = np.arange(len(data)).reshape(-1, 1)
            y = data.values
            
            # Train model
            model_key = f"{metric_name}_trend"
            if model_key not in self.models:
                self.models[model_key] = LinearRegression()
            
            self.models[model_key].fit(X, y)
            
            # Make predictions
            future_X = np.arange(len(data), len(data) + hours_ahead).reshape(-1, 1)
            predictions = self.models[model_key].predict(future_X)
            
            # Calculate confidence intervals
            train_predictions = self.models[model_key].predict(X)
            mse = mean_squared_error(y, train_predictions)
            std_error = np.sqrt(mse)
            
            # Generate prediction timestamps
            last_timestamp = data.index[-1]
            pred_timestamps = [
                (last_timestamp + timedelta(hours=i+1)).isoformat() 
                for i in range(hours_ahead)
            ]
            
            prediction = {
                'metric': metric_name,
                'prediction_type': 'trend_forecast',
                'forecast_hours': hours_ahead,
                'predictions': [
                    {
                        'timestamp': pred_timestamps[i],
                        'predicted_value': float(predictions[i]),
                        'confidence_lower': float(predictions[i] - 2 * std_error),
                        'confidence_upper': float(predictions[i] + 2 * std_error)
                    }
                    for i in range(len(predictions))
                ],
                'model_accuracy': float(1 - (mse / np.var(y))),  # R-squared approximation
                'trend': 'increasing' if predictions[-1] > predictions[0] else 'decreasing'
            }
            
            # Generate alerts for concerning trends
            max_pred = max(predictions)
            if metric_name in ['cpu_usage', 'memory_usage', 'disk_usage'] and max_pred > 90:
                prediction['alert'] = {
                    'severity': 'high',
                    'message': f"{metric_name} predicted to reach {max_pred:.1f}% within {hours_ahead} hours",
                    'recommended_action': f"Consider scaling or optimizing {metric_name.split('_')[0]} resources"
                }
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error creating prediction for {metric_name}: {e}")
            return None

    def analyze_container_behavior(self):
        """Analyze container performance patterns"""
        logger.info("Analyzing container behavior patterns...")
        
        insights = []
        
        try:
            # Get container metrics from Prometheus via InfluxDB (if available)
            # This is a placeholder for container-specific analysis
            container_data = self.get_metrics_data('docker_container_cpu', '24h', 'telegraf')
            
            if not container_data.empty:
                # Analyze container resource patterns
                for container in container_data.get('container_name', pd.Series()).unique():
                    if pd.isna(container):
                        continue
                        
                    container_subset = container_data[container_data['container_name'] == container]
                    
                    if not container_subset.empty and 'usage_percent' in container_subset.columns:
                        avg_cpu = container_subset['usage_percent'].mean()
                        max_cpu = container_subset['usage_percent'].max()
                        
                        insight = {
                            'type': 'container_analysis',
                            'container': container,
                            'avg_cpu_usage': float(avg_cpu),
                            'max_cpu_usage': float(max_cpu),
                            'cpu_volatility': float(container_subset['usage_percent'].std()),
                            'analysis_period': '24h',
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        
                        # Add recommendations
                        if avg_cpu > 80:
                            insight['recommendation'] = 'Consider increasing CPU resources'
                            insight['priority'] = 'high'
                        elif avg_cpu < 10:
                            insight['recommendation'] = 'Container may be over-provisioned'
                            insight['priority'] = 'low'
                        else:
                            insight['priority'] = 'normal'
                        
                        insights.append(insight)
                        
        except Exception as e:
            logger.error(f"Error analyzing container behavior: {e}")
        
        return insights

    def detect_security_patterns(self):
        """Analyze security events for patterns and threats"""
        logger.info("Analyzing security event patterns...")
        
        patterns = []
        
        try:
            # Get security data
            security_data = self.get_metrics_data('security_threat', '48h', 'security_monitoring')
            
            if not security_data.empty:
                # Analyze threat frequency patterns
                if 'threat_count' in security_data.columns:
                    hourly_threats = security_data['threat_count'].resample('1H').sum()
                    
                    # Detect unusual security activity
                    if len(hourly_threats) > 12:  # At least 12 hours of data
                        threat_anomalies = self.detect_univariate_anomalies(
                            hourly_threats, 'security_threats', threshold=0.05
                        )
                        
                        for anomaly in threat_anomalies:
                            pattern = {
                                'type': 'security_pattern',
                                'pattern_name': 'unusual_threat_activity',
                                'timestamp': anomaly['timestamp'],
                                'threat_count': anomaly['value'],
                                'severity': anomaly['severity'],
                                'description': f"Unusual security threat activity detected: {anomaly['value']} threats"
                            }
                            patterns.append(pattern)
            
            # Analyze file integrity violations
            file_data = self.get_metrics_data('file_integrity_violation', '48h', 'security_monitoring')
            if not file_data.empty and 'violation_count' in file_data.columns:
                daily_violations = file_data['violation_count'].resample('1D').sum()
                
                if len(daily_violations) > 1:
                    avg_violations = daily_violations.mean()
                    recent_violations = daily_violations.iloc[-1]
                    
                    if recent_violations > avg_violations * 2:
                        pattern = {
                            'type': 'security_pattern',
                            'pattern_name': 'increased_file_modifications',
                            'timestamp': datetime.utcnow().isoformat(),
                            'recent_violations': float(recent_violations),
                            'average_violations': float(avg_violations),
                            'severity': 'medium',
                            'description': f"File modification activity increased: {recent_violations} vs avg {avg_violations:.1f}"
                        }
                        patterns.append(pattern)
                        
        except Exception as e:
            logger.error(f"Error analyzing security patterns: {e}")
        
        return patterns

    def generate_performance_insights(self):
        """Generate intelligent performance insights"""
        logger.info("Generating performance insights...")
        
        insights = []
        
        try:
            # Resource utilization insights
            cpu_data = self.get_metrics_data('cpu', '7d')
            if not cpu_data.empty and 'usage_idle' in cpu_data.columns:
                cpu_usage = 100 - cpu_data['usage_idle'].fillna(0)
                
                # Daily patterns
                daily_avg = cpu_usage.resample('1D').mean()
                hourly_avg = cpu_usage.resample('1H').mean()
                
                # Peak hours analysis
                peak_hour = hourly_avg.groupby(hourly_avg.index.hour).mean().idxmax()
                low_hour = hourly_avg.groupby(hourly_avg.index.hour).mean().idxmin()
                
                insight = {
                    'type': 'performance_insight',
                    'metric': 'cpu_usage',
                    'weekly_average': float(daily_avg.mean()),
                    'peak_hour': int(peak_hour),
                    'low_usage_hour': int(low_hour),
                    'usage_pattern': 'business_hours' if 9 <= peak_hour <= 17 else 'off_hours',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Add recommendations
                if daily_avg.mean() > 70:
                    insight['recommendation'] = 'Consider CPU scaling or optimization'
                    insight['priority'] = 'high'
                elif daily_avg.std() > 20:
                    insight['recommendation'] = 'High CPU usage variability detected - investigate workload patterns'
                    insight['priority'] = 'medium'
                
                insights.append(insight)
            
            # Network performance insights
            net_data = self.get_metrics_data('net', '7d')
            if not net_data.empty and 'bytes_recv' in net_data.columns:
                daily_traffic = net_data['bytes_recv'].resample('1D').sum()
                
                if len(daily_traffic) > 1:
                    insight = {
                        'type': 'performance_insight',
                        'metric': 'network_traffic',
                        'daily_average_bytes': float(daily_traffic.mean()),
                        'peak_day_bytes': float(daily_traffic.max()),
                        'traffic_growth': float((daily_traffic.iloc[-1] - daily_traffic.iloc[0]) / daily_traffic.iloc[0] * 100) if daily_traffic.iloc[0] > 0 else 0,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    
                    if insight['traffic_growth'] > 50:
                        insight['recommendation'] = 'Network traffic growing rapidly - monitor bandwidth utilization'
                        insight['priority'] = 'medium'
                    
                    insights.append(insight)
                    
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
        
        return insights

    def store_ml_results(self, anomalies: list, predictions: list, insights: list, patterns: list):
        """Store ML analysis results in InfluxDB"""
        if not self.client:
            return
        
        try:
            points = []
            timestamp = datetime.utcnow()
            
            # Switch to ML database
            self.client.switch_database(ML_DATABASE)
            
            # Store anomalies
            for anomaly in anomalies:
                point = {
                    "measurement": "ml_anomaly",
                    "tags": {
                        "metric": anomaly['metric'],
                        "type": anomaly['type'],
                        "severity": anomaly['severity']
                    },
                    "fields": {
                        "value": anomaly['value'],
                        "anomaly_score": anomaly['anomaly_score'],
                        "anomaly_count": 1
                    },
                    "time": timestamp
                }
                points.append(point)
            
            # Store predictions summary
            for prediction in predictions:
                if prediction and 'predictions' in prediction:
                    # Store prediction summary
                    point = {
                        "measurement": "ml_prediction",
                        "tags": {
                            "metric": prediction['metric'],
                            "prediction_type": prediction['prediction_type'],
                            "trend": prediction.get('trend', 'unknown')
                        },
                        "fields": {
                            "forecast_hours": prediction['forecast_hours'],
                            "model_accuracy": prediction['model_accuracy'],
                            "has_alert": 1 if 'alert' in prediction else 0
                        },
                        "time": timestamp
                    }
                    points.append(point)
            
            # Store insights
            for insight in insights:
                point = {
                    "measurement": "ml_insight",
                    "tags": {
                        "type": insight['type'],
                        "metric": insight.get('metric', 'general'),
                        "priority": insight.get('priority', 'normal')
                    },
                    "fields": {
                        "insight_count": 1,
                        "has_recommendation": 1 if 'recommendation' in insight else 0
                    },
                    "time": timestamp
                }
                points.append(point)
            
            # Store security patterns
            for pattern in patterns:
                point = {
                    "measurement": "ml_security_pattern",
                    "tags": {
                        "pattern_type": pattern['type'],
                        "pattern_name": pattern['pattern_name'],
                        "severity": pattern['severity']
                    },
                    "fields": {
                        "pattern_count": 1
                    },
                    "time": timestamp
                }
                points.append(point)
            
            # Store summary metrics
            summary_point = {
                "measurement": "ml_analysis_summary",
                "tags": {
                    "analysis_type": "comprehensive"
                },
                "fields": {
                    "anomalies_detected": len(anomalies),
                    "predictions_generated": len(predictions),
                    "insights_created": len(insights),
                    "security_patterns": len(patterns),
                    "analysis_duration": 0  # Placeholder
                },
                "time": timestamp
            }
            points.append(summary_point)
            
            if points:
                self.client.write_points(points)
                logger.info(f"Stored {len(points)} ML analysis results in InfluxDB")
                
        except Exception as e:
            logger.error(f"Error storing ML results: {e}")

    def send_ml_alerts(self, anomalies: list, predictions: list):
        """Send alerts for critical ML findings"""
        try:
            import requests
            
            # Count high-severity findings
            high_anomalies = [a for a in anomalies if a['severity'] == 'high']
            critical_predictions = [p for p in predictions if 'alert' in p and p['alert']['severity'] == 'high']
            
            if high_anomalies or critical_predictions:
                alert_data = {
                    "alerts": [{
                        "status": "firing",
                        "labels": {
                            "alertname": "MLAnalyticsAlert",
                            "severity": "warning",
                            "service": "ml-analytics"
                        },
                        "annotations": {
                            "summary": f"ML Analytics detected {len(high_anomalies)} high-severity anomalies and {len(critical_predictions)} critical predictions",
                            "description": f"Anomalies: {len(high_anomalies)}, Critical Predictions: {len(critical_predictions)}"
                        }
                    }]
                }
                
                response = requests.post(
                    'http://slack-notifier:5001/webhook',
                    json=alert_data,
                    timeout=5
                )
                
                if response.status_code == 200:
                    logger.info("ML analytics alert sent successfully")
                else:
                    logger.error(f"Failed to send ML alert: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error sending ML alerts: {e}")

    def run_ml_analysis(self):
        """Run comprehensive ML analysis"""
        logger.info("Starting ML analysis cycle...")
        
        try:
            start_time = time.time()
            
            # Detect anomalies
            anomalies = self.detect_system_anomalies()
            
            # Generate predictions
            predictions = self.predict_resource_usage()
            
            # Analyze container behavior
            container_insights = self.analyze_container_behavior()
            
            # Detect security patterns
            security_patterns = self.detect_security_patterns()
            
            # Generate performance insights
            performance_insights = self.generate_performance_insights()
            
            # Combine insights
            all_insights = container_insights + performance_insights
            
            # Store results
            self.store_ml_results(anomalies, predictions, all_insights, security_patterns)
            
            # Send alerts if needed
            self.send_ml_alerts(anomalies, predictions)
            
            analysis_duration = time.time() - start_time
            
            logger.info(f"ML analysis complete: {len(anomalies)} anomalies, "
                       f"{len(predictions)} predictions, {len(all_insights)} insights, "
                       f"{len(security_patterns)} security patterns (took {analysis_duration:.2f}s)")
            
            return {
                'anomalies': anomalies,
                'predictions': predictions,
                'insights': all_insights,
                'security_patterns': security_patterns,
                'analysis_duration': analysis_duration
            }
            
        except Exception as e:
            logger.error(f"Error in ML analysis: {e}")
            return None

    def run_continuous_analysis(self):
        """Run continuous ML analysis"""
        logger.info(f"Starting continuous ML analysis (interval: {ANALYSIS_INTERVAL}s)...")
        
        while True:
            try:
                self.run_ml_analysis()
                time.sleep(ANALYSIS_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Stopping ML analytics")
                break
            except Exception as e:
                logger.error(f"Error in continuous analysis: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

if __name__ == "__main__":
    analytics = MLAnalytics()
    analytics.run_continuous_analysis()