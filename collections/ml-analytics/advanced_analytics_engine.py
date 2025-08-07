#!/usr/bin/env python3
"""
Advanced Analytics and Machine Learning Engine
Provides predictive analytics, anomaly detection, and intelligent insights for infrastructure monitoring
"""

import numpy as np
import pandas as pd
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import requests
import joblib
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# Machine Learning imports
try:
    from sklearn.ensemble import IsolationForest, RandomForestRegressor
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    from sklearn.cluster import DBSCAN
    import scipy.stats as stats
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML libraries not available. Some features will be disabled.")

# Import secrets helper
try:
    import sys
    sys.path.append('/app')
    from secrets_helper import read_secret, get_database_url, get_slack_webhook
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
ANALYSIS_INTERVAL = 300  # 5 minutes
TRAINING_INTERVAL_HOURS = 6  # Retrain models every 6 hours
ANOMALY_THRESHOLD = -0.1  # Isolation Forest threshold
PREDICTION_HORIZON_HOURS = 24  # Predict 24 hours ahead
MIN_DATA_POINTS = 100  # Minimum data points for training

INFLUXDB_HOST = "influxdb"
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = "ml_analytics"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnalysisType(Enum):
    ANOMALY_DETECTION = "anomaly_detection"
    PREDICTIVE_ANALYTICS = "predictive_analytics"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    CAPACITY_PLANNING = "capacity_planning"
    TREND_ANALYSIS = "trend_analysis"

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class MLInsight:
    """Machine learning insight data structure"""
    analysis_type: AnalysisType
    severity: AlertSeverity
    timestamp: datetime
    title: str
    description: str
    confidence: float  # 0.0 to 1.0
    affected_services: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    data_points: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelPerformance:
    """Model performance tracking"""
    model_name: str
    accuracy: float
    last_trained: datetime
    training_samples: int
    validation_error: float

class AdvancedAnalyticsEngine:
    """Advanced analytics and machine learning system"""
    
    def __init__(self):
        self.influxdb_client = None
        self.setup_influxdb()
        
        # ML Models storage
        self.models = {}
        self.scalers = {}
        self.model_performance = {}
        
        # Data cache
        self.data_cache = {}
        self.last_analysis = {}
        
        # Insights storage
        self.insights_history = []
        self.active_alerts = set()
        
        # Model paths
        self.model_dir = Path('/app/models')
        self.model_dir.mkdir(exist_ok=True)
        
        # Analysis statistics
        self.analysis_stats = {
            'total_analyses': 0,
            'anomalies_detected': 0,
            'predictions_generated': 0,
            'models_trained': 0,
            'insights_generated': 0
        }
        
        if ML_AVAILABLE:
            logger.info("ML Analytics Engine initialized with full capabilities")
        else:
            logger.warning("ML Analytics Engine initialized with limited capabilities (ML libraries unavailable)")
        
    def setup_influxdb(self):
        """Setup InfluxDB connection for analytics data"""
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
                
            logger.info("InfluxDB connection established for ML analytics")
                
        except Exception as e:
            logger.error(f"Failed to setup InfluxDB: {e}")
            self.influxdb_client = None

    def fetch_historical_data(self, measurement: str, hours: int = 48) -> pd.DataFrame:
        """Fetch historical data from InfluxDB for analysis"""
        if not self.influxdb_client:
            logger.error("InfluxDB client not available")
            return pd.DataFrame()
        
        try:
            # Query for recent data
            query = f"""
            SELECT * FROM "{measurement}" 
            WHERE time > now() - {hours}h 
            ORDER BY time ASC
            """
            
            result = self.influxdb_client.query(query)
            
            if not result:
                logger.warning(f"No data found for measurement: {measurement}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            points = list(result.get_points())
            if not points:
                return pd.DataFrame()
            
            df = pd.DataFrame(points)
            
            # Convert time column to datetime
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
            
            logger.debug(f"Fetched {len(df)} data points from {measurement}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data from {measurement}: {e}")
            return pd.DataFrame()

    def detect_anomalies(self, data: pd.DataFrame, features: List[str]) -> List[MLInsight]:
        """Detect anomalies using Isolation Forest"""
        if not ML_AVAILABLE or data.empty or len(data) < MIN_DATA_POINTS:
            return []
        
        try:
            insights = []
            
            # Prepare feature data
            feature_data = data[features].dropna()
            if len(feature_data) < MIN_DATA_POINTS:
                return []
            
            # Scale features
            scaler_key = f"anomaly_{'_'.join(features)}"
            if scaler_key not in self.scalers:
                self.scalers[scaler_key] = StandardScaler()
                scaled_data = self.scalers[scaler_key].fit_transform(feature_data)
            else:
                scaled_data = self.scalers[scaler_key].transform(feature_data)
            
            # Train/use Isolation Forest
            model_key = f"isolation_forest_{'_'.join(features)}"
            if model_key not in self.models:
                self.models[model_key] = IsolationForest(
                    contamination=0.1,  # Expect 10% anomalies
                    random_state=42,
                    n_estimators=100
                )
                self.models[model_key].fit(scaled_data)
                logger.info(f"Trained new anomaly detection model: {model_key}")
            
            # Detect anomalies
            anomaly_scores = self.models[model_key].decision_function(scaled_data)
            anomalies = anomaly_scores < ANOMALY_THRESHOLD
            
            if np.any(anomalies):
                anomaly_indices = np.where(anomalies)[0]
                
                # Group consecutive anomalies
                anomaly_groups = self.group_consecutive_anomalies(anomaly_indices, feature_data.index)
                
                for group_start, group_end, indices in anomaly_groups:
                    avg_score = np.mean(anomaly_scores[indices])
                    severity = AlertSeverity.CRITICAL if avg_score < -0.3 else AlertSeverity.WARNING
                    
                    # Calculate feature statistics for this anomaly group
                    anomaly_data = feature_data.iloc[indices]
                    feature_stats = {}
                    for feature in features:
                        if feature in anomaly_data.columns:
                            feature_stats[feature] = {
                                'mean': float(anomaly_data[feature].mean()),
                                'max': float(anomaly_data[feature].max()),
                                'std': float(anomaly_data[feature].std())
                            }
                    
                    insight = MLInsight(
                        analysis_type=AnalysisType.ANOMALY_DETECTION,
                        severity=severity,
                        timestamp=datetime.utcnow(),
                        title=f"Anomalous behavior detected in {', '.join(features)}",
                        description=f"Detected {len(indices)} anomalous data points between {group_start} and {group_end}. "
                                  f"Anomaly score: {avg_score:.3f}",
                        confidence=min(1.0, abs(avg_score)),
                        affected_services=self.identify_affected_services(features),
                        recommendations=self.generate_anomaly_recommendations(features, feature_stats),
                        data_points={
                            'anomaly_score': float(avg_score),
                            'anomaly_count': len(indices),
                            'time_range': f"{group_start} to {group_end}",
                            'feature_stats': feature_stats
                        }
                    )
                    
                    insights.append(insight)
                
                self.analysis_stats['anomalies_detected'] += len(insights)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
            return []

    def generate_predictions(self, data: pd.DataFrame, target_feature: str) -> List[MLInsight]:
        """Generate predictive analytics for infrastructure metrics"""
        if not ML_AVAILABLE or data.empty or len(data) < MIN_DATA_POINTS:
            return []
        
        try:
            insights = []
            
            # Prepare time series data
            if target_feature not in data.columns:
                return []
            
            # Create time-based features
            df = data.copy()
            df = df.dropna(subset=[target_feature])
            
            if len(df) < MIN_DATA_POINTS:
                return []
            
            # Create features from time series
            df['hour'] = df.index.hour
            df['day_of_week'] = df.index.dayofweek
            df['is_weekend'] = df.index.dayofweek.isin([5, 6]).astype(int)
            
            # Rolling statistics
            df['rolling_mean_6h'] = df[target_feature].rolling('6H').mean()
            df['rolling_std_6h'] = df[target_feature].rolling('6H').std()
            df['rolling_mean_24h'] = df[target_feature].rolling('24H').mean()
            
            # Lag features
            df['lag_1h'] = df[target_feature].shift(freq='1H')
            df['lag_6h'] = df[target_feature].shift(freq='6H')
            
            # Remove NaN values
            df = df.dropna()
            
            if len(df) < MIN_DATA_POINTS:
                return []
            
            # Feature columns
            feature_cols = ['hour', 'day_of_week', 'is_weekend', 
                          'rolling_mean_6h', 'rolling_std_6h', 'rolling_mean_24h',
                          'lag_1h', 'lag_6h']
            
            X = df[feature_cols]
            y = df[target_feature]
            
            # Train/use prediction model
            model_key = f"predictor_{target_feature}"
            scaler_key = f"scaler_{target_feature}"
            
            if model_key not in self.models or len(df) > len(self.data_cache.get(target_feature, [])) * 1.5:
                # Retrain model if we have significantly more data
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                
                # Scale features
                self.scalers[scaler_key] = StandardScaler()
                X_train_scaled = self.scalers[scaler_key].fit_transform(X_train)
                X_test_scaled = self.scalers[scaler_key].transform(X_test)
                
                # Train model
                self.models[model_key] = RandomForestRegressor(
                    n_estimators=100,
                    random_state=42,
                    max_depth=10
                )
                self.models[model_key].fit(X_train_scaled, y_train)
                
                # Evaluate model
                y_pred = self.models[model_key].predict(X_test_scaled)
                mae = mean_absolute_error(y_test, y_pred)
                mse = mean_squared_error(y_test, y_pred)
                
                self.model_performance[model_key] = ModelPerformance(
                    model_name=model_key,
                    accuracy=1.0 - (mae / y_test.mean()) if y_test.mean() > 0 else 0.0,
                    last_trained=datetime.utcnow(),
                    training_samples=len(X_train),
                    validation_error=mae
                )
                
                self.analysis_stats['models_trained'] += 1
                logger.info(f"Trained prediction model {model_key}: MAE={mae:.3f}, MSE={mse:.3f}")
            
            # Generate predictions
            if model_key in self.models and scaler_key in self.scalers:
                # Create future time points
                last_time = df.index[-1]
                future_times = pd.date_range(
                    start=last_time + timedelta(hours=1),
                    periods=PREDICTION_HORIZON_HOURS,
                    freq='H'
                )
                
                # Create features for future predictions
                future_features = []
                for future_time in future_times:
                    # Use last known rolling statistics (simplified approach)
                    future_feature = [
                        future_time.hour,
                        future_time.dayofweek,
                        1 if future_time.dayofweek in [5, 6] else 0,
                        df['rolling_mean_6h'].iloc[-1],
                        df['rolling_std_6h'].iloc[-1],
                        df['rolling_mean_24h'].iloc[-1],
                        df[target_feature].iloc[-1],  # Use last value as lag
                        df[target_feature].iloc[-6] if len(df) >= 6 else df[target_feature].iloc[-1]
                    ]
                    future_features.append(future_feature)
                
                future_X = pd.DataFrame(future_features, columns=feature_cols)
                future_X_scaled = self.scalers[scaler_key].transform(future_X)
                
                predictions = self.models[model_key].predict(future_X_scaled)
                
                # Analyze predictions
                current_value = df[target_feature].iloc[-1]
                predicted_max = np.max(predictions)
                predicted_min = np.min(predictions)
                predicted_mean = np.mean(predictions)
                
                # Determine if predictions indicate concerning trends
                if predicted_max > current_value * 1.5:
                    severity = AlertSeverity.WARNING if predicted_max < current_value * 2.0 else AlertSeverity.CRITICAL
                    
                    insight = MLInsight(
                        analysis_type=AnalysisType.PREDICTIVE_ANALYTICS,
                        severity=severity,
                        timestamp=datetime.utcnow(),
                        title=f"High {target_feature} predicted",
                        description=f"ML model predicts {target_feature} will increase from {current_value:.2f} to {predicted_max:.2f} "
                                  f"within the next {PREDICTION_HORIZON_HOURS} hours.",
                        confidence=self.model_performance[model_key].accuracy,
                        affected_services=self.identify_affected_services([target_feature]),
                        recommendations=self.generate_prediction_recommendations(target_feature, current_value, predicted_max),
                        data_points={
                            'current_value': float(current_value),
                            'predicted_max': float(predicted_max),
                            'predicted_mean': float(predicted_mean),
                            'prediction_horizon_hours': PREDICTION_HORIZON_HOURS,
                            'model_accuracy': float(self.model_performance[model_key].accuracy)
                        }
                    )
                    
                    insights.append(insight)
                
                self.analysis_stats['predictions_generated'] += len(insights)
            
            # Cache data for future use
            self.data_cache[target_feature] = df
            
            return insights
            
        except Exception as e:
            logger.error(f"Error in predictive analytics: {e}")
            return []

    def analyze_performance_trends(self, data: pd.DataFrame, metrics: List[str]) -> List[MLInsight]:
        """Analyze performance trends and identify degradation patterns"""
        if data.empty:
            return []
        
        try:
            insights = []
            
            for metric in metrics:
                if metric not in data.columns:
                    continue
                
                metric_data = data[metric].dropna()
                if len(metric_data) < 20:  # Need minimum data for trend analysis
                    continue
                
                # Calculate trend statistics
                x = np.arange(len(metric_data))
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, metric_data.values)
                
                # Analyze trend significance
                if abs(r_value) > 0.7 and p_value < 0.05:  # Significant trend
                    trend_direction = "increasing" if slope > 0 else "decreasing"
                    
                    # Calculate performance degradation
                    recent_avg = metric_data.tail(10).mean()
                    historical_avg = metric_data.head(10).mean()
                    degradation_percent = ((recent_avg - historical_avg) / historical_avg * 100) if historical_avg > 0 else 0
                    
                    if abs(degradation_percent) > 20:  # Significant performance change
                        severity = AlertSeverity.CRITICAL if abs(degradation_percent) > 50 else AlertSeverity.WARNING
                        
                        insight = MLInsight(
                            analysis_type=AnalysisType.PERFORMANCE_ANALYSIS,
                            severity=severity,
                            timestamp=datetime.utcnow(),
                            title=f"Performance trend detected in {metric}",
                            description=f"{metric} shows a {trend_direction} trend with {abs(degradation_percent):.1f}% change. "
                                      f"Correlation coefficient: {r_value:.3f}",
                            confidence=abs(r_value),
                            affected_services=self.identify_affected_services([metric]),
                            recommendations=self.generate_trend_recommendations(metric, trend_direction, degradation_percent),
                            data_points={
                                'slope': float(slope),
                                'correlation': float(r_value),
                                'degradation_percent': float(degradation_percent),
                                'trend_direction': trend_direction,
                                'p_value': float(p_value)
                            }
                        )
                        
                        insights.append(insight)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error in performance trend analysis: {e}")
            return []

    def capacity_planning_analysis(self, data: pd.DataFrame, resource_metrics: List[str]) -> List[MLInsight]:
        """Perform capacity planning analysis"""
        try:
            insights = []
            
            for metric in resource_metrics:
                if metric not in data.columns:
                    continue
                
                metric_data = data[metric].dropna()
                if len(metric_data) < MIN_DATA_POINTS:
                    continue
                
                # Calculate growth rate
                recent_period = metric_data.tail(24)  # Last 24 hours
                older_period = metric_data.head(24)   # First 24 hours
                
                if len(recent_period) > 0 and len(older_period) > 0:
                    growth_rate = (recent_period.mean() - older_period.mean()) / older_period.mean() * 100
                    
                    # Project future capacity needs
                    current_utilization = recent_period.mean()
                    
                    # Simple linear projection (days until 90% capacity)
                    if growth_rate > 0:
                        days_to_90_percent = (90 - current_utilization) / (growth_rate / 7) if growth_rate > 0 else float('inf')
                        
                        if days_to_90_percent < 30:  # Less than 30 days
                            severity = AlertSeverity.CRITICAL if days_to_90_percent < 7 else AlertSeverity.WARNING
                            
                            insight = MLInsight(
                                analysis_type=AnalysisType.CAPACITY_PLANNING,
                                severity=severity,
                                timestamp=datetime.utcnow(),
                                title=f"Capacity planning alert for {metric}",
                                description=f"{metric} is growing at {growth_rate:.2f}% per week. "
                                          f"At current rate, will reach 90% capacity in {days_to_90_percent:.1f} days.",
                                confidence=0.7,  # Moderate confidence for linear projections
                                affected_services=self.identify_affected_services([metric]),
                                recommendations=self.generate_capacity_recommendations(metric, days_to_90_percent, current_utilization),
                                data_points={
                                    'current_utilization': float(current_utilization),
                                    'growth_rate_percent_per_week': float(growth_rate),
                                    'days_to_90_percent': float(days_to_90_percent),
                                    'projected_utilization_30_days': float(current_utilization + (growth_rate * 4.28))
                                }
                            )
                            
                            insights.append(insight)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error in capacity planning analysis: {e}")
            return []

    def group_consecutive_anomalies(self, anomaly_indices: np.ndarray, time_index: pd.DatetimeIndex) -> List[Tuple]:
        """Group consecutive anomalies for better reporting"""
        groups = []
        if len(anomaly_indices) == 0:
            return groups
        
        start_idx = anomaly_indices[0]
        end_idx = anomaly_indices[0]
        current_group = [anomaly_indices[0]]
        
        for i in range(1, len(anomaly_indices)):
            if anomaly_indices[i] == anomaly_indices[i-1] + 1:
                # Consecutive anomaly
                end_idx = anomaly_indices[i]
                current_group.append(anomaly_indices[i])
            else:
                # Gap found, save current group and start new one
                groups.append((
                    time_index[start_idx].strftime('%Y-%m-%d %H:%M'),
                    time_index[end_idx].strftime('%Y-%m-%d %H:%M'),
                    current_group
                ))
                start_idx = anomaly_indices[i]
                end_idx = anomaly_indices[i]
                current_group = [anomaly_indices[i]]
        
        # Add final group
        groups.append((
            time_index[start_idx].strftime('%Y-%m-%d %H:%M'),
            time_index[end_idx].strftime('%Y-%m-%d %H:%M'),
            current_group
        ))
        
        return groups

    def identify_affected_services(self, features: List[str]) -> List[str]:
        """Identify which services are affected by the analysis"""
        service_mappings = {
            'cpu_percent': ['all_services'],
            'memory_percent': ['memory_intensive_services'],
            'disk_percent': ['database_services'],
            'network_bytes': ['network_services'],
            'container_cpu': ['containerized_services'],
            'response_time': ['web_services'],
            'error_rate': ['application_services']
        }
        
        affected_services = set()
        for feature in features:
            for key, services in service_mappings.items():
                if key in feature.lower():
                    affected_services.update(services)
        
        return list(affected_services)

    def generate_anomaly_recommendations(self, features: List[str], feature_stats: Dict) -> List[str]:
        """Generate recommendations based on detected anomalies"""
        recommendations = []
        
        for feature in features:
            if 'cpu' in feature.lower():
                recommendations.extend([
                    "Review CPU-intensive processes and consider optimization",
                    "Check for runaway processes or infinite loops",
                    "Consider scaling horizontally or upgrading CPU resources"
                ])
            elif 'memory' in feature.lower():
                recommendations.extend([
                    "Investigate memory leaks in applications",
                    "Review container memory limits and usage patterns",
                    "Consider restarting high-memory services"
                ])
            elif 'disk' in feature.lower():
                recommendations.extend([
                    "Perform disk cleanup and remove old log files",
                    "Review data retention policies",
                    "Consider adding more storage capacity"
                ])
            elif 'network' in feature.lower():
                recommendations.extend([
                    "Analyze network traffic patterns",
                    "Check for DDoS attacks or unusual traffic",
                    "Review network configuration and bandwidth limits"
                ])
        
        return list(set(recommendations))  # Remove duplicates

    def generate_prediction_recommendations(self, feature: str, current_value: float, predicted_max: float) -> List[str]:
        """Generate recommendations based on predictions"""
        recommendations = []
        increase_percent = ((predicted_max - current_value) / current_value) * 100 if current_value > 0 else 0
        
        if 'cpu' in feature.lower():
            recommendations.extend([
                f"Prepare for {increase_percent:.1f}% CPU usage increase",
                "Consider scaling services horizontally before peak load",
                "Review and optimize CPU-intensive operations"
            ])
        elif 'memory' in feature.lower():
            recommendations.extend([
                f"Memory usage expected to increase by {increase_percent:.1f}%",
                "Plan memory optimization or additional capacity",
                "Monitor for potential memory exhaustion"
            ])
        elif 'disk' in feature.lower():
            recommendations.extend([
                f"Disk usage predicted to grow by {increase_percent:.1f}%",
                "Schedule disk cleanup operations",
                "Consider expanding storage before reaching capacity limits"
            ])
        
        return recommendations

    def generate_trend_recommendations(self, metric: str, direction: str, degradation_percent: float) -> List[str]:
        """Generate recommendations based on performance trends"""
        recommendations = []
        
        if direction == "increasing" and 'response_time' in metric.lower():
            recommendations.extend([
                "Performance degradation detected - response times increasing",
                "Review application performance and database queries",
                "Consider load balancing or caching optimizations"
            ])
        elif direction == "decreasing" and 'throughput' in metric.lower():
            recommendations.extend([
                "Throughput declining - investigate bottlenecks",
                "Review system capacity and scaling requirements",
                "Analyze recent changes that may impact performance"
            ])
        
        recommendations.append(f"Monitor {metric} closely as it shows {abs(degradation_percent):.1f}% change")
        
        return recommendations

    def generate_capacity_recommendations(self, metric: str, days_to_limit: float, current_utilization: float) -> List[str]:
        """Generate capacity planning recommendations"""
        recommendations = []
        
        urgency = "immediate" if days_to_limit < 7 else "near-term" if days_to_limit < 30 else "planned"
        
        recommendations.extend([
            f"Capacity planning required: {urgency} action needed",
            f"Current {metric} utilization: {current_utilization:.1f}%",
            f"Estimated {days_to_limit:.1f} days until 90% capacity"
        ])
        
        if 'disk' in metric.lower():
            recommendations.extend([
                "Plan storage expansion or data archiving",
                "Implement data lifecycle management policies"
            ])
        elif 'memory' in metric.lower():
            recommendations.extend([
                "Plan memory upgrades or service optimization",
                "Review memory allocation across services"
            ])
        elif 'cpu' in metric.lower():
            recommendations.extend([
                "Plan CPU scaling or performance optimization",
                "Review workload distribution and scheduling"
            ])
        
        return recommendations

    def send_ml_insights_notification(self, insights: List[MLInsight]):
        """Send ML insights via Slack"""
        if not insights:
            return
        
        try:
            webhook_url = get_slack_webhook()
            if not webhook_url:
                return
            
            # Group insights by severity
            critical_insights = [i for i in insights if i.severity == AlertSeverity.CRITICAL]
            warning_insights = [i for i in insights if i.severity == AlertSeverity.WARNING]
            
            if critical_insights or warning_insights:
                severity = "🚨 CRITICAL" if critical_insights else "⚠️ WARNING"
                total_insights = len(critical_insights) + len(warning_insights)
                
                message = f"{severity} ML Analytics Alert - {total_insights} insights generated"
                
                attachment_fields = []
                
                # Add top insights (limit to 3)
                top_insights = (critical_insights + warning_insights)[:3]
                for insight in top_insights:
                    attachment_fields.append({
                        'title': f"{insight.analysis_type.value.title()}: {insight.title}",
                        'value': f"{insight.description[:200]}{'...' if len(insight.description) > 200 else ''}",
                        'short': False
                    })
                
                # Add statistics
                attachment_fields.append({
                    'title': 'Analysis Statistics',
                    'value': f"Anomalies: {self.analysis_stats['anomalies_detected']} | "
                           f"Predictions: {self.analysis_stats['predictions_generated']} | "
                           f"Models: {len(self.models)}",
                    'short': True
                })
                
                payload = {
                    'text': message,
                    'attachments': [{
                        'color': 'danger' if critical_insights else 'warning',
                        'fields': attachment_fields,
                        'footer': 'Maelstrom ML Analytics Engine',
                        'ts': int(time.time())
                    }]
                }
                
                response = requests.post(webhook_url, json=payload, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Sent ML insights notification with {len(insights)} insights")
                else:
                    logger.error(f"Failed to send ML notification: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error sending ML insights notification: {e}")

    def store_ml_insights(self, insights: List[MLInsight]):
        """Store ML insights in InfluxDB"""
        if not self.influxdb_client or not insights:
            return
        
        try:
            points = []
            
            for insight in insights:
                point = {
                    'measurement': 'ml_insights',
                    'tags': {
                        'analysis_type': insight.analysis_type.value,
                        'severity': insight.severity.value,
                        'title': insight.title[:50]  # Limit tag length
                    },
                    'fields': {
                        'confidence': insight.confidence,
                        'description': insight.description,
                        'affected_services_count': len(insight.affected_services),
                        'recommendations_count': len(insight.recommendations),
                        'data_points': json.dumps(insight.data_points)
                    },
                    'time': insight.timestamp
                }
                points.append(point)
            
            # Store summary statistics
            summary_point = {
                'measurement': 'ml_analytics_summary',
                'tags': {
                    'engine': 'advanced_analytics'
                },
                'fields': {
                    'total_insights': len(insights),
                    'critical_insights': len([i for i in insights if i.severity == AlertSeverity.CRITICAL]),
                    'warning_insights': len([i for i in insights if i.severity == AlertSeverity.WARNING]),
                    'models_active': len(self.models),
                    'total_analyses': self.analysis_stats['total_analyses'],
                    'anomalies_detected': self.analysis_stats['anomalies_detected'],
                    'predictions_generated': self.analysis_stats['predictions_generated']
                },
                'time': datetime.utcnow()
            }
            points.append(summary_point)
            
            self.influxdb_client.write_points(points)
            logger.debug(f"Stored {len(points)} ML insight points in InfluxDB")
            
        except Exception as e:
            logger.error(f"Error storing ML insights: {e}")

    def run_comprehensive_analysis(self):
        """Run comprehensive ML analysis cycle"""
        try:
            logger.info("Starting comprehensive ML analysis cycle")
            all_insights = []
            
            # Define analysis targets
            analysis_targets = {
                'host_resources': ['cpu_percent', 'memory_percent', 'disk_percent'],
                'container_resources': ['cpu_percent', 'memory_percent'],
                'network_discovery_summary': ['alive_devices', 'availability_percent'],
                'service_health_summary': ['healthy_services', 'warning_services', 'critical_services']
            }
            
            for measurement, features in analysis_targets.items():
                try:
                    # Fetch data
                    data = self.fetch_historical_data(measurement, hours=48)
                    
                    if data.empty:
                        logger.debug(f"No data available for {measurement}")
                        continue
                    
                    logger.info(f"Analyzing {measurement} with {len(data)} data points")
                    
                    # Available features in data
                    available_features = [f for f in features if f in data.columns]
                    
                    if not available_features:
                        logger.debug(f"No available features for {measurement}")
                        continue
                    
                    # 1. Anomaly Detection
                    anomaly_insights = self.detect_anomalies(data, available_features)
                    all_insights.extend(anomaly_insights)
                    
                    # 2. Predictive Analytics (for numeric features)
                    for feature in available_features:
                        if pd.api.types.is_numeric_dtype(data[feature]):
                            prediction_insights = self.generate_predictions(data, feature)
                            all_insights.extend(prediction_insights)
                    
                    # 3. Performance Trend Analysis
                    trend_insights = self.analyze_performance_trends(data, available_features)
                    all_insights.extend(trend_insights)
                    
                    # 4. Capacity Planning (for resource metrics)
                    if 'resources' in measurement:
                        capacity_insights = self.capacity_planning_analysis(data, available_features)
                        all_insights.extend(capacity_insights)
                    
                    time.sleep(1)  # Brief pause between measurements
                    
                except Exception as e:
                    logger.error(f"Error analyzing {measurement}: {e}")
                    continue
            
            # Update statistics
            self.analysis_stats['total_analyses'] += 1
            self.analysis_stats['insights_generated'] += len(all_insights)
            
            # Store insights
            if all_insights:
                self.store_ml_insights(all_insights)
                self.insights_history.extend(all_insights)
                
                # Send notifications for high-priority insights
                high_priority_insights = [
                    i for i in all_insights 
                    if i.severity in [AlertSeverity.CRITICAL, AlertSeverity.WARNING]
                ]
                
                if high_priority_insights:
                    self.send_ml_insights_notification(high_priority_insights)
                
                logger.info(f"Analysis complete: {len(all_insights)} insights generated "
                          f"({len(high_priority_insights)} high priority)")
            else:
                logger.info("Analysis complete: No insights generated")
            
            # Cleanup old insights (keep last 100)
            if len(self.insights_history) > 100:
                self.insights_history = self.insights_history[-100:]
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")

    def run_continuous_analytics(self):
        """Run continuous ML analytics"""
        logger.info("Starting continuous ML analytics engine")
        last_model_training = datetime.utcnow()
        
        while True:
            try:
                # Check if we need to retrain models
                if datetime.utcnow() - last_model_training > timedelta(hours=TRAINING_INTERVAL_HOURS):
                    logger.info("Retraining ML models...")
                    # Clear models to force retraining
                    self.models.clear()
                    self.scalers.clear()
                    last_model_training = datetime.utcnow()
                
                # Run analysis
                self.run_comprehensive_analysis()
                
                # Sleep until next analysis
                time.sleep(ANALYSIS_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Stopping ML analytics engine")
                break
            except Exception as e:
                logger.error(f"Error in continuous analytics: {e}")
                time.sleep(60)


if __name__ == "__main__":
    engine = AdvancedAnalyticsEngine()
    engine.run_continuous_analytics()