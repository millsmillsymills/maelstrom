#!/usr/bin/env python3
"""
Edge Data Processing Engine
Handles real-time data processing for IoT devices and edge computing nodes
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from collections import deque
import threading
from enum import Enum
import statistics

import requests
from influxdb import InfluxDBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Edge processing modes"""

    REAL_TIME = "real_time"
    BATCH = "batch"
    STREAM = "stream"
    HYBRID = "hybrid"


class DataQuality(Enum):
    """Data quality levels"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INVALID = "invalid"


@dataclass
class EdgeDataPoint:
    """Individual data point from edge device"""

    device_id: str
    timestamp: datetime
    metric_name: str
    value: float
    unit: str
    quality: DataQuality
    metadata: Dict[str, Any]
    processing_latency: float = 0.0


@dataclass
class ProcessedEvent:
    """Processed edge computing event"""

    event_id: str
    source_device: str
    event_type: str
    timestamp: datetime
    data_points: List[EdgeDataPoint]
    processing_result: Dict[str, Any]
    confidence: float
    actions_triggered: List[str]


@dataclass
class EdgeComputeTask:
    """Edge computing task definition"""

    task_id: str
    node_id: str
    task_type: str
    input_data: Dict[str, Any]
    processing_requirements: Dict[str, Any]
    priority: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EdgeDataProcessor:
    """Main Edge Data Processing Engine"""

    def __init__(self):
        self.running = False
        self.processing_mode = ProcessingMode.HYBRID

        # Data buffers and queues
        self.data_buffer = deque(maxlen=10000)
        self.processed_events = deque(maxlen=5000)
        self.compute_tasks = {}
        self.active_streams = {}

        # Processing configuration
        self.batch_size = 100
        self.batch_timeout = 30  # seconds
        self.max_processing_latency = 5.0  # seconds
        self.quality_threshold = 0.7

        # Real-time processors
        self.stream_processors = {}
        self.anomaly_detectors = {}
        self.pattern_matchers = {}

        # Processing statistics
        self.stats = {
            "data_points_processed": 0,
            "events_generated": 0,
            "processing_errors": 0,
            "average_latency": 0.0,
            "quality_score": 1.0,
            "compute_tasks_completed": 0,
            "real_time_processed": 0,
            "batch_processed": 0,
        }

        # Initialize components
        self.setup_database()
        self.setup_processors()

    def setup_database(self):
        """Setup InfluxDB connection for processed data storage"""
        try:
            from collections.ml_analytics.secrets_helper import get_database_url

            db_url = get_database_url("influxdb")

            # Parse connection URL
            if "@" in db_url:
                auth_part = db_url.split("//")[1].split("@")[0]
                username, password = auth_part.split(":")
                host_part = db_url.split("@")[1].split(":")[0]
                port = 8086
            else:
                username, password = None, None
                host_part = db_url.split("//")[1].split(":")[0]
                port = 8086

            self.influxdb_client = InfluxDBClient(
                host=host_part,
                port=port,
                username=username,
                password=password,
                database="edge_processing",
            )

            # Create database if it doesn't exist
            try:
                databases = self.influxdb_client.get_list_database()
                if not any(db["name"] == "edge_processing" for db in databases):
                    self.influxdb_client.create_database("edge_processing")
                    logger.info("Created edge_processing database")
            except Exception as e:
                logger.warning(f"Could not create database: {e}")

            logger.info("InfluxDB connection established for edge processing")

        except Exception as e:
            logger.error(f"Failed to setup InfluxDB connection: {e}")
            self.influxdb_client = None

    def setup_processors(self):
        """Initialize processing components"""
        # Real-time stream processors
        self.stream_processors = {
            "temperature": self.process_temperature_stream,
            "motion": self.process_motion_stream,
            "energy": self.process_energy_stream,
            "network": self.process_network_stream,
            "security": self.process_security_stream,
        }

        # Anomaly detection for different metrics
        self.anomaly_detectors = {
            "temperature": TemperatureAnomalyDetector(),
            "motion": MotionAnomalyDetector(),
            "energy": EnergyAnomalyDetector(),
            "network": NetworkAnomalyDetector(),
        }

        # Pattern matching engines
        self.pattern_matchers = {
            "usage_patterns": UsagePatternMatcher(),
            "failure_patterns": FailurePatternMatcher(),
            "security_patterns": SecurityPatternMatcher(),
        }

        logger.info("Edge processors initialized")

    async def ingest_data_point(
        self,
        device_id: str,
        metric_name: str,
        value: float,
        unit: str = "",
        metadata: Dict[str, Any] = None,
    ):
        """Ingest a single data point from edge device"""
        start_time = time.time()

        try:
            # Validate and quality check
            quality = self.assess_data_quality(value, metadata or {})

            # Create data point
            data_point = EdgeDataPoint(
                device_id=device_id,
                timestamp=datetime.utcnow(),
                metric_name=metric_name,
                value=value,
                unit=unit,
                quality=quality,
                metadata=metadata or {},
                processing_latency=0.0,
            )

            # Add to buffer
            self.data_buffer.append(data_point)
            self.stats["data_points_processed"] += 1

            # Real-time processing if enabled
            if self.processing_mode in [
                ProcessingMode.REAL_TIME,
                ProcessingMode.HYBRID,
            ]:
                await self.process_real_time(data_point)

            # Calculate processing latency
            data_point.processing_latency = time.time() - start_time
            self.update_latency_stats(data_point.processing_latency)

        except Exception as e:
            logger.error(f"Error ingesting data point: {e}")
            self.stats["processing_errors"] += 1

    def assess_data_quality(
        self, value: float, metadata: Dict[str, Any]
    ) -> DataQuality:
        """Assess quality of incoming data"""
        try:
            # Basic validation
            if not isinstance(value, (int, float)) or value is None:
                return DataQuality.INVALID

            # Check for extreme values
            if abs(value) > 1e6:  # Arbitrary large number check
                return DataQuality.LOW

            # Check metadata for quality indicators
            signal_strength = metadata.get("signal_strength", -50)
            if signal_strength < -80:  # Very weak signal
                return DataQuality.LOW
            elif signal_strength < -60:
                return DataQuality.MEDIUM

            # Check timestamp freshness
            timestamp = metadata.get("timestamp")
            if timestamp:
                age = (
                    datetime.utcnow() - datetime.fromisoformat(timestamp)
                ).total_seconds()
                if age > 300:  # Data older than 5 minutes
                    return DataQuality.LOW
                elif age > 60:
                    return DataQuality.MEDIUM

            return DataQuality.HIGH

        except Exception as e:
            logger.debug(f"Quality assessment error: {e}")
            return DataQuality.MEDIUM

    async def process_real_time(self, data_point: EdgeDataPoint):
        """Process data point in real-time"""
        try:
            self.stats["real_time_processed"] += 1

            # Route to appropriate stream processor
            processor = self.stream_processors.get(data_point.metric_name)
            if processor:
                result = await processor(data_point)
                if result:
                    await self.handle_processing_result(data_point, result)

            # Check for anomalies
            detector = self.anomaly_detectors.get(data_point.metric_name)
            if detector:
                anomaly_result = detector.check_anomaly(data_point)
                if anomaly_result["is_anomaly"]:
                    await self.handle_anomaly(data_point, anomaly_result)

            # Pattern matching
            for matcher_name, matcher in self.pattern_matchers.items():
                patterns = matcher.check_patterns([data_point])
                if patterns:
                    await self.handle_patterns(data_point, patterns, matcher_name)

        except Exception as e:
            logger.error(f"Real-time processing error: {e}")
            self.stats["processing_errors"] += 1

    async def process_temperature_stream(
        self, data_point: EdgeDataPoint
    ) -> Optional[Dict[str, Any]]:
        """Process temperature data stream"""
        try:
            temp_value = data_point.value
            device_id = data_point.device_id

            # Temperature-specific processing
            result = {
                "processed_value": temp_value,
                "comfort_level": self.calculate_comfort_level(temp_value),
                "energy_efficiency": self.calculate_temp_efficiency(temp_value),
                "alerts": [],
            }

            # Temperature alerts
            if temp_value > 85:  # High temperature alert
                result["alerts"].append(
                    {
                        "level": "critical",
                        "message": f"High temperature detected: {temp_value}°F",
                        "recommended_action": "Check HVAC system",
                    }
                )
            elif temp_value < 45:  # Low temperature alert
                result["alerts"].append(
                    {
                        "level": "warning",
                        "message": f"Low temperature detected: {temp_value}°F",
                        "recommended_action": "Check heating system",
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Temperature processing error: {e}")
            return None

    async def process_motion_stream(
        self, data_point: EdgeDataPoint
    ) -> Optional[Dict[str, Any]]:
        """Process motion sensor data stream"""
        try:
            motion_value = data_point.value
            device_id = data_point.device_id

            result = {
                "motion_detected": motion_value > 0,
                "motion_intensity": motion_value,
                "security_relevance": self.assess_motion_security(
                    motion_value, data_point.metadata
                ),
                "automation_triggers": [],
            }

            # Motion-based automation
            if motion_value > 0:
                result["automation_triggers"].append("lights_on")
                result["automation_triggers"].append("security_recording")

                # Check for unusual motion patterns
                if self.is_unusual_motion_time(data_point.timestamp):
                    result["alerts"] = [
                        {
                            "level": "warning",
                            "message": "Motion detected during unusual hours",
                            "recommended_action": "Review security footage",
                        }
                    ]

            return result

        except Exception as e:
            logger.error(f"Motion processing error: {e}")
            return None

    async def process_energy_stream(
        self, data_point: EdgeDataPoint
    ) -> Optional[Dict[str, Any]]:
        """Process energy consumption data stream"""
        try:
            energy_value = data_point.value
            device_id = data_point.device_id

            result = {
                "power_consumption": energy_value,
                "efficiency_rating": self.calculate_energy_efficiency(energy_value),
                "cost_estimate": self.estimate_energy_cost(energy_value),
                "recommendations": [],
            }

            # Energy optimization recommendations
            if energy_value > 1000:  # High consumption
                result["recommendations"].append(
                    {
                        "type": "optimization",
                        "message": "High energy consumption detected",
                        "action": "Consider power-saving settings",
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Energy processing error: {e}")
            return None

    async def process_network_stream(
        self, data_point: EdgeDataPoint
    ) -> Optional[Dict[str, Any]]:
        """Process network performance data stream"""
        try:
            network_value = data_point.value
            metric_name = data_point.metric_name

            result = {
                "network_metric": metric_name,
                "value": network_value,
                "performance_rating": self.assess_network_performance(
                    network_value, metric_name
                ),
                "optimization_suggestions": [],
            }

            # Network performance analysis
            if metric_name == "latency" and network_value > 100:  # High latency
                result["optimization_suggestions"].append(
                    {
                        "issue": "high_latency",
                        "suggestion": "Check network congestion and routing",
                    }
                )
            elif metric_name == "packet_loss" and network_value > 5:  # High packet loss
                result["optimization_suggestions"].append(
                    {
                        "issue": "packet_loss",
                        "suggestion": "Investigate network connectivity issues",
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Network processing error: {e}")
            return None

    async def process_security_stream(
        self, data_point: EdgeDataPoint
    ) -> Optional[Dict[str, Any]]:
        """Process security-related data stream"""
        try:
            security_value = data_point.value
            device_id = data_point.device_id

            result = {
                "security_metric": data_point.metric_name,
                "risk_level": self.assess_security_risk(
                    security_value, data_point.metadata
                ),
                "threat_indicators": [],
                "response_actions": [],
            }

            # Security threat detection
            if data_point.metric_name == "failed_login_attempts" and security_value > 5:
                result["threat_indicators"].append("brute_force_attack")
                result["response_actions"].append("block_ip_temporarily")
            elif data_point.metric_name == "unusual_traffic" and security_value > 0:
                result["threat_indicators"].append("suspicious_network_activity")
                result["response_actions"].append("increase_monitoring")

            return result

        except Exception as e:
            logger.error(f"Security processing error: {e}")
            return None

    def calculate_comfort_level(self, temperature: float) -> str:
        """Calculate comfort level from temperature"""
        if 68 <= temperature <= 72:
            return "optimal"
        elif 65 <= temperature <= 75:
            return "comfortable"
        elif 60 <= temperature <= 80:
            return "acceptable"
        else:
            return "uncomfortable"

    def calculate_temp_efficiency(self, temperature: float) -> float:
        """Calculate temperature efficiency score"""
        optimal_temp = 70  # Degrees Fahrenheit
        deviation = abs(temperature - optimal_temp)
        return max(0.0, 1.0 - (deviation / 20))  # Normalize to 0-1 scale

    def assess_motion_security(
        self, motion_value: float, metadata: Dict[str, Any]
    ) -> str:
        """Assess security relevance of motion"""
        if motion_value > 0:
            hour = datetime.utcnow().hour
            if hour < 6 or hour > 22:  # Night time motion
                return "high"
            elif 6 <= hour <= 8 or 17 <= hour <= 19:  # Normal activity hours
                return "low"
            else:
                return "medium"
        return "none"

    def is_unusual_motion_time(self, timestamp: datetime) -> bool:
        """Check if motion time is unusual"""
        hour = timestamp.hour
        return hour < 6 or hour > 22  # Consider night hours unusual

    def calculate_energy_efficiency(self, energy_value: float) -> str:
        """Calculate energy efficiency rating"""
        if energy_value < 100:
            return "excellent"
        elif energy_value < 500:
            return "good"
        elif energy_value < 1000:
            return "fair"
        else:
            return "poor"

    def estimate_energy_cost(self, energy_watts: float) -> float:
        """Estimate energy cost (simplified)"""
        # Assume $0.12 per kWh
        kwh = energy_watts / 1000  # Convert watts to kilowatts
        cost_per_hour = kwh * 0.12
        return cost_per_hour

    def assess_network_performance(self, value: float, metric_name: str) -> str:
        """Assess network performance"""
        if metric_name == "latency":
            if value < 10:
                return "excellent"
            elif value < 50:
                return "good"
            elif value < 100:
                return "fair"
            else:
                return "poor"
        elif metric_name == "throughput":
            if value > 100:  # Mbps
                return "excellent"
            elif value > 50:
                return "good"
            elif value > 10:
                return "fair"
            else:
                return "poor"
        elif metric_name == "packet_loss":
            if value < 1:
                return "excellent"
            elif value < 3:
                return "good"
            elif value < 5:
                return "fair"
            else:
                return "poor"

        return "unknown"

    def assess_security_risk(self, value: float, metadata: Dict[str, Any]) -> str:
        """Assess security risk level"""
        if value > 10:
            return "critical"
        elif value > 5:
            return "high"
        elif value > 1:
            return "medium"
        else:
            return "low"

    async def handle_processing_result(
        self, data_point: EdgeDataPoint, result: Dict[str, Any]
    ):
        """Handle processing result"""
        try:
            # Store processed result
            await self.store_processed_result(data_point, result)

            # Check for alerts
            alerts = result.get("alerts", [])
            if alerts:
                await self.send_alerts(data_point.device_id, alerts)

            # Handle automation triggers
            triggers = result.get("automation_triggers", [])
            if triggers:
                await self.execute_automation_triggers(data_point.device_id, triggers)

        except Exception as e:
            logger.error(f"Error handling processing result: {e}")

    async def handle_anomaly(
        self, data_point: EdgeDataPoint, anomaly_result: Dict[str, Any]
    ):
        """Handle detected anomaly"""
        try:
            logger.warning(
                f"Anomaly detected for {data_point.device_id}: {anomaly_result}"
            )

            # Create anomaly event
            event = ProcessedEvent(
                event_id=f"anomaly-{int(time.time())}",
                source_device=data_point.device_id,
                event_type="anomaly_detection",
                timestamp=datetime.utcnow(),
                data_points=[data_point],
                processing_result=anomaly_result,
                confidence=anomaly_result.get("confidence", 0.5),
                actions_triggered=["anomaly_alert"],
            )

            self.processed_events.append(event)
            self.stats["events_generated"] += 1

            # Send anomaly notification
            await self.send_anomaly_notification(event)

        except Exception as e:
            logger.error(f"Error handling anomaly: {e}")

    async def handle_patterns(
        self,
        data_point: EdgeDataPoint,
        patterns: List[Dict[str, Any]],
        matcher_name: str,
    ):
        """Handle detected patterns"""
        try:
            for pattern in patterns:
                logger.info(f"Pattern detected by {matcher_name}: {pattern}")

                # Create pattern event
                event = ProcessedEvent(
                    event_id=f"pattern-{matcher_name}-{int(time.time())}",
                    source_device=data_point.device_id,
                    event_type="pattern_detection",
                    timestamp=datetime.utcnow(),
                    data_points=[data_point],
                    processing_result=pattern,
                    confidence=pattern.get("confidence", 0.7),
                    actions_triggered=["pattern_notification"],
                )

                self.processed_events.append(event)
                self.stats["events_generated"] += 1

        except Exception as e:
            logger.error(f"Error handling patterns: {e}")

    async def batch_processing(self):
        """Process data in batches"""
        while self.running:
            try:
                if len(self.data_buffer) >= self.batch_size:
                    # Extract batch
                    batch = [
                        self.data_buffer.popleft()
                        for _ in range(min(self.batch_size, len(self.data_buffer)))
                    ]

                    # Process batch
                    await self.process_batch(batch)
                    self.stats["batch_processed"] += len(batch)

                await asyncio.sleep(1)  # Check every second

            except Exception as e:
                logger.error(f"Batch processing error: {e}")
                await asyncio.sleep(5)

    async def process_batch(self, batch: List[EdgeDataPoint]):
        """Process a batch of data points"""
        try:
            logger.info(f"Processing batch of {len(batch)} data points")

            # Group by device and metric
            grouped_data = {}
            for data_point in batch:
                key = f"{data_point.device_id}:{data_point.metric_name}"
                if key not in grouped_data:
                    grouped_data[key] = []
                grouped_data[key].append(data_point)

            # Process each group
            for group_key, data_points in grouped_data.items():
                await self.process_grouped_data(group_key, data_points)

            # Store batch results
            await self.store_batch_results(batch)

        except Exception as e:
            logger.error(f"Error processing batch: {e}")

    async def process_grouped_data(
        self, group_key: str, data_points: List[EdgeDataPoint]
    ):
        """Process grouped data points"""
        try:
            device_id, metric_name = group_key.split(":")

            # Calculate statistics
            values = [dp.value for dp in data_points]
            stats = {
                "count": len(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            }

            # Detect trends
            if len(values) > 2:
                trend = self.detect_trend(values)
                stats["trend"] = trend

            # Store aggregated statistics
            await self.store_aggregated_stats(
                device_id, metric_name, stats, data_points[0].timestamp
            )

        except Exception as e:
            logger.error(f"Error processing grouped data for {group_key}: {e}")

    def detect_trend(self, values: List[float]) -> str:
        """Detect trend in values"""
        if len(values) < 3:
            return "insufficient_data"

        # Simple trend detection using linear regression slope
        x_values = list(range(len(values)))
        n = len(values)

        # Calculate slope
        sum_x = sum(x_values)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(x_values, values))
        sum_x_squared = sum(x * x for x in x_values)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x_squared - sum_x * sum_x)

        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"

    async def store_processed_result(
        self, data_point: EdgeDataPoint, result: Dict[str, Any]
    ):
        """Store processed result in database"""
        if not self.influxdb_client:
            return

        try:
            points = [
                {
                    "measurement": "edge_processed_data",
                    "tags": {
                        "device_id": data_point.device_id,
                        "metric_name": data_point.metric_name,
                        "quality": data_point.quality.value,
                    },
                    "fields": {
                        "original_value": data_point.value,
                        "processing_latency": data_point.processing_latency,
                        "processing_result": json.dumps(result),
                    },
                    "time": data_point.timestamp,
                }
            ]

            self.influxdb_client.write_points(points)

        except Exception as e:
            logger.error(f"Failed to store processed result: {e}")

    async def store_batch_results(self, batch: List[EdgeDataPoint]):
        """Store batch processing results"""
        if not self.influxdb_client:
            return

        try:
            points = []
            for data_point in batch:
                point = {
                    "measurement": "edge_batch_processed",
                    "tags": {
                        "device_id": data_point.device_id,
                        "metric_name": data_point.metric_name,
                        "quality": data_point.quality.value,
                    },
                    "fields": {
                        "value": data_point.value,
                        "processing_latency": data_point.processing_latency,
                    },
                    "time": data_point.timestamp,
                }
                points.append(point)

            self.influxdb_client.write_points(points)

        except Exception as e:
            logger.error(f"Failed to store batch results: {e}")

    async def store_aggregated_stats(
        self,
        device_id: str,
        metric_name: str,
        stats: Dict[str, Any],
        timestamp: datetime,
    ):
        """Store aggregated statistics"""
        if not self.influxdb_client:
            return

        try:
            points = [
                {
                    "measurement": "edge_aggregated_stats",
                    "tags": {"device_id": device_id, "metric_name": metric_name},
                    "fields": {
                        "count": stats["count"],
                        "mean": stats["mean"],
                        "median": stats["median"],
                        "min_value": stats["min"],
                        "max_value": stats["max"],
                        "standard_deviation": stats["stdev"],
                        "trend": stats.get("trend", "unknown"),
                    },
                    "time": timestamp,
                }
            ]

            self.influxdb_client.write_points(points)

        except Exception as e:
            logger.error(f"Failed to store aggregated stats: {e}")

    async def send_alerts(self, device_id: str, alerts: List[Dict[str, Any]]):
        """Send alerts for processed data"""
        try:
            from collections.ml_analytics.secrets_helper import get_slack_webhook

            webhook_url = get_slack_webhook()

            if webhook_url:
                for alert in alerts:
                    color = {
                        "critical": "danger",
                        "warning": "warning",
                        "info": "good",
                    }.get(alert["level"], "warning")

                    message = {
                        "text": f"🚨 Edge Processing Alert",
                        "attachments": [
                            {
                                "color": color,
                                "fields": [
                                    {
                                        "title": "Device",
                                        "value": device_id,
                                        "short": True,
                                    },
                                    {
                                        "title": "Level",
                                        "value": alert["level"].upper(),
                                        "short": True,
                                    },
                                    {
                                        "title": "Message",
                                        "value": alert["message"],
                                        "short": False,
                                    },
                                    {
                                        "title": "Action",
                                        "value": alert.get(
                                            "recommended_action", "Monitor"
                                        ),
                                        "short": False,
                                    },
                                ],
                            }
                        ],
                    }

                    await asyncio.to_thread(
                        requests.post, webhook_url, json=message, timeout=5
                    )

        except Exception as e:
            logger.error(f"Failed to send alerts: {e}")

    async def send_anomaly_notification(self, event: ProcessedEvent):
        """Send anomaly notification"""
        try:
            from collections.ml_analytics.secrets_helper import get_slack_webhook

            webhook_url = get_slack_webhook()

            if webhook_url:
                message = {
                    "text": f"🔍 Anomaly Detected",
                    "attachments": [
                        {
                            "color": "danger",
                            "fields": [
                                {
                                    "title": "Device",
                                    "value": event.source_device,
                                    "short": True,
                                },
                                {
                                    "title": "Confidence",
                                    "value": f"{event.confidence:.2%}",
                                    "short": True,
                                },
                                {
                                    "title": "Event ID",
                                    "value": event.event_id,
                                    "short": False,
                                },
                                {
                                    "title": "Details",
                                    "value": json.dumps(
                                        event.processing_result, indent=2
                                    ),
                                    "short": False,
                                },
                            ],
                        }
                    ],
                }

                await asyncio.to_thread(
                    requests.post, webhook_url, json=message, timeout=5
                )

        except Exception as e:
            logger.error(f"Failed to send anomaly notification: {e}")

    async def execute_automation_triggers(self, device_id: str, triggers: List[str]):
        """Execute automation triggers"""
        try:
            logger.info(f"Executing automation triggers for {device_id}: {triggers}")

            for trigger in triggers:
                if trigger == "lights_on":
                    await self.trigger_lights(device_id, True)
                elif trigger == "security_recording":
                    await self.trigger_security_recording(device_id)
                elif trigger == "energy_optimization":
                    await self.trigger_energy_optimization(device_id)

        except Exception as e:
            logger.error(f"Failed to execute automation triggers: {e}")

    async def trigger_lights(self, device_id: str, state: bool):
        """Trigger smart lights automation"""
        # Placeholder for smart home integration
        logger.info(
            f"Light automation triggered for {device_id}: {'ON' if state else 'OFF'}"
        )

    async def trigger_security_recording(self, device_id: str):
        """Trigger security recording automation"""
        # Placeholder for security system integration
        logger.info(f"Security recording triggered for {device_id}")

    async def trigger_energy_optimization(self, device_id: str):
        """Trigger energy optimization automation"""
        # Placeholder for energy management integration
        logger.info(f"Energy optimization triggered for {device_id}")

    def update_latency_stats(self, latency: float):
        """Update processing latency statistics"""
        # Simple running average
        current_avg = self.stats["average_latency"]
        processed_count = self.stats["data_points_processed"]

        if processed_count > 1:
            self.stats["average_latency"] = (
                (current_avg * (processed_count - 1)) + latency
            ) / processed_count
        else:
            self.stats["average_latency"] = latency

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        return {
            "processing_mode": self.processing_mode.value,
            "buffer_size": len(self.data_buffer),
            "processed_events": len(self.processed_events),
            "active_streams": len(self.active_streams),
            "compute_tasks": len(self.compute_tasks),
            "statistics": self.stats,
        }

    async def start_processing(self):
        """Start the edge data processing system"""
        logger.info("Starting Edge Data Processing Engine")
        self.running = True

        # Start processing tasks based on mode
        tasks = []

        if self.processing_mode in [ProcessingMode.BATCH, ProcessingMode.HYBRID]:
            tasks.append(asyncio.create_task(self.batch_processing()))

        # Start monitoring and statistics tasks
        tasks.append(asyncio.create_task(self.monitor_processing_health()))

        # Run processing tasks
        await asyncio.gather(*tasks, return_exceptions=True)

    async def monitor_processing_health(self):
        """Monitor processing system health"""
        while self.running:
            try:
                # Check buffer levels
                buffer_usage = len(self.data_buffer) / self.data_buffer.maxlen
                if buffer_usage > 0.8:
                    logger.warning(f"High buffer usage: {buffer_usage:.1%}")

                # Check processing latency
                if self.stats["average_latency"] > self.max_processing_latency:
                    logger.warning(
                        f"High processing latency: {self.stats['average_latency']:.3f}s"
                    )

                # Update quality score based on recent performance
                error_rate = self.stats["processing_errors"] / max(
                    1, self.stats["data_points_processed"]
                )
                self.stats["quality_score"] = max(0.0, 1.0 - error_rate)

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(30)

    async def stop_processing(self):
        """Stop the processing system"""
        logger.info("Stopping Edge Data Processing Engine")
        self.running = False


# Anomaly detection classes
class TemperatureAnomalyDetector:
    """Temperature anomaly detection"""

    def __init__(self):
        self.normal_range = (60, 80)  # Fahrenheit
        self.history = deque(maxlen=100)

    def check_anomaly(self, data_point: EdgeDataPoint) -> Dict[str, Any]:
        self.history.append(data_point.value)

        # Simple threshold-based detection
        if (
            data_point.value < self.normal_range[0]
            or data_point.value > self.normal_range[1]
        ):
            return {
                "is_anomaly": True,
                "confidence": 0.8,
                "type": "threshold_violation",
                "details": f"Temperature {data_point.value} outside normal range {self.normal_range}",
            }

        # Statistical anomaly detection if we have enough history
        if len(self.history) > 20:
            mean_temp = statistics.mean(self.history)
            std_temp = statistics.stdev(self.history)

            if abs(data_point.value - mean_temp) > 2 * std_temp:
                return {
                    "is_anomaly": True,
                    "confidence": 0.7,
                    "type": "statistical_outlier",
                    "details": f"Temperature {data_point.value} is {abs(data_point.value - mean_temp):.1f} degrees from mean",
                }

        return {"is_anomaly": False}


class MotionAnomalyDetector:
    """Motion anomaly detection"""

    def __init__(self):
        self.motion_history = deque(maxlen=50)
        self.time_patterns = {}

    def check_anomaly(self, data_point: EdgeDataPoint) -> Dict[str, Any]:
        self.motion_history.append(data_point)

        # Check for unusual timing
        hour = data_point.timestamp.hour
        if hour < 6 or hour > 22:  # Night hours
            if data_point.value > 0:
                return {
                    "is_anomaly": True,
                    "confidence": 0.6,
                    "type": "unusual_timing",
                    "details": f"Motion detected at {hour}:00 (unusual hour)",
                }

        return {"is_anomaly": False}


class EnergyAnomalyDetector:
    """Energy consumption anomaly detection"""

    def __init__(self):
        self.consumption_history = deque(maxlen=200)

    def check_anomaly(self, data_point: EdgeDataPoint) -> Dict[str, Any]:
        self.consumption_history.append(data_point.value)

        # Check for sudden spikes
        if len(self.consumption_history) > 10:
            recent_avg = statistics.mean(list(self.consumption_history)[-10:])
            if data_point.value > recent_avg * 2:  # Double the recent average
                return {
                    "is_anomaly": True,
                    "confidence": 0.9,
                    "type": "consumption_spike",
                    "details": f"Energy consumption {data_point.value}W is {data_point.value/recent_avg:.1f}x recent average",
                }

        return {"is_anomaly": False}


class NetworkAnomalyDetector:
    """Network performance anomaly detection"""

    def __init__(self):
        self.latency_history = deque(maxlen=100)
        self.throughput_history = deque(maxlen=100)

    def check_anomaly(self, data_point: EdgeDataPoint) -> Dict[str, Any]:
        if data_point.metric_name == "latency":
            self.latency_history.append(data_point.value)

            # High latency threshold
            if data_point.value > 500:  # milliseconds
                return {
                    "is_anomaly": True,
                    "confidence": 0.8,
                    "type": "high_latency",
                    "details": f"Network latency {data_point.value}ms exceeds threshold",
                }

        elif data_point.metric_name == "throughput":
            self.throughput_history.append(data_point.value)

            # Low throughput detection
            if data_point.value < 1:  # Mbps
                return {
                    "is_anomaly": True,
                    "confidence": 0.7,
                    "type": "low_throughput",
                    "details": f"Network throughput {data_point.value}Mbps is critically low",
                }

        return {"is_anomaly": False}


# Pattern matching classes
class UsagePatternMatcher:
    """Usage pattern detection"""

    def __init__(self):
        self.patterns = {}

    def check_patterns(self, data_points: List[EdgeDataPoint]) -> List[Dict[str, Any]]:
        # Placeholder for usage pattern detection
        return []


class FailurePatternMatcher:
    """Failure pattern detection"""

    def __init__(self):
        self.failure_indicators = {}

    def check_patterns(self, data_points: List[EdgeDataPoint]) -> List[Dict[str, Any]]:
        # Placeholder for failure pattern detection
        return []


class SecurityPatternMatcher:
    """Security pattern detection"""

    def __init__(self):
        self.security_patterns = {}

    def check_patterns(self, data_points: List[EdgeDataPoint]) -> List[Dict[str, Any]]:
        # Placeholder for security pattern detection
        return []


def main():
    """Main entry point for Edge Data Processor"""
    processor = EdgeDataProcessor()

    try:
        asyncio.run(processor.start_processing())
    except KeyboardInterrupt:
        logger.info("Edge processing stopped by user")
    except Exception as e:
        logger.error(f"Edge processing error: {e}")


if __name__ == "__main__":
    main()
