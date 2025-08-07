#!/usr/bin/env python3
"""
Advanced Alert Orchestrator
Intelligent alerting system with dynamic thresholds, alert correlation, and multi-channel notifications
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import threading
from enum import Enum
import statistics
import hashlib

import requests
from influxdb import InfluxDBClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AlertStatus(Enum):
    """Alert status states"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

class NotificationChannel(Enum):
    """Notification channel types"""
    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    DASHBOARD = "dashboard"

@dataclass
class AlertRule:
    """Alert rule definition"""
    rule_id: str
    name: str
    description: str
    query: str
    metric_name: str
    threshold_operator: str  # >, <, >=, <=, ==, !=
    threshold_value: float
    severity: AlertSeverity
    duration: int  # seconds
    evaluation_interval: int  # seconds
    dynamic_threshold: bool = False
    correlation_rules: List[str] = None
    notification_channels: List[NotificationChannel] = None
    suppress_duration: int = 300  # 5 minutes default
    escalation_rules: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None

@dataclass
class Alert:
    """Alert instance"""
    alert_id: str
    rule_id: str
    title: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    source_metric: str
    source_value: float
    threshold_value: float
    first_seen: datetime
    last_seen: datetime
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notification_history: List[Dict[str, Any]] = None
    correlation_group: Optional[str] = None
    escalation_level: int = 0
    metadata: Dict[str, Any] = None

@dataclass
class NotificationTemplate:
    """Notification message template"""
    channel: NotificationChannel
    template_id: str
    subject_template: str
    body_template: str
    priority_mapping: Dict[AlertSeverity, str]
    rate_limit: int = 60  # seconds
    retry_count: int = 3

class DynamicThresholdCalculator:
    """Calculates dynamic thresholds based on historical data"""
    
    def __init__(self):
        self.metric_history = defaultdict(lambda: deque(maxlen=1000))
        self.threshold_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def update_metric_data(self, metric_name: str, value: float, timestamp: datetime):
        """Update metric history for threshold calculation"""
        self.metric_history[metric_name].append((timestamp, value))
        
        # Clear threshold cache for this metric
        if metric_name in self.threshold_cache:
            del self.threshold_cache[metric_name]
    
    def calculate_dynamic_threshold(self, metric_name: str, operator: str, 
                                  base_threshold: float, sensitivity: float = 2.0) -> float:
        """Calculate dynamic threshold based on historical data"""
        cache_key = f"{metric_name}:{operator}:{base_threshold}:{sensitivity}"
        
        # Check cache
        if cache_key in self.threshold_cache:
            cached_time, cached_value = self.threshold_cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self.cache_ttl:
                return cached_value
        
        history = self.metric_history[metric_name]
        if len(history) < 20:  # Need minimum data points
            return base_threshold
        
        # Extract recent values (last hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        recent_values = [value for timestamp, value in history if timestamp >= cutoff_time]
        
        if len(recent_values) < 10:
            recent_values = [value for _, value in list(history)[-50:]]  # Use last 50 points
        
        if not recent_values:
            return base_threshold
        
        try:
            mean_value = statistics.mean(recent_values)
            std_dev = statistics.stdev(recent_values) if len(recent_values) > 1 else 0
            
            # Calculate dynamic threshold based on statistical anomaly detection
            if operator in ['>', '>=']:
                # Upper threshold: mean + (sensitivity * std_dev)
                dynamic_threshold = mean_value + (sensitivity * std_dev)
                # Don't go below the base threshold
                threshold = max(base_threshold, dynamic_threshold)
            elif operator in ['<', '<=']:
                # Lower threshold: mean - (sensitivity * std_dev)  
                dynamic_threshold = mean_value - (sensitivity * std_dev)
                # Don't go above the base threshold
                threshold = min(base_threshold, dynamic_threshold)
            else:
                threshold = base_threshold
            
            # Cache the result
            self.threshold_cache[cache_key] = (datetime.utcnow(), threshold)
            
            logger.debug(f"Dynamic threshold for {metric_name}: {threshold:.2f} (base: {base_threshold:.2f})")
            return threshold
            
        except Exception as e:
            logger.error(f"Error calculating dynamic threshold for {metric_name}: {e}")
            return base_threshold

class AlertCorrelationEngine:
    """Correlates related alerts to reduce noise"""
    
    def __init__(self):
        self.correlation_groups = {}
        self.correlation_rules = {}
        self.alert_relationships = defaultdict(set)
    
    def add_correlation_rule(self, rule_id: str, correlation_config: Dict[str, Any]):
        """Add alert correlation rule"""
        self.correlation_rules[rule_id] = correlation_config
    
    def correlate_alerts(self, new_alert: Alert, active_alerts: List[Alert]) -> Optional[str]:
        """Correlate new alert with existing alerts"""
        # Time-based correlation (alerts within 5 minutes)
        correlation_window = timedelta(minutes=5)
        recent_alerts = [
            alert for alert in active_alerts 
            if abs((new_alert.first_seen - alert.first_seen).total_seconds()) <= correlation_window.total_seconds()
        ]
        
        # Service-based correlation
        service_correlation = self.correlate_by_service(new_alert, recent_alerts)
        if service_correlation:
            return service_correlation
        
        # Host-based correlation  
        host_correlation = self.correlate_by_host(new_alert, recent_alerts)
        if host_correlation:
            return host_correlation
        
        # Metric-based correlation
        metric_correlation = self.correlate_by_metric(new_alert, recent_alerts)
        if metric_correlation:
            return metric_correlation
        
        # Create new correlation group
        correlation_id = f"corr-{int(time.time())}-{hashlib.md5(new_alert.alert_id.encode()).hexdigest()[:8]}"
        self.correlation_groups[correlation_id] = [new_alert.alert_id]
        
        return correlation_id
    
    def correlate_by_service(self, new_alert: Alert, recent_alerts: List[Alert]) -> Optional[str]:
        """Correlate alerts by service"""
        new_service = new_alert.metadata.get('service') if new_alert.metadata else None
        if not new_service:
            return None
        
        for alert in recent_alerts:
            if alert.metadata and alert.metadata.get('service') == new_service:
                if alert.correlation_group:
                    return alert.correlation_group
        
        return None
    
    def correlate_by_host(self, new_alert: Alert, recent_alerts: List[Alert]) -> Optional[str]:
        """Correlate alerts by host/node"""
        new_host = new_alert.metadata.get('host') if new_alert.metadata else None
        if not new_host:
            return None
        
        for alert in recent_alerts:
            if alert.metadata and alert.metadata.get('host') == new_host:
                if alert.correlation_group:
                    return alert.correlation_group
        
        return None
    
    def correlate_by_metric(self, new_alert: Alert, recent_alerts: List[Alert]) -> Optional[str]:
        """Correlate alerts by metric type"""
        metric_type = new_alert.source_metric.split('_')[0]  # e.g., 'cpu' from 'cpu_usage'
        
        for alert in recent_alerts:
            alert_metric_type = alert.source_metric.split('_')[0]
            if alert_metric_type == metric_type:
                if alert.correlation_group:
                    return alert.correlation_group
        
        return None

class NotificationManager:
    """Manages multi-channel notifications with rate limiting and retries"""
    
    def __init__(self):
        self.notification_history = deque(maxlen=10000)
        self.rate_limiters = defaultdict(lambda: deque(maxlen=100))
        self.templates = {}
        self.channel_configs = {}
        
        # Load default templates
        self.load_default_templates()
    
    def load_default_templates(self):
        """Load default notification templates"""
        self.templates = {
            NotificationChannel.SLACK: NotificationTemplate(
                channel=NotificationChannel.SLACK,
                template_id="slack_default",
                subject_template="{severity} Alert: {title}",
                body_template="""🚨 *{severity.upper()} Alert*
*Title:* {title}
*Description:* {description}
*Source:* {source_metric} = {source_value}
*Threshold:* {threshold_value}
*Time:* {first_seen}
*Rule:* {rule_id}
*Alert ID:* {alert_id}""",
                priority_mapping={
                    AlertSeverity.CRITICAL: "<!channel>",
                    AlertSeverity.HIGH: "<!here>",
                    AlertSeverity.MEDIUM: "",
                    AlertSeverity.LOW: "",
                    AlertSeverity.INFO: ""
                }
            ),
            NotificationChannel.EMAIL: NotificationTemplate(
                channel=NotificationChannel.EMAIL,
                template_id="email_default",
                subject_template="[{severity.upper()}] {title}",
                body_template="""Alert Details:

Title: {title}
Description: {description}
Severity: {severity.upper()}

Metric Information:
- Source: {source_metric}
- Current Value: {source_value}
- Threshold: {threshold_value}
- First Seen: {first_seen}
- Last Seen: {last_seen}

Alert Management:
- Alert ID: {alert_id}
- Rule ID: {rule_id}
- Status: {status.value}

This is an automated alert from the Maelstrom Monitoring System.""",
                priority_mapping={
                    AlertSeverity.CRITICAL: "High",
                    AlertSeverity.HIGH: "High", 
                    AlertSeverity.MEDIUM: "Normal",
                    AlertSeverity.LOW: "Low",
                    AlertSeverity.INFO: "Low"
                }
            )
        }
    
    def is_rate_limited(self, channel: NotificationChannel, alert_rule_id: str, 
                       rate_limit: int) -> bool:
        """Check if notification is rate limited"""
        key = f"{channel.value}:{alert_rule_id}"
        now = datetime.utcnow()
        
        # Clean old entries
        while (self.rate_limiters[key] and 
               (now - self.rate_limiters[key][0]).total_seconds() > rate_limit):
            self.rate_limiters[key].popleft()
        
        # Check if we can send
        if len(self.rate_limiters[key]) >= 1:  # 1 notification per rate_limit period
            return True
        
        # Add current time
        self.rate_limiters[key].append(now)
        return False
    
    async def send_notification(self, alert: Alert, rule: AlertRule, 
                              channels: List[NotificationChannel] = None):
        """Send notification to specified channels"""
        if not channels:
            channels = rule.notification_channels or [NotificationChannel.SLACK]
        
        notification_tasks = []
        for channel in channels:
            if self.is_rate_limited(channel, rule.rule_id, rule.suppress_duration):
                logger.info(f"Notification rate limited for {channel.value}:{rule.rule_id}")
                continue
            
            task = asyncio.create_task(self.send_channel_notification(alert, rule, channel))
            notification_tasks.append(task)
        
        # Send notifications concurrently
        if notification_tasks:
            results = await asyncio.gather(*notification_tasks, return_exceptions=True)
            
            # Log results
            for i, result in enumerate(results):
                channel = channels[i] if i < len(channels) else "unknown"
                if isinstance(result, Exception):
                    logger.error(f"Notification failed for {channel}: {result}")
                else:
                    logger.info(f"Notification sent successfully to {channel}")
    
    async def send_channel_notification(self, alert: Alert, rule: AlertRule, 
                                      channel: NotificationChannel):
        """Send notification to specific channel"""
        try:
            template = self.templates.get(channel)
            if not template:
                logger.error(f"No template found for channel {channel}")
                return
            
            # Format message
            message_data = self.format_notification_message(alert, rule, template)
            
            # Send based on channel type
            if channel == NotificationChannel.SLACK:
                await self.send_slack_notification(message_data, template)
            elif channel == NotificationChannel.EMAIL:
                await self.send_email_notification(message_data, template)
            elif channel == NotificationChannel.WEBHOOK:
                await self.send_webhook_notification(message_data, alert)
            else:
                logger.warning(f"Channel {channel} not implemented yet")
            
            # Record notification
            notification_record = {
                'alert_id': alert.alert_id,
                'channel': channel.value,
                'timestamp': datetime.utcnow(),
                'success': True
            }
            self.notification_history.append(notification_record)
            
        except Exception as e:
            logger.error(f"Error sending {channel.value} notification: {e}")
            notification_record = {
                'alert_id': alert.alert_id,
                'channel': channel.value,
                'timestamp': datetime.utcnow(),
                'success': False,
                'error': str(e)
            }
            self.notification_history.append(notification_record)
    
    def format_notification_message(self, alert: Alert, rule: AlertRule, 
                                   template: NotificationTemplate) -> Dict[str, Any]:
        """Format notification message using template"""
        context = {
            'alert_id': alert.alert_id,
            'rule_id': alert.rule_id,
            'title': alert.title,
            'description': alert.description,
            'severity': alert.severity,
            'status': alert.status,
            'source_metric': alert.source_metric,
            'source_value': alert.source_value,
            'threshold_value': alert.threshold_value,
            'first_seen': alert.first_seen.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'last_seen': alert.last_seen.strftime('%Y-%m-%d %H:%M:%S UTC'),
        }
        
        subject = template.subject_template.format(**context)
        body = template.body_template.format(**context)
        priority = template.priority_mapping.get(alert.severity, "")
        
        return {
            'subject': subject,
            'body': body,
            'priority': priority,
            'severity': alert.severity.value,
            'alert_id': alert.alert_id
        }
    
    async def send_slack_notification(self, message_data: Dict[str, Any], 
                                    template: NotificationTemplate):
        """Send Slack notification"""
        try:
            from secrets_helper import get_slack_webhook
            webhook_url = get_slack_webhook()
            
            if not webhook_url:
                logger.warning("Slack webhook URL not configured")
                return
            
            # Determine color based on severity
            color_map = {
                'critical': 'danger',
                'high': 'warning', 
                'medium': 'warning',
                'low': 'good',
                'info': 'good'
            }
            
            slack_message = {
                'text': f"{message_data['priority']} {message_data['subject']}",
                'attachments': [
                    {
                        'color': color_map.get(message_data['severity'], 'warning'),
                        'text': message_data['body'],
                        'footer': 'Maelstrom Monitoring System',
                        'ts': int(time.time())
                    }
                ]
            }
            
            response = await asyncio.to_thread(
                requests.post, webhook_url, json=slack_message, timeout=10
            )
            response.raise_for_status()
            
        except Exception as e:
            raise Exception(f"Slack notification failed: {e}")
    
    async def send_email_notification(self, message_data: Dict[str, Any], 
                                    template: NotificationTemplate):
        """Send email notification"""
        # Email implementation would go here
        # For now, just log the email content
        logger.info(f"Email notification: {message_data['subject']}")
        logger.debug(f"Email body: {message_data['body']}")
    
    async def send_webhook_notification(self, message_data: Dict[str, Any], alert: Alert):
        """Send webhook notification"""
        # Generic webhook implementation
        webhook_url = alert.metadata.get('webhook_url') if alert.metadata else None
        if not webhook_url:
            logger.warning("Webhook URL not configured for alert")
            return
        
        payload = {
            'alert': asdict(alert),
            'message': message_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        response = await asyncio.to_thread(
            requests.post, webhook_url, json=payload, timeout=10
        )
        response.raise_for_status()

class AlertOrchestrator:
    """Main alert orchestration system"""
    
    def __init__(self):
        self.running = False
        self.alert_rules = {}
        self.active_alerts = {}
        self.alert_history = deque(maxlen=50000)
        
        # Component systems
        self.threshold_calculator = DynamicThresholdCalculator()
        self.correlation_engine = AlertCorrelationEngine()
        self.notification_manager = NotificationManager()
        
        # Processing queues
        self.metric_queue = asyncio.Queue(maxsize=10000)
        self.alert_queue = asyncio.Queue(maxsize=1000)
        
        # Statistics
        self.stats = {
            'rules_loaded': 0,
            'alerts_generated': 0,
            'alerts_resolved': 0,
            'notifications_sent': 0,
            'correlation_groups': 0,
            'dynamic_thresholds_calculated': 0
        }
        
        # Initialize database and rules
        self.setup_database()
        self.load_default_rules()
    
    def setup_database(self):
        """Setup InfluxDB connection for metrics and alerts"""
        try:
            from secrets_helper import get_database_url
            db_url = get_database_url('influxdb')
            
            # Parse connection URL
            if '@' in db_url:
                auth_part = db_url.split('//')[1].split('@')[0]
                username, password = auth_part.split(':')
                host_part = db_url.split('@')[1].split(':')[0]
                port = 8086
            else:
                username, password = None, None
                host_part = db_url.split('//')[1].split(':')[0]
                port = 8086
            
            self.influxdb_client = InfluxDBClient(
                host=host_part,
                port=port,
                username=username,
                password=password,
                database='alerting'
            )
            
            # Create database if it doesn't exist
            try:
                databases = self.influxdb_client.get_list_database()
                if not any(db['name'] == 'alerting' for db in databases):
                    self.influxdb_client.create_database('alerting')
                    logger.info("Created alerting database")
            except Exception as e:
                logger.warning(f"Could not create database: {e}")
            
            logger.info("InfluxDB connection established for alerting")
            
        except Exception as e:
            logger.error(f"Failed to setup InfluxDB connection: {e}")
            self.influxdb_client = None
    
    def load_default_rules(self):
        """Load default alert rules"""
        default_rules = [
            AlertRule(
                rule_id="high_cpu_usage",
                name="High CPU Usage",
                description="CPU usage exceeds threshold",
                query="SELECT mean(usage_percent) FROM cpu WHERE time > now() - 5m GROUP BY host",
                metric_name="cpu_usage",
                threshold_operator=">",
                threshold_value=80.0,
                severity=AlertSeverity.HIGH,
                duration=300,  # 5 minutes
                evaluation_interval=60,
                dynamic_threshold=True,
                notification_channels=[NotificationChannel.SLACK],
                escalation_rules=[
                    {'level': 1, 'threshold': 90.0, 'duration': 600, 'severity': AlertSeverity.CRITICAL}
                ]
            ),
            AlertRule(
                rule_id="high_memory_usage",
                name="High Memory Usage", 
                description="Memory usage exceeds threshold",
                query="SELECT mean(usage_percent) FROM memory WHERE time > now() - 5m GROUP BY host",
                metric_name="memory_usage",
                threshold_operator=">",
                threshold_value=85.0,
                severity=AlertSeverity.HIGH,
                duration=300,
                evaluation_interval=60,
                dynamic_threshold=True,
                notification_channels=[NotificationChannel.SLACK]
            ),
            AlertRule(
                rule_id="disk_space_low",
                name="Low Disk Space",
                description="Disk space usage exceeds threshold",
                query="SELECT mean(usage_percent) FROM disk WHERE time > now() - 5m GROUP BY host,device",
                metric_name="disk_usage",
                threshold_operator=">",
                threshold_value=90.0,
                severity=AlertSeverity.CRITICAL,
                duration=60,
                evaluation_interval=300,  # Check every 5 minutes
                notification_channels=[NotificationChannel.SLACK],
                escalation_rules=[
                    {'level': 1, 'threshold': 95.0, 'duration': 300, 'severity': AlertSeverity.CRITICAL}
                ]
            ),
            AlertRule(
                rule_id="service_down",
                name="Service Down",
                description="Service is not responding",
                query="SELECT last(status) FROM service_health WHERE time > now() - 2m GROUP BY service",
                metric_name="service_status",
                threshold_operator="==",
                threshold_value=0.0,  # 0 = down, 1 = up
                severity=AlertSeverity.CRITICAL,
                duration=120,
                evaluation_interval=60,
                notification_channels=[NotificationChannel.SLACK],
                suppress_duration=600  # 10 minutes
            ),
            AlertRule(
                rule_id="high_network_latency",
                name="High Network Latency",
                description="Network latency exceeds threshold",
                query="SELECT mean(response_time) FROM network_metrics WHERE time > now() - 5m GROUP BY host",
                metric_name="network_latency",
                threshold_operator=">",
                threshold_value=100.0,  # milliseconds
                severity=AlertSeverity.MEDIUM,
                duration=300,
                evaluation_interval=60,
                dynamic_threshold=True,
                notification_channels=[NotificationChannel.SLACK]
            )
        ]
        
        for rule in default_rules:
            self.add_alert_rule(rule)
        
        logger.info(f"Loaded {len(default_rules)} default alert rules")
    
    def add_alert_rule(self, rule: AlertRule):
        """Add or update alert rule"""
        self.alert_rules[rule.rule_id] = rule
        self.stats['rules_loaded'] += 1
        
        # Add correlation rules if specified
        if rule.correlation_rules:
            self.correlation_engine.add_correlation_rule(
                rule.rule_id, 
                {'related_rules': rule.correlation_rules}
            )
        
        logger.info(f"Added alert rule: {rule.rule_id}")
    
    async def evaluate_metric(self, metric_name: str, value: float, 
                            metadata: Dict[str, Any] = None):
        """Evaluate metric against alert rules"""
        try:
            # Update threshold calculator
            self.threshold_calculator.update_metric_data(metric_name, value, datetime.utcnow())
            
            # Find applicable rules
            applicable_rules = [
                rule for rule in self.alert_rules.values()
                if rule.metric_name == metric_name or metric_name.startswith(rule.metric_name)
            ]
            
            # Evaluate each rule
            for rule in applicable_rules:
                await self.evaluate_rule(rule, value, metadata or {})
                
        except Exception as e:
            logger.error(f"Error evaluating metric {metric_name}: {e}")
    
    async def evaluate_rule(self, rule: AlertRule, value: float, metadata: Dict[str, Any]):
        """Evaluate specific alert rule"""
        try:
            # Calculate threshold (dynamic or static)
            if rule.dynamic_threshold:
                threshold = self.threshold_calculator.calculate_dynamic_threshold(
                    rule.metric_name, rule.threshold_operator, rule.threshold_value
                )
                self.stats['dynamic_thresholds_calculated'] += 1
            else:
                threshold = rule.threshold_value
            
            # Check if threshold is breached
            threshold_breached = self.check_threshold(value, rule.threshold_operator, threshold)
            
            alert_key = f"{rule.rule_id}:{metadata.get('host', 'unknown')}"
            
            if threshold_breached:
                # Check if we already have an active alert
                if alert_key in self.active_alerts:
                    # Update existing alert
                    existing_alert = self.active_alerts[alert_key]
                    existing_alert.last_seen = datetime.utcnow()
                    existing_alert.source_value = value
                else:
                    # Create new alert
                    await self.create_alert(rule, value, threshold, metadata)
            else:
                # Check if we should resolve an existing alert
                if alert_key in self.active_alerts:
                    await self.resolve_alert(self.active_alerts[alert_key])
        
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
    
    def check_threshold(self, value: float, operator: str, threshold: float) -> bool:
        """Check if value breaches threshold"""
        if operator == '>':
            return value > threshold
        elif operator == '>=':
            return value >= threshold
        elif operator == '<':
            return value < threshold
        elif operator == '<=':
            return value <= threshold
        elif operator == '==':
            return abs(value - threshold) < 0.001  # Float comparison
        elif operator == '!=':
            return abs(value - threshold) >= 0.001
        else:
            logger.warning(f"Unknown threshold operator: {operator}")
            return False
    
    async def create_alert(self, rule: AlertRule, value: float, threshold: float, 
                         metadata: Dict[str, Any]):
        """Create new alert"""
        try:
            alert_id = f"alert-{rule.rule_id}-{int(time.time())}-{hashlib.md5(str(metadata).encode()).hexdigest()[:8]}"
            
            alert = Alert(
                alert_id=alert_id,
                rule_id=rule.rule_id,
                title=rule.name,
                description=rule.description,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                source_metric=rule.metric_name,
                source_value=value,
                threshold_value=threshold,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                metadata=metadata,
                notification_history=[]
            )
            
            # Correlate with existing alerts
            correlation_group = self.correlation_engine.correlate_alerts(
                alert, list(self.active_alerts.values())
            )
            alert.correlation_group = correlation_group
            
            # Store alert
            alert_key = f"{rule.rule_id}:{metadata.get('host', 'unknown')}"
            self.active_alerts[alert_key] = alert
            self.alert_history.append(alert)
            self.stats['alerts_generated'] += 1
            
            # Send notifications
            await self.notification_manager.send_notification(alert, rule)
            self.stats['notifications_sent'] += 1
            
            # Store in database
            await self.store_alert(alert)
            
            logger.warning(f"Alert created: {alert.title} (ID: {alert.alert_id})")
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
    
    async def resolve_alert(self, alert: Alert):
        """Resolve active alert"""
        try:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            
            # Remove from active alerts
            alert_key = f"{alert.rule_id}:{alert.metadata.get('host', 'unknown') if alert.metadata else 'unknown'}"
            if alert_key in self.active_alerts:
                del self.active_alerts[alert_key]
            
            self.stats['alerts_resolved'] += 1
            
            # Store resolution in database
            await self.store_alert(alert)
            
            logger.info(f"Alert resolved: {alert.title} (ID: {alert.alert_id})")
            
        except Exception as e:
            logger.error(f"Error resolving alert {alert.alert_id}: {e}")
    
    async def store_alert(self, alert: Alert):
        """Store alert in database"""
        if not self.influxdb_client:
            return
        
        try:
            points = [{
                'measurement': 'alerts',
                'tags': {
                    'alert_id': alert.alert_id,
                    'rule_id': alert.rule_id,
                    'severity': alert.severity.value,
                    'status': alert.status.value,
                    'source_metric': alert.source_metric,
                    'host': alert.metadata.get('host', 'unknown') if alert.metadata else 'unknown',
                    'service': alert.metadata.get('service', 'unknown') if alert.metadata else 'unknown'
                },
                'fields': {
                    'source_value': alert.source_value,
                    'threshold_value': alert.threshold_value,
                    'title': alert.title,
                    'description': alert.description,
                    'correlation_group': alert.correlation_group or '',
                    'escalation_level': alert.escalation_level
                },
                'time': alert.last_seen
            }]
            
            self.influxdb_client.write_points(points)
            
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    async def process_metrics_stream(self):
        """Process incoming metrics for alert evaluation"""
        while self.running:
            try:
                # Get metrics from various sources
                await self.collect_system_metrics()
                await self.collect_service_metrics()
                await self.collect_application_metrics()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error processing metrics stream: {e}")
                await asyncio.sleep(60)
    
    async def collect_system_metrics(self):
        """Collect system metrics from various sources"""
        try:
            # Query InfluxDB for recent metrics
            if not self.influxdb_client:
                return
            
            # CPU metrics
            cpu_query = "SELECT mean(usage_percent) FROM cpu WHERE time > now() - 2m GROUP BY host"
            cpu_result = self.influxdb_client.query(cpu_query)
            
            for point in cpu_result.get_points():
                host = point.get('host', 'unknown')
                cpu_value = point.get('mean', 0)
                await self.evaluate_metric('cpu_usage', cpu_value, {'host': host, 'service': 'system'})
            
            # Memory metrics
            memory_query = "SELECT mean(usage_percent) FROM memory WHERE time > now() - 2m GROUP BY host"
            memory_result = self.influxdb_client.query(memory_query)
            
            for point in memory_result.get_points():
                host = point.get('host', 'unknown')
                memory_value = point.get('mean', 0)
                await self.evaluate_metric('memory_usage', memory_value, {'host': host, 'service': 'system'})
            
            # Disk metrics
            disk_query = "SELECT mean(usage_percent) FROM disk WHERE time > now() - 2m GROUP BY host,device"
            disk_result = self.influxdb_client.query(disk_query)
            
            for point in disk_result.get_points():
                host = point.get('host', 'unknown')
                device = point.get('device', 'unknown')
                disk_value = point.get('mean', 0)
                await self.evaluate_metric('disk_usage', disk_value, {
                    'host': host, 
                    'device': device, 
                    'service': 'system'
                })
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    async def collect_service_metrics(self):
        """Collect service health metrics"""
        try:
            if not self.influxdb_client:
                return
            
            # Service health check
            health_query = "SELECT last(status) FROM service_health WHERE time > now() - 5m GROUP BY service"
            health_result = self.influxdb_client.query(health_query)
            
            for point in health_result.get_points():
                service = point.get('service', 'unknown')
                status = point.get('last', 1)  # Default to up
                await self.evaluate_metric('service_status', status, {
                    'service': service,
                    'host': 'monitoring_server'
                })
            
        except Exception as e:
            logger.error(f"Error collecting service metrics: {e}")
    
    async def collect_application_metrics(self):
        """Collect application-specific metrics"""
        try:
            if not self.influxdb_client:
                return
            
            # Network latency
            network_query = "SELECT mean(response_time) FROM network_metrics WHERE time > now() - 2m GROUP BY host"
            network_result = self.influxdb_client.query(network_query)
            
            for point in network_result.get_points():
                host = point.get('host', 'unknown')
                latency = point.get('mean', 0)
                await self.evaluate_metric('network_latency', latency, {
                    'host': host,
                    'service': 'network'
                })
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
    
    async def cleanup_resolved_alerts(self):
        """Clean up old resolved alerts"""
        while self.running:
            try:
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                # Remove old alerts from history
                while (self.alert_history and 
                       self.alert_history[0].resolved_at and 
                       self.alert_history[0].resolved_at < cutoff_time):
                    self.alert_history.popleft()
                
                await asyncio.sleep(3600)  # Clean up every hour
                
            except Exception as e:
                logger.error(f"Error cleaning up alerts: {e}")
                await asyncio.sleep(1800)  # Retry in 30 minutes
    
    def get_alerting_stats(self) -> Dict[str, Any]:
        """Get current alerting statistics"""
        return {
            'active_alerts': len(self.active_alerts),
            'total_rules': len(self.alert_rules),
            'correlation_groups': len(self.correlation_engine.correlation_groups),
            'notification_history': len(self.notification_manager.notification_history),
            'alert_history': len(self.alert_history),
            'statistics': self.stats,
            'severity_breakdown': {
                severity.value: sum(1 for alert in self.active_alerts.values() 
                                  if alert.severity == severity)
                for severity in AlertSeverity
            }
        }
    
    async def start_alerting(self):
        """Start the alert orchestration system"""
        logger.info("Starting Advanced Alert Orchestrator")
        self.running = True
        
        # Start processing tasks
        tasks = [
            asyncio.create_task(self.process_metrics_stream()),
            asyncio.create_task(self.cleanup_resolved_alerts())
        ]
        
        # Run alerting tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_alerting(self):
        """Stop the alerting system"""
        logger.info("Stopping Advanced Alert Orchestrator")
        self.running = False

def main():
    """Main entry point for Alert Orchestrator"""
    orchestrator = AlertOrchestrator()
    
    try:
        asyncio.run(orchestrator.start_alerting())
    except KeyboardInterrupt:
        logger.info("Alert orchestrator stopped by user")
    except Exception as e:
        logger.error(f"Alert orchestrator error: {e}")

if __name__ == "__main__":
    main()