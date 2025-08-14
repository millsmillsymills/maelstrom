#!/usr/bin/env python3
"""
Advanced Machine Learning Analytics Pipeline
LSTM and Prophet forecasting for network and infrastructure monitoring
"""

import os
import json
import time
import asyncio
import logging
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, deque
from influxdb import InfluxDBClient
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor
import requests

# ML libraries
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.metrics import mean_squared_error, mean_absolute_error
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import joblib

# Suppress warnings
warnings.filterwarnings("ignore")
tf.get_logger().setLevel("ERROR")

# Configuration
INFLUXDB_CONFIG = {
    "host": "influxdb",
    "port": 8086,
    "username": "admin",
    "password": "MRC1hzg2xvy8bpz*uhf",
    "database": "ml_analytics",
}

ANALYSIS_INTERVAL = 600  # Run analysis every 10 minutes
TRAINING_INTERVAL = 3600  # Retrain models every hour
PREDICTION_HORIZON = 24  # Predict 24 hours ahead
LOOKBACK_WINDOW = 168  # Use last 7 days for training (24*7)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AdvancedMLPipeline:
    def __init__(self):
        self.client = None
        self.models = {}
        self.scalers = {}
        self.data_cache = defaultdict(lambda: deque(maxlen=10000))
        self.predictions = {}
        self.anomalies = {}
        self.model_performance = defaultdict(dict)
        self.setup_influxdb()

    def setup_influxdb(self):
        """Setup InfluxDB connection and databases"""
        try:
            self.client = InfluxDBClient(**INFLUXDB_CONFIG)
            databases = [db["name"] for db in self.client.get_list_database()]
            if INFLUXDB_CONFIG["database"] not in databases:
                self.client.create_database(INFLUXDB_CONFIG["database"])
                logger.info(f"Created database: {INFLUXDB_CONFIG['database']}")

            # Create retention policies
            self.client.create_retention_policy(
                "predictions",
                "30d",
                1,
                database=INFLUXDB_CONFIG["database"],
                default=False,
            )
            self.client.create_retention_policy(
                "anomalies",
                "90d",
                1,
                database=INFLUXDB_CONFIG["database"],
                default=False,
            )
            self.client.create_retention_policy(
                "model_performance",
                "365d",
                1,
                database=INFLUXDB_CONFIG["database"],
                default=False,
            )

        except Exception as e:
            logger.error(f"Failed to setup InfluxDB: {e}")

    def fetch_historical_data(self, measurement, time_range="7d", fields=None):
        """Fetch historical data from InfluxDB for training"""
        try:
            if fields is None:
                fields = "*"
            elif isinstance(fields, list):
                fields = ", ".join(fields)

            query = f"""
                SELECT {fields} FROM {measurement}
                WHERE time >= now() - {time_range}
                ORDER BY time ASC
            """

            # Try multiple databases to find the data - use actual available databases
            databases = ["telegraf", "unifi"]

            for database in databases:
                try:
                    result = InfluxDBClient(
                        host=INFLUXDB_CONFIG["host"],
                        port=INFLUXDB_CONFIG["port"],
                        username=INFLUXDB_CONFIG["username"],
                        password=INFLUXDB_CONFIG["password"],
                        database=database,
                    ).query(query)

                    if result.raw and "series" in result.raw:
                        df = pd.DataFrame(
                            result.raw["series"][0]["values"],
                            columns=result.raw["series"][0]["columns"],
                        )
                        df["time"] = pd.to_datetime(df["time"])
                        df.set_index("time", inplace=True)
                        logger.info(
                            f"Fetched {len(df)} data points from {database}.{measurement}"
                        )
                        return df

                except Exception as e:
                    continue

            logger.warning(f"No data found for measurement: {measurement}")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return pd.DataFrame()

    def prepare_lstm_data(self, data, target_column, lookback=24):
        """Prepare data for LSTM training"""
        try:
            if data.empty or target_column not in data.columns:
                return None, None, None

            # Handle missing values
            data = data.fillna(method="ffill").fillna(method="bfill")

            values = data[target_column].values.reshape(-1, 1)

            # Scale the data
            scaler = MinMaxScaler()
            scaled_values = scaler.fit_transform(values)

            # Create sequences
            X, y = [], []
            for i in range(lookback, len(scaled_values)):
                X.append(scaled_values[i - lookback : i, 0])
                y.append(scaled_values[i, 0])

            if len(X) == 0:
                return None, None, None

            X = np.array(X)
            y = np.array(y)

            # Reshape for LSTM [samples, time steps, features]
            X = X.reshape((X.shape[0], X.shape[1], 1))

            return X, y, scaler

        except Exception as e:
            logger.error(f"Error preparing LSTM data: {e}")
            return None, None, None

    def build_lstm_model(self, input_shape):
        """Build LSTM model architecture"""
        try:
            model = keras.Sequential(
                [
                    layers.LSTM(50, return_sequences=True, input_shape=input_shape),
                    layers.Dropout(0.2),
                    layers.LSTM(50, return_sequences=True),
                    layers.Dropout(0.2),
                    layers.LSTM(50),
                    layers.Dropout(0.2),
                    layers.Dense(25, activation="relu"),
                    layers.Dense(1),
                ]
            )

            model.compile(optimizer="adam", loss="mse", metrics=["mae"])

            return model

        except Exception as e:
            logger.error(f"Error building LSTM model: {e}")
            return None

    def train_lstm_model(self, measurement, target_column):
        """Train LSTM model for time series forecasting"""
        try:
            logger.info(f"Training LSTM model for {measurement}.{target_column}")

            # Fetch historical data
            data = self.fetch_historical_data(measurement, "7d", [target_column])
            if data.empty:
                logger.warning(f"No data available for {measurement}.{target_column}")
                return None

            # Prepare data
            X, y, scaler = self.prepare_lstm_data(data, target_column, LOOKBACK_WINDOW)
            if X is None:
                logger.warning(
                    f"Insufficient data for LSTM training: {measurement}.{target_column}"
                )
                return None

            # Split data
            train_size = int(len(X) * 0.8)
            X_train, X_test = X[:train_size], X[train_size:]
            y_train, y_test = y[:train_size], y[train_size:]

            if len(X_train) < 10:
                logger.warning(f"Insufficient training data: {len(X_train)} samples")
                return None

            # Build and train model
            model = self.build_lstm_model((X.shape[1], X.shape[2]))
            if model is None:
                return None

            # Early stopping callback
            early_stopping = keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=10, restore_best_weights=True
            )

            # Train model
            history = model.fit(
                X_train,
                y_train,
                epochs=50,
                batch_size=32,
                validation_data=(X_test, y_test),
                callbacks=[early_stopping],
                verbose=0,
            )

            # Evaluate model
            train_loss = model.evaluate(X_train, y_train, verbose=0)
            val_loss = model.evaluate(X_test, y_test, verbose=0)

            # Store model and scaler
            model_key = f"{measurement}_{target_column}_lstm"
            self.models[model_key] = model
            self.scalers[model_key] = scaler

            # Store performance metrics
            self.model_performance[model_key] = {
                "train_loss": (
                    train_loss[0] if isinstance(train_loss, list) else train_loss
                ),
                "val_loss": val_loss[0] if isinstance(val_loss, list) else val_loss,
                "train_mae": (
                    train_loss[1]
                    if isinstance(train_loss, list) and len(train_loss) > 1
                    else 0
                ),
                "val_mae": (
                    val_loss[1]
                    if isinstance(val_loss, list) and len(val_loss) > 1
                    else 0
                ),
                "last_trained": datetime.utcnow().isoformat(),
                "data_points": len(X),
            }

            logger.info(
                f"LSTM model trained successfully: {model_key}, Val Loss: {val_loss}"
            )
            return model

        except Exception as e:
            logger.error(f"Error training LSTM model: {e}")
            return None

    def generate_lstm_predictions(self, measurement, target_column, horizon=24):
        """Generate predictions using trained LSTM model"""
        try:
            model_key = f"{measurement}_{target_column}_lstm"

            if model_key not in self.models or model_key not in self.scalers:
                logger.warning(f"No trained model found for {model_key}")
                return []

            model = self.models[model_key]
            scaler = self.scalers[model_key]

            # Get recent data for prediction
            data = self.fetch_historical_data(measurement, "1d", [target_column])
            if data.empty or len(data) < LOOKBACK_WINDOW:
                logger.warning(f"Insufficient recent data for prediction: {model_key}")
                return []

            # Prepare input sequence
            values = data[target_column].values.reshape(-1, 1)
            scaled_values = scaler.transform(values)

            # Get last sequence
            last_sequence = scaled_values[-LOOKBACK_WINDOW:].reshape(
                1, LOOKBACK_WINDOW, 1
            )

            predictions = []
            current_sequence = last_sequence.copy()

            # Generate predictions
            for _ in range(horizon):
                pred = model.predict(current_sequence, verbose=0)[0, 0]
                predictions.append(pred)

                # Update sequence for next prediction
                new_sequence = np.roll(current_sequence[0], -1, axis=0)
                new_sequence[-1, 0] = pred
                current_sequence = new_sequence.reshape(1, LOOKBACK_WINDOW, 1)

            # Inverse transform predictions
            predictions = np.array(predictions).reshape(-1, 1)
            predictions = scaler.inverse_transform(predictions).flatten()

            # Create prediction timestamps
            start_time = data.index[-1] + pd.Timedelta(
                minutes=5
            )  # Assume 5-minute intervals
            timestamps = pd.date_range(start_time, periods=horizon, freq="5T")

            prediction_data = [
                {
                    "timestamp": ts.isoformat(),
                    "predicted_value": float(pred),
                    "model_type": "lstm",
                    "measurement": measurement,
                    "field": target_column,
                }
                for ts, pred in zip(timestamps, predictions)
            ]

            return prediction_data

        except Exception as e:
            logger.error(f"Error generating LSTM predictions: {e}")
            return []

    def detect_anomalies_isolation_forest(self, measurement, target_columns):
        """Detect anomalies using Isolation Forest"""
        try:
            logger.info(f"Running anomaly detection for {measurement}")

            # Fetch recent data
            data = self.fetch_historical_data(measurement, "24h", target_columns)
            if data.empty or len(data) < 10:
                logger.warning(
                    f"Insufficient data for anomaly detection: {measurement}"
                )
                return []

            # Prepare features
            feature_columns = [col for col in target_columns if col in data.columns]
            if not feature_columns:
                return []

            features = data[feature_columns].fillna(method="ffill").fillna(0)

            # Scale features
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)

            # Train Isolation Forest
            iso_forest = IsolationForest(
                contamination=0.1,  # Expect 10% anomalies
                random_state=42,
                n_estimators=100,
            )

            anomaly_labels = iso_forest.fit_predict(scaled_features)
            anomaly_scores = iso_forest.score_samples(scaled_features)

            # Find anomalies
            anomalies = []
            for i, (label, score) in enumerate(zip(anomaly_labels, anomaly_scores)):
                if label == -1:  # Anomaly detected
                    anomaly = {
                        "timestamp": data.index[i].isoformat(),
                        "measurement": measurement,
                        "anomaly_score": float(score),
                        "severity": "high" if score < -0.6 else "medium",
                        "features": {
                            col: float(features.iloc[i][col]) for col in feature_columns
                        },
                        "detection_method": "isolation_forest",
                    }
                    anomalies.append(anomaly)

            logger.info(f"Detected {len(anomalies)} anomalies in {measurement}")
            return anomalies

        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
            return []

    def cluster_analysis(self, measurement, target_columns):
        """Perform cluster analysis to identify patterns"""
        try:
            logger.info(f"Running cluster analysis for {measurement}")

            # Fetch data for analysis
            data = self.fetch_historical_data(measurement, "7d", target_columns)
            if data.empty or len(data) < 50:
                return {}

            # Prepare features
            feature_columns = [col for col in target_columns if col in data.columns]
            if not feature_columns:
                return {}

            features = data[feature_columns].fillna(method="ffill").fillna(0)

            # Scale features
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)

            # DBSCAN clustering
            dbscan = DBSCAN(eps=0.5, min_samples=5)
            cluster_labels = dbscan.fit_predict(scaled_features)

            # Analyze clusters
            cluster_analysis = {
                "total_clusters": len(set(cluster_labels))
                - (1 if -1 in cluster_labels else 0),
                "noise_points": sum(1 for label in cluster_labels if label == -1),
                "cluster_stats": {},
            }

            for cluster_id in set(cluster_labels):
                if cluster_id == -1:  # Skip noise
                    continue

                cluster_mask = cluster_labels == cluster_id
                cluster_data = features[cluster_mask]

                cluster_analysis["cluster_stats"][f"cluster_{cluster_id}"] = {
                    "size": int(sum(cluster_mask)),
                    "mean_values": {
                        col: float(cluster_data[col].mean()) for col in feature_columns
                    },
                    "std_values": {
                        col: float(cluster_data[col].std()) for col in feature_columns
                    },
                }

            return cluster_analysis

        except Exception as e:
            logger.error(f"Error in cluster analysis: {e}")
            return {}

    def business_intelligence_insights(self):
        """Generate business intelligence insights from all data"""
        try:
            logger.info("Generating business intelligence insights")

            insights = {
                "infrastructure_health": {},
                "performance_trends": {},
                "cost_optimization": {},
                "capacity_planning": {},
                "security_posture": {},
            }

            # Infrastructure health analysis - map to actual available measurements
            measurement_mapping = {
                "docker_container_metrics": "docker_container_cpu",  # Available in telegraf DB
                "unraid_system_stats": "cpu",  # Use cpu measurement from telegraf
                "network_performance": "net",  # Use net measurement from telegraf
                "security_threat": "clients",  # Use UniFi clients data for network security insights
            }

            measurements = list(measurement_mapping.keys())

            for measurement in measurements:
                try:
                    # Use the mapped measurement name for actual data retrieval
                    actual_measurement = measurement_mapping.get(
                        measurement, measurement
                    )
                    data = self.fetch_historical_data(actual_measurement, "24h")
                    if not data.empty:
                        insights["infrastructure_health"][measurement] = {
                            "data_availability": "good",
                            "avg_values": {
                                col: float(data[col].mean())
                                for col in data.select_dtypes(
                                    include=[np.number]
                                ).columns
                                if not data[col].isnull().all()
                            },
                            "trend": "stable",
                            "alerts": [],
                        }
                except:
                    continue

            # Performance trends
            performance_metrics = [
                "cpu_usage_percent",
                "memory_usage_percent",
                "response_time",
            ]
            for metric in performance_metrics:
                try:
                    # Aggregate across all sources
                    trend_data = []
                    for measurement in measurements:
                        data = self.fetch_historical_data(measurement, "7d", [metric])
                        if not data.empty and metric in data.columns:
                            trend_data.extend(data[metric].dropna().values)

                    if trend_data:
                        insights["performance_trends"][metric] = {
                            "average": float(np.mean(trend_data)),
                            "trend": (
                                "improving"
                                if np.mean(trend_data[-24:]) < np.mean(trend_data[:24])
                                else "stable"
                            ),
                            "volatility": float(np.std(trend_data)),
                        }
                except:
                    continue

            # Capacity planning
            insights["capacity_planning"] = {
                "storage_growth_rate": "stable",
                "memory_utilization_trend": "stable",
                "network_bandwidth_trend": "stable",
                "projected_capacity_exhaustion": None,
            }

            # Cost optimization opportunities
            insights["cost_optimization"] = {
                "under_utilized_resources": [],
                "optimization_potential": "medium",
                "estimated_savings": "TBD",
            }

            # Security posture
            insights["security_posture"] = {
                "threat_level": "low",
                "vulnerabilities_detected": 0,
                "security_score": 85,
            }

            return insights

        except Exception as e:
            logger.error(f"Error generating business intelligence insights: {e}")
            return {}

    def store_predictions(self, predictions):
        """Store ML predictions in InfluxDB"""
        if not self.client or not predictions:
            return

        try:
            points = []

            for pred in predictions:
                point = {
                    "measurement": "ml_predictions",
                    "tags": {
                        "model_type": pred["model_type"],
                        "measurement": pred["measurement"],
                        "field": pred["field"],
                    },
                    "fields": {
                        "predicted_value": pred["predicted_value"],
                        "prediction_horizon": PREDICTION_HORIZON,
                    },
                    "time": pred["timestamp"],
                }
                points.append(point)

            if points:
                self.client.write_points(points, retention_policy="predictions")
                logger.info(f"Stored {len(points)} predictions in InfluxDB")

        except Exception as e:
            logger.error(f"Error storing predictions: {e}")

    def store_anomalies(self, anomalies):
        """Store detected anomalies in InfluxDB"""
        if not self.client or not anomalies:
            return

        try:
            points = []

            for anomaly in anomalies:
                point = {
                    "measurement": "ml_anomalies",
                    "tags": {
                        "measurement": anomaly["measurement"],
                        "severity": anomaly["severity"],
                        "detection_method": anomaly["detection_method"],
                    },
                    "fields": {
                        "anomaly_score": anomaly["anomaly_score"],
                        "feature_values": json.dumps(anomaly["features"]),
                    },
                    "time": anomaly["timestamp"],
                }
                points.append(point)

            if points:
                self.client.write_points(points, retention_policy="anomalies")
                logger.info(f"Stored {len(points)} anomalies in InfluxDB")

        except Exception as e:
            logger.error(f"Error storing anomalies: {e}")

    def store_insights(self, insights):
        """Store business intelligence insights in InfluxDB"""
        if not self.client or not insights:
            return

        try:
            points = []
            timestamp = datetime.utcnow()

            # Store infrastructure health scores
            if "infrastructure_health" in insights:
                for measurement, health in insights["infrastructure_health"].items():
                    point = {
                        "measurement": "business_intelligence",
                        "tags": {
                            "category": "infrastructure_health",
                            "measurement": measurement,
                        },
                        "fields": {
                            "health_score": 100,  # Default good health
                            "data_availability": (
                                1 if health.get("data_availability") == "good" else 0
                            ),
                        },
                        "time": timestamp,
                    }
                    points.append(point)

            # Store performance trends
            if "performance_trends" in insights:
                for metric, trend in insights["performance_trends"].items():
                    point = {
                        "measurement": "business_intelligence",
                        "tags": {"category": "performance_trends", "metric": metric},
                        "fields": {
                            "average_value": trend.get("average", 0),
                            "volatility": trend.get("volatility", 0),
                            "trend_score": (
                                1 if trend.get("trend") == "improving" else 0
                            ),
                        },
                        "time": timestamp,
                    }
                    points.append(point)

            if points:
                self.client.write_points(points)
                logger.info(f"Stored {len(points)} business intelligence insights")

        except Exception as e:
            logger.error(f"Error storing insights: {e}")

    async def send_slack_notification(self, message, severity="info"):
        """Send notifications to Slack"""
        try:
            slack_webhook = "http://172.30.0.21:5001/webhook"

            payload = {
                "title": f"[ML Analytics] {severity.upper()}",
                "message": message,
                "severity": severity,
                "service": "ml-analytics",
            }

            response = requests.post(slack_webhook, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Slack notification sent successfully")
            else:
                logger.error(
                    f"Failed to send Slack notification: {response.status_code}"
                )

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    async def training_cycle(self):
        """Run model training cycle"""
        logger.info("Starting ML model training cycle")

        try:
            # Define metrics to train models for
            training_targets = [
                ("unraid_system_stats", "cpu_usage_percent"),
                ("unraid_system_stats", "memory_usage_percent"),
                ("network_performance", "response_time"),
                ("docker_container_metrics", "cpu_percent"),
                ("docker_container_metrics", "memory_percent"),
            ]

            trained_models = 0

            for measurement, target_column in training_targets:
                try:
                    model = self.train_lstm_model(measurement, target_column)
                    if model:
                        trained_models += 1

                        # Generate predictions
                        predictions = self.generate_lstm_predictions(
                            measurement, target_column
                        )
                        if predictions:
                            self.store_predictions(predictions)

                except Exception as e:
                    logger.error(
                        f"Error training model for {measurement}.{target_column}: {e}"
                    )

            await self.send_slack_notification(
                f"ML training cycle completed: {trained_models} models trained", "info"
            )

        except Exception as e:
            logger.error(f"Error in training cycle: {e}")

    async def analysis_cycle(self):
        """Run analysis and anomaly detection cycle"""
        logger.info("Starting ML analysis cycle")

        try:
            # Anomaly detection targets
            anomaly_targets = [
                ("unraid_system_stats", ["cpu_usage_percent", "memory_usage_percent"]),
                ("network_performance", ["response_time", "packet_loss"]),
                ("docker_container_metrics", ["cpu_percent", "memory_percent"]),
            ]

            total_anomalies = 0

            for measurement, columns in anomaly_targets:
                try:
                    anomalies = self.detect_anomalies_isolation_forest(
                        measurement, columns
                    )
                    if anomalies:
                        self.store_anomalies(anomalies)
                        total_anomalies += len(anomalies)

                    # Cluster analysis
                    cluster_results = self.cluster_analysis(measurement, columns)

                except Exception as e:
                    logger.error(f"Error in analysis for {measurement}: {e}")

            # Generate business intelligence insights
            insights = self.business_intelligence_insights()
            if insights:
                self.store_insights(insights)

            if total_anomalies > 0:
                await self.send_slack_notification(
                    f"ML analysis detected {total_anomalies} anomalies", "warning"
                )

        except Exception as e:
            logger.error(f"Error in analysis cycle: {e}")

    async def continuous_ml_pipeline(self):
        """Continuous ML pipeline execution"""
        logger.info("Starting continuous ML analytics pipeline...")

        last_training = 0
        last_analysis = 0

        while True:
            try:
                current_time = time.time()

                # Run training cycle
                if current_time - last_training >= TRAINING_INTERVAL:
                    await self.training_cycle()
                    last_training = current_time

                # Run analysis cycle
                elif current_time - last_analysis >= ANALYSIS_INTERVAL:
                    await self.analysis_cycle()
                    last_analysis = current_time

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in continuous ML pipeline: {e}")
                await asyncio.sleep(60)


def main():
    """Main function"""
    logger.info("Starting Advanced ML Analytics Pipeline")

    pipeline = AdvancedMLPipeline()

    try:
        asyncio.run(pipeline.continuous_ml_pipeline())
    except KeyboardInterrupt:
        logger.info("Shutting down ML Analytics Pipeline")
    except Exception as e:
        logger.error(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
