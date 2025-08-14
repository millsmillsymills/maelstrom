#!/usr/bin/env python3
"""
Global Infrastructure Monitoring and Federation System
Federated monitoring across multiple sites, data centers, and cloud environments
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import deque, defaultdict
from enum import Enum
import hashlib
import statistics

import aiohttp
from influxdb import InfluxDBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FederationNodeType(Enum):
    """Federation node types"""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EDGE = "edge"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class NodeStatus(Enum):
    """Node status states"""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class SyncStatus(Enum):
    """Data synchronization status"""

    SYNCED = "synced"
    SYNCING = "syncing"
    OUT_OF_SYNC = "out_of_sync"
    FAILED = "failed"


class MetricType(Enum):
    """Metric aggregation types"""

    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class FederationNode:
    """Federation node definition"""

    node_id: str
    name: str
    description: str
    node_type: FederationNodeType
    status: NodeStatus
    endpoint_url: str
    api_key: Optional[str]
    location: Dict[str, Any]  # Geographic/logical location info
    capabilities: List[str]
    last_seen: datetime
    sync_status: SyncStatus
    metrics_endpoints: List[str]
    health_check_interval: int = 60
    sync_interval: int = 300
    priority: int = 100
    metadata: Dict[str, Any] = None


@dataclass
class GlobalMetric:
    """Global aggregated metric"""

    metric_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    source_nodes: List[str]
    aggregation_method: str
    labels: Dict[str, str]
    confidence: float = 1.0
    metadata: Dict[str, Any] = None


@dataclass
class CrossSiteAlert:
    """Cross-site alert definition"""

    alert_id: str
    title: str
    description: str
    severity: str
    affected_nodes: List[str]
    alert_type: str
    first_seen: datetime
    last_updated: datetime
    correlation_id: Optional[str] = None
    propagated: bool = False
    metadata: Dict[str, Any] = None


class MetricAggregator:
    """Aggregates metrics across federation nodes"""

    def __init__(self):
        self.aggregation_methods = {
            "sum": self.sum_metrics,
            "average": self.average_metrics,
            "min": self.min_metrics,
            "max": self.max_metrics,
            "count": self.count_metrics,
            "percentile_95": self.percentile_95_metrics,
            "weighted_average": self.weighted_average_metrics,
        }

        # Cache for metric aggregations
        self.aggregation_cache = {}
        self.cache_ttl = 60  # 1 minute

    async def aggregate_global_metrics(
        self, node_metrics: Dict[str, List[Dict]], aggregation_rules: Dict[str, str]
    ) -> List[GlobalMetric]:
        """Aggregate metrics from multiple nodes"""
        global_metrics = []

        for metric_name, aggregation_method in aggregation_rules.items():
            try:
                # Collect metric values from all nodes
                metric_values = []
                source_nodes = []

                for node_id, metrics in node_metrics.items():
                    for metric in metrics:
                        if metric.get("name") == metric_name:
                            metric_values.append(
                                {
                                    "value": metric.get("value", 0),
                                    "timestamp": metric.get(
                                        "timestamp", datetime.utcnow()
                                    ),
                                    "node_id": node_id,
                                    "labels": metric.get("labels", {}),
                                    "weight": metric.get("weight", 1.0),
                                }
                            )
                            source_nodes.append(node_id)

                if not metric_values:
                    continue

                # Apply aggregation method
                aggregation_func = self.aggregation_methods.get(
                    aggregation_method, self.average_metrics
                )
                aggregated_value, confidence = aggregation_func(metric_values)

                # Create global metric
                global_metric = GlobalMetric(
                    metric_name=metric_name,
                    metric_type=MetricType.GAUGE,  # Default type
                    value=aggregated_value,
                    timestamp=datetime.utcnow(),
                    source_nodes=list(set(source_nodes)),
                    aggregation_method=aggregation_method,
                    labels=self.merge_labels([m["labels"] for m in metric_values]),
                    confidence=confidence,
                )

                global_metrics.append(global_metric)

            except Exception as e:
                logger.error(f"Error aggregating metric {metric_name}: {e}")

        return global_metrics

    def sum_metrics(self, metric_values: List[Dict]) -> Tuple[float, float]:
        """Sum aggregation method"""
        total = sum(m["value"] for m in metric_values)
        confidence = min(
            1.0, len(metric_values) / 5.0
        )  # Higher confidence with more data points
        return total, confidence

    def average_metrics(self, metric_values: List[Dict]) -> Tuple[float, float]:
        """Average aggregation method"""
        values = [m["value"] for m in metric_values]
        avg = statistics.mean(values)
        confidence = min(1.0, len(values) / 3.0)
        return avg, confidence

    def min_metrics(self, metric_values: List[Dict]) -> Tuple[float, float]:
        """Minimum aggregation method"""
        min_value = min(m["value"] for m in metric_values)
        confidence = 1.0  # Min is always accurate
        return min_value, confidence

    def max_metrics(self, metric_values: List[Dict]) -> Tuple[float, float]:
        """Maximum aggregation method"""
        max_value = max(m["value"] for m in metric_values)
        confidence = 1.0  # Max is always accurate
        return max_value, confidence

    def count_metrics(self, metric_values: List[Dict]) -> Tuple[float, float]:
        """Count aggregation method"""
        count = len(metric_values)
        confidence = 1.0
        return float(count), confidence

    def percentile_95_metrics(self, metric_values: List[Dict]) -> Tuple[float, float]:
        """95th percentile aggregation method"""
        values = sorted([m["value"] for m in metric_values])
        if not values:
            return 0.0, 0.0

        index = int(0.95 * len(values))
        p95_value = values[min(index, len(values) - 1)]
        confidence = min(
            1.0, len(values) / 10.0
        )  # Need more samples for accurate percentiles
        return p95_value, confidence

    def weighted_average_metrics(
        self, metric_values: List[Dict]
    ) -> Tuple[float, float]:
        """Weighted average aggregation method"""
        total_weight = sum(m.get("weight", 1.0) for m in metric_values)
        if total_weight == 0:
            return 0.0, 0.0

        weighted_sum = sum(m["value"] * m.get("weight", 1.0) for m in metric_values)
        weighted_avg = weighted_sum / total_weight
        confidence = min(1.0, len(metric_values) / 3.0)

        return weighted_avg, confidence

    def merge_labels(self, label_sets: List[Dict[str, str]]) -> Dict[str, str]:
        """Merge labels from multiple metrics"""
        merged = {}

        # Find common labels
        if label_sets:
            common_keys = set(label_sets[0].keys())
            for labels in label_sets[1:]:
                common_keys &= set(labels.keys())

            # Include labels that are consistent across all sets
            for key in common_keys:
                values = set(labels.get(key) for labels in label_sets)
                if len(values) == 1:
                    merged[key] = values.pop()
                else:
                    # Multiple values - create aggregated label
                    merged[key] = f"multiple[{len(values)}]"

        return merged


class NodeHealthMonitor:
    """Monitors health of federation nodes"""

    def __init__(self):
        self.health_checks = {}
        self.health_history = defaultdict(lambda: deque(maxlen=100))

    async def check_node_health(self, node: FederationNode) -> Dict[str, Any]:
        """Check health of a federation node"""
        health_result = {
            "node_id": node.node_id,
            "status": NodeStatus.UNKNOWN,
            "response_time": 0,
            "last_check": datetime.utcnow(),
            "metrics_available": False,
            "api_accessible": False,
            "error": None,
        }

        try:
            start_time = time.time()

            # Basic connectivity check
            async with aiohttp.ClientSession() as session:
                # Check main endpoint
                try:
                    headers = {}
                    if node.api_key:
                        headers["Authorization"] = f"Bearer {node.api_key}"

                    async with session.get(
                        f"{node.endpoint_url}/health",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as response:

                        response_time = time.time() - start_time
                        health_result["response_time"] = response_time

                        if response.status == 200:
                            health_result["api_accessible"] = True

                            try:
                                data = await response.json()
                                health_result["status"] = NodeStatus(
                                    data.get("status", "unknown")
                                )
                            except Exception:
                                health_result["status"] = NodeStatus.ONLINE
                        else:
                            health_result["status"] = NodeStatus.DEGRADED
                            health_result["error"] = f"HTTP {response.status}"

                except asyncio.TimeoutError:
                    health_result["status"] = NodeStatus.OFFLINE
                    health_result["error"] = "Connection timeout"
                except Exception as e:
                    health_result["status"] = NodeStatus.OFFLINE
                    health_result["error"] = str(e)

                # Check metrics endpoints
                if health_result["api_accessible"]:
                    metrics_available = await self.check_metrics_availability(
                        session, node, headers
                    )
                    health_result["metrics_available"] = metrics_available

        except Exception as e:
            health_result["status"] = NodeStatus.OFFLINE
            health_result["error"] = str(e)

        # Update health history
        self.health_history[node.node_id].append(health_result)

        # Update node status
        node.status = health_result["status"]
        node.last_seen = health_result["last_check"]

        return health_result

    async def check_metrics_availability(
        self,
        session: aiohttp.ClientSession,
        node: FederationNode,
        headers: Dict[str, str],
    ) -> bool:
        """Check if node metrics are available"""
        try:
            for endpoint in node.metrics_endpoints:
                full_url = f"{node.endpoint_url}{endpoint}"

                async with session.get(
                    full_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        # Try to parse a small sample of metrics
                        content = await response.text()
                        if len(content) > 0:
                            return True

            return False

        except Exception as e:
            logger.debug(f"Metrics check failed for {node.node_id}: {e}")
            return False

    def get_node_health_summary(self, node_id: str) -> Dict[str, Any]:
        """Get health summary for a node"""
        history = list(self.health_history[node_id])
        if not history:
            return {"status": "no_data", "uptime_percentage": 0}

        # Calculate uptime percentage
        online_checks = sum(
            1
            for h in history
            if h["status"] in [NodeStatus.ONLINE, NodeStatus.DEGRADED]
        )
        uptime_percentage = (online_checks / len(history)) * 100

        # Calculate average response time
        response_times = [h["response_time"] for h in history if h["response_time"] > 0]
        avg_response_time = statistics.mean(response_times) if response_times else 0

        latest = history[-1]

        return {
            "current_status": latest["status"].value,
            "uptime_percentage": uptime_percentage,
            "average_response_time": avg_response_time,
            "last_check": latest["last_check"],
            "checks_performed": len(history),
        }


class DataSynchronizer:
    """Synchronizes data between federation nodes"""

    def __init__(self):
        self.sync_status = {}
        self.sync_conflicts = []
        self.sync_statistics = defaultdict(int)

    async def sync_node_data(
        self,
        source_node: FederationNode,
        target_nodes: List[FederationNode],
        data_types: List[str],
    ) -> Dict[str, Any]:
        """Synchronize data from source to target nodes"""
        sync_result = {
            "source_node": source_node.node_id,
            "target_nodes": [node.node_id for node in target_nodes],
            "data_types": data_types,
            "start_time": datetime.utcnow(),
            "success_count": 0,
            "failure_count": 0,
            "conflicts": [],
            "errors": [],
        }

        try:
            # Fetch data from source node
            source_data = await self.fetch_node_data(source_node, data_types)

            if not source_data:
                sync_result["errors"].append("No data available from source node")
                return sync_result

            # Synchronize to each target node
            sync_tasks = []
            for target_node in target_nodes:
                task = asyncio.create_task(
                    self.sync_to_target_node(source_data, target_node, data_types)
                )
                sync_tasks.append((target_node.node_id, task))

            # Wait for all sync operations
            for node_id, task in sync_tasks:
                try:
                    result = await task
                    if result["success"]:
                        sync_result["success_count"] += 1
                    else:
                        sync_result["failure_count"] += 1
                        sync_result["errors"].append(f"{node_id}: {result['error']}")

                    if result.get("conflicts"):
                        sync_result["conflicts"].extend(result["conflicts"])

                except Exception as e:
                    sync_result["failure_count"] += 1
                    sync_result["errors"].append(f"{node_id}: {str(e)}")

            sync_result["end_time"] = datetime.utcnow()

            # Update sync statistics
            self.sync_statistics["total_syncs"] += 1
            self.sync_statistics["successful_syncs"] += sync_result["success_count"]
            self.sync_statistics["failed_syncs"] += sync_result["failure_count"]

            return sync_result

        except Exception as e:
            sync_result["errors"].append(f"Sync operation failed: {str(e)}")
            sync_result["end_time"] = datetime.utcnow()
            return sync_result

    async def fetch_node_data(
        self, node: FederationNode, data_types: List[str]
    ) -> Dict[str, Any]:
        """Fetch data from a federation node"""
        node_data = {}

        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if node.api_key:
                    headers["Authorization"] = f"Bearer {node.api_key}"

                for data_type in data_types:
                    try:
                        url = f"{node.endpoint_url}/api/v1/{data_type}"

                        async with session.get(
                            url,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30),
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                node_data[data_type] = data
                            else:
                                logger.warning(
                                    f"Failed to fetch {data_type} from {node.node_id}: HTTP {response.status}"
                                )

                    except Exception as e:
                        logger.error(
                            f"Error fetching {data_type} from {node.node_id}: {e}"
                        )
                        continue

            return node_data

        except Exception as e:
            logger.error(f"Error fetching data from {node.node_id}: {e}")
            return {}

    async def sync_to_target_node(
        self, data: Dict[str, Any], target_node: FederationNode, data_types: List[str]
    ) -> Dict[str, Any]:
        """Sync data to a target node"""
        result = {
            "node_id": target_node.node_id,
            "success": False,
            "error": None,
            "conflicts": [],
        }

        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Content-Type": "application/json"}
                if target_node.api_key:
                    headers["Authorization"] = f"Bearer {target_node.api_key}"

                for data_type in data_types:
                    if data_type not in data:
                        continue

                    url = f"{target_node.endpoint_url}/api/v1/{data_type}/sync"

                    async with session.post(
                        url,
                        json=data[data_type],
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as response:
                        if response.status == 200:
                            continue
                        elif response.status == 409:  # Conflict
                            conflict_data = await response.json()
                            result["conflicts"].append(
                                {"data_type": data_type, "conflict": conflict_data}
                            )
                        else:
                            result["error"] = f"HTTP {response.status} for {data_type}"
                            return result

                result["success"] = True
                return result

        except Exception as e:
            result["error"] = str(e)
            return result


class GlobalMonitoringFederation:
    """Main global monitoring federation orchestrator"""

    def __init__(self):
        self.running = False
        self.federation_nodes = {}
        self.metric_aggregator = MetricAggregator()
        self.health_monitor = NodeHealthMonitor()
        self.data_synchronizer = DataSynchronizer()

        # Global metrics and alerts
        self.global_metrics = deque(maxlen=50000)
        self.cross_site_alerts = {}

        # Configuration
        self.aggregation_rules = {}
        self.sync_schedules = {}

        # Statistics
        self.stats = {
            "total_nodes": 0,
            "online_nodes": 0,
            "metrics_aggregated": 0,
            "alerts_propagated": 0,
            "sync_operations": 0,
            "last_global_sync": None,
        }

        # Initialize system
        self.setup_database()
        self.load_default_configuration()

    def setup_database(self):
        """Setup InfluxDB connection for federation metrics"""
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
                database="global_federation",
            )

            # Create database if it doesn't exist
            try:
                databases = self.influxdb_client.get_list_database()
                if not any(db["name"] == "global_federation" for db in databases):
                    self.influxdb_client.create_database("global_federation")
                    logger.info("Created global_federation database")
            except Exception as e:
                logger.warning(f"Could not create database: {e}")

            logger.info("InfluxDB connection established for global federation")

        except Exception as e:
            logger.error(f"Failed to setup InfluxDB connection: {e}")
            self.influxdb_client = None

    def load_default_configuration(self):
        """Load default federation configuration"""
        # Default aggregation rules
        self.aggregation_rules = {
            "cpu_usage_percent": "weighted_average",
            "memory_usage_percent": "weighted_average",
            "disk_usage_percent": "max",
            "network_bytes_total": "sum",
            "http_requests_total": "sum",
            "response_time_seconds": "percentile_95",
            "error_rate": "average",
            "uptime_seconds": "min",
        }

        # Default node configurations
        default_nodes = [
            FederationNode(
                node_id="primary_datacenter",
                name="Primary Data Center",
                description="Main monitoring infrastructure",
                node_type=FederationNodeType.PRIMARY,
                status=NodeStatus.UNKNOWN,
                endpoint_url="http://localhost:9090",  # Prometheus endpoint
                api_key=None,
                location={"region": "us-west", "datacenter": "primary", "zone": "a"},
                capabilities=["metrics", "alerts", "dashboards"],
                last_seen=datetime.utcnow(),
                sync_status=SyncStatus.SYNCED,
                metrics_endpoints=["/api/v1/query", "/metrics"],
                priority=1,
            ),
            FederationNode(
                node_id="edge_node_1",
                name="Edge Node 1",
                description="Edge monitoring node",
                node_type=FederationNodeType.EDGE,
                status=NodeStatus.UNKNOWN,
                endpoint_url="http://edge1.example.com:9090",
                api_key=None,
                location={"region": "us-east", "datacenter": "edge", "zone": "1"},
                capabilities=["metrics", "local_alerts"],
                last_seen=datetime.utcnow(),
                sync_status=SyncStatus.OUT_OF_SYNC,
                metrics_endpoints=["/api/v1/query", "/metrics"],
                priority=10,
            ),
        ]

        for node in default_nodes:
            self.add_federation_node(node)

        logger.info("Loaded default federation configuration")

    def add_federation_node(self, node: FederationNode):
        """Add a federation node"""
        self.federation_nodes[node.node_id] = node
        self.stats["total_nodes"] += 1
        logger.info(f"Added federation node: {node.name}")

    async def collect_global_metrics(self):
        """Collect and aggregate metrics from all nodes"""
        while self.running:
            try:
                logger.info("Starting global metrics collection")

                # Collect metrics from all nodes
                node_metrics = {}

                collection_tasks = []
                for node_id, node in self.federation_nodes.items():
                    if node.status == NodeStatus.ONLINE:
                        task = asyncio.create_task(self.collect_node_metrics(node))
                        collection_tasks.append((node_id, task))

                # Wait for all collections to complete
                for node_id, task in collection_tasks:
                    try:
                        metrics = await task
                        if metrics:
                            node_metrics[node_id] = metrics
                    except Exception as e:
                        logger.error(f"Error collecting metrics from {node_id}: {e}")

                # Aggregate global metrics
                if node_metrics:
                    global_metrics = (
                        await self.metric_aggregator.aggregate_global_metrics(
                            node_metrics, self.aggregation_rules
                        )
                    )

                    # Store global metrics
                    for metric in global_metrics:
                        self.global_metrics.append(metric)

                    # Store in database
                    await self.store_global_metrics(global_metrics)

                    self.stats["metrics_aggregated"] += len(global_metrics)
                    logger.info(f"Aggregated {len(global_metrics)} global metrics")

                # Update node statistics
                self.update_node_statistics()

                await asyncio.sleep(60)  # Collect every minute

            except Exception as e:
                logger.error(f"Error in global metrics collection: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def collect_node_metrics(self, node: FederationNode) -> List[Dict[str, Any]]:
        """Collect metrics from a specific node"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if node.api_key:
                    headers["Authorization"] = f"Bearer {node.api_key}"

                metrics = []

                # Query each metrics endpoint
                for endpoint in node.metrics_endpoints:
                    try:
                        url = f"{node.endpoint_url}{endpoint}"

                        async with session.get(
                            url,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30),
                        ) as response:
                            if response.status == 200:
                                # Parse metrics based on endpoint type
                                if "/api/v1/query" in endpoint:
                                    # Prometheus query format
                                    data = await response.json()
                                    parsed_metrics = self.parse_prometheus_metrics(
                                        data, node.node_id
                                    )
                                    metrics.extend(parsed_metrics)
                                elif "/metrics" in endpoint:
                                    # Prometheus exposition format
                                    text = await response.text()
                                    parsed_metrics = self.parse_prometheus_exposition(
                                        text, node.node_id
                                    )
                                    metrics.extend(parsed_metrics)

                    except Exception as e:
                        logger.debug(
                            f"Error collecting from {endpoint} on {node.node_id}: {e}"
                        )
                        continue

                return metrics

        except Exception as e:
            logger.error(f"Error collecting metrics from {node.node_id}: {e}")
            return []

    def parse_prometheus_metrics(
        self, data: Dict[str, Any], node_id: str
    ) -> List[Dict[str, Any]]:
        """Parse Prometheus query response"""
        metrics = []

        try:
            if data.get("status") == "success":
                result_data = data.get("data", {})
                result = result_data.get("result", [])

                for metric in result:
                    metric_name = metric.get("metric", {}).get("__name__", "unknown")
                    labels = metric.get("metric", {})

                    # Get value (could be instant or range query)
                    value_data = metric.get("value")
                    if value_data and len(value_data) >= 2:
                        timestamp = datetime.fromtimestamp(float(value_data[0]))
                        value = float(value_data[1])

                        metrics.append(
                            {
                                "name": metric_name,
                                "value": value,
                                "timestamp": timestamp,
                                "labels": labels,
                                "source_node": node_id,
                            }
                        )

        except Exception as e:
            logger.error(f"Error parsing Prometheus metrics: {e}")

        return metrics

    def parse_prometheus_exposition(
        self, text: str, node_id: str
    ) -> List[Dict[str, Any]]:
        """Parse Prometheus exposition format"""
        metrics = []

        try:
            current_time = datetime.utcnow()

            for line in text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Basic parsing (simplified)
                if " " in line:
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        metric_part, value_str = parts

                        try:
                            value = float(value_str)

                            # Extract metric name and labels
                            if "{" in metric_part:
                                metric_name = metric_part[: metric_part.find("{")]
                                label_part = metric_part[
                                    metric_part.find("{") : metric_part.rfind("}") + 1
                                ]
                                labels = self.parse_labels(label_part)
                            else:
                                metric_name = metric_part
                                labels = {}

                            metrics.append(
                                {
                                    "name": metric_name,
                                    "value": value,
                                    "timestamp": current_time,
                                    "labels": labels,
                                    "source_node": node_id,
                                }
                            )

                        except ValueError:
                            continue

        except Exception as e:
            logger.error(f"Error parsing exposition format: {e}")

        return metrics

    def parse_labels(self, label_string: str) -> Dict[str, str]:
        """Parse Prometheus label string"""
        labels = {}

        try:
            # Remove outer braces
            label_string = label_string.strip("{}")

            # Simple label parsing (not handling all edge cases)
            if label_string:
                for pair in label_string.split(","):
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"')
                        labels[key] = value

        except Exception as e:
            logger.debug(f"Error parsing labels: {e}")

        return labels

    async def store_global_metrics(self, metrics: List[GlobalMetric]):
        """Store global metrics in InfluxDB"""
        if not self.influxdb_client:
            return

        try:
            points = []

            for metric in metrics:
                point = {
                    "measurement": "global_metrics",
                    "tags": {
                        "metric_name": metric.metric_name,
                        "aggregation_method": metric.aggregation_method,
                        "source_node_count": len(metric.source_nodes),
                    },
                    "fields": {
                        "value": metric.value,
                        "confidence": metric.confidence,
                        "source_nodes": ",".join(metric.source_nodes),
                    },
                    "time": metric.timestamp,
                }

                # Add labels as tags
                for key, value in metric.labels.items():
                    point["tags"][f"label_{key}"] = value

                points.append(point)

            if points:
                self.influxdb_client.write_points(points)
                logger.debug(f"Stored {len(points)} global metrics in InfluxDB")

        except Exception as e:
            logger.error(f"Failed to store global metrics: {e}")

    async def monitor_node_health(self):
        """Monitor health of all federation nodes"""
        while self.running:
            try:
                health_tasks = []

                for node_id, node in self.federation_nodes.items():
                    task = asyncio.create_task(
                        self.health_monitor.check_node_health(node)
                    )
                    health_tasks.append((node_id, task))

                # Wait for all health checks
                for node_id, task in health_tasks:
                    try:
                        health_result = await task
                        await self.store_node_health(health_result)
                    except Exception as e:
                        logger.error(f"Health check failed for {node_id}: {e}")

                self.update_node_statistics()

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in node health monitoring: {e}")
                await asyncio.sleep(300)

    async def store_node_health(self, health_result: Dict[str, Any]):
        """Store node health metrics in InfluxDB"""
        if not self.influxdb_client:
            return

        try:
            point = {
                "measurement": "federation_node_health",
                "tags": {
                    "node_id": health_result["node_id"],
                    "status": health_result["status"].value,
                },
                "fields": {
                    "response_time": health_result["response_time"],
                    "api_accessible": health_result["api_accessible"],
                    "metrics_available": health_result["metrics_available"],
                    "online": 1 if health_result["status"] == NodeStatus.ONLINE else 0,
                },
                "time": health_result["last_check"],
            }

            if health_result["error"]:
                point["fields"]["error"] = health_result["error"]

            self.influxdb_client.write_points([point])

        except Exception as e:
            logger.error(f"Failed to store node health: {e}")

    def update_node_statistics(self):
        """Update federation statistics"""
        online_count = sum(
            1
            for node in self.federation_nodes.values()
            if node.status == NodeStatus.ONLINE
        )

        self.stats.update(
            {
                "total_nodes": len(self.federation_nodes),
                "online_nodes": online_count,
                "offline_nodes": len(self.federation_nodes) - online_count,
            }
        )

    async def propagate_cross_site_alerts(self):
        """Propagate alerts across federation nodes"""
        while self.running:
            try:
                # Check for new alerts from each node
                for node_id, node in self.federation_nodes.items():
                    if node.status != NodeStatus.ONLINE:
                        continue

                    # Fetch alerts from node
                    node_alerts = await self.fetch_node_alerts(node)

                    # Process and propagate alerts
                    for alert in node_alerts:
                        await self.process_cross_site_alert(alert, node_id)

                await asyncio.sleep(120)  # Check every 2 minutes

            except Exception as e:
                logger.error(f"Error in alert propagation: {e}")
                await asyncio.sleep(300)

    async def fetch_node_alerts(self, node: FederationNode) -> List[Dict[str, Any]]:
        """Fetch active alerts from a node"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if node.api_key:
                    headers["Authorization"] = f"Bearer {node.api_key}"

                # Try Prometheus alertmanager API
                url = f"{node.endpoint_url}/api/v1/alerts"

                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", [])

            return []

        except Exception as e:
            logger.debug(f"Error fetching alerts from {node.node_id}: {e}")
            return []

    async def process_cross_site_alert(
        self, alert: Dict[str, Any], source_node_id: str
    ):
        """Process and potentially propagate a cross-site alert"""
        try:
            alert_fingerprint = self.generate_alert_fingerprint(alert)

            # Check if we've already processed this alert
            if alert_fingerprint in self.cross_site_alerts:
                return

            # Determine if alert should be propagated
            if self.should_propagate_alert(alert, source_node_id):
                cross_site_alert = CrossSiteAlert(
                    alert_id=alert_fingerprint,
                    title=alert.get("labels", {}).get("alertname", "Unknown Alert"),
                    description=alert.get("annotations", {}).get("description", ""),
                    severity=alert.get("labels", {}).get("severity", "warning"),
                    affected_nodes=[source_node_id],
                    alert_type="federation",
                    first_seen=datetime.utcnow(),
                    last_updated=datetime.utcnow(),
                    metadata={"source_alert": alert},
                )

                self.cross_site_alerts[alert_fingerprint] = cross_site_alert

                # Propagate to other nodes
                await self.propagate_alert_to_nodes(cross_site_alert)

                self.stats["alerts_propagated"] += 1
                logger.info(f"Propagated cross-site alert: {cross_site_alert.title}")

        except Exception as e:
            logger.error(f"Error processing cross-site alert: {e}")

    def generate_alert_fingerprint(self, alert: Dict[str, Any]) -> str:
        """Generate unique fingerprint for alert"""
        # Create fingerprint from alert name and key labels
        labels = alert.get("labels", {})
        key_labels = ["alertname", "instance", "job", "service"]

        fingerprint_data = []
        for key in key_labels:
            if key in labels:
                fingerprint_data.append(f"{key}={labels[key]}")

        fingerprint_string = "|".join(fingerprint_data)
        return hashlib.md5(fingerprint_string.encode()).hexdigest()

    def should_propagate_alert(
        self, alert: Dict[str, Any], source_node_id: str
    ) -> bool:
        """Determine if alert should be propagated across federation"""
        labels = alert.get("labels", {})

        # Only propagate critical and high severity alerts
        severity = labels.get("severity", "").lower()
        if severity not in ["critical", "high", "warning"]:
            return False

        # Don't propagate node-specific alerts
        if "instance" in labels and labels["instance"].startswith("localhost"):
            return False

        # Propagate service-level alerts
        if "service" in labels or "job" in labels:
            return True

        return False

    async def propagate_alert_to_nodes(self, alert: CrossSiteAlert):
        """Propagate alert to other federation nodes"""
        # Implementation would send alert to webhook endpoints or APIs of other nodes
        # For now, just log the propagation
        logger.info(
            f"Would propagate alert {alert.alert_id} to {len(self.federation_nodes)-1} other nodes"
        )

    def get_federation_status(self) -> Dict[str, Any]:
        """Get current federation status"""
        return {
            "federation_nodes": {
                node_id: {
                    "name": node.name,
                    "type": node.node_type.value,
                    "status": node.status.value,
                    "last_seen": node.last_seen.isoformat(),
                    "sync_status": node.sync_status.value,
                    "health_summary": self.health_monitor.get_node_health_summary(
                        node_id
                    ),
                }
                for node_id, node in self.federation_nodes.items()
            },
            "global_metrics_count": len(self.global_metrics),
            "cross_site_alerts_count": len(self.cross_site_alerts),
            "sync_statistics": dict(self.data_synchronizer.sync_statistics),
            "federation_statistics": self.stats,
        }

    async def start_federation(self):
        """Start the global monitoring federation"""
        logger.info("Starting Global Monitoring Federation")
        self.running = True

        # Start federation tasks
        tasks = [
            asyncio.create_task(self.collect_global_metrics()),
            asyncio.create_task(self.monitor_node_health()),
            asyncio.create_task(self.propagate_cross_site_alerts()),
        ]

        # Run federation
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_federation(self):
        """Stop the federation system"""
        logger.info("Stopping Global Monitoring Federation")
        self.running = False


def main():
    """Main entry point for Global Monitoring Federation"""
    federation = GlobalMonitoringFederation()

    try:
        asyncio.run(federation.start_federation())
    except KeyboardInterrupt:
        logger.info("Global monitoring federation stopped by user")
    except Exception as e:
        logger.error(f"Global monitoring federation error: {e}")


if __name__ == "__main__":
    main()
