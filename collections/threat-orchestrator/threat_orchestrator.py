#!/usr/bin/env python3
"""
Threat Orchestrator - Maelstrom Security Intelligence
Normalizes events from Suricata/Zeek/Wazuh and provides threat response coordination
"""

import json
import logging
import asyncio
import httpx
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
import uvicorn
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Threat Orchestrator", version="1.0.0")

# Configuration
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "http://slack-notifier:5001/webhook")
WAZUH_API_URL = os.getenv("WAZUH_API_URL", "http://wazuh-manager:55000")
AUTO_BLOCK = os.getenv("AUTO_BLOCK", "false").lower() == "true"


class ThreatSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatEvent:
    """Normalized threat event"""

    def __init__(self, raw_event: Dict[str, Any], source: str):
        self.id = f"{source}_{int(datetime.now().timestamp())}"
        self.timestamp = datetime.now().isoformat()
        self.source = source
        self.raw_event = raw_event
        self.normalized = self._normalize_event()
        self.severity = self._determine_severity()
        self.recommended_actions = self._get_recommended_actions()

    def _normalize_event(self) -> Dict[str, Any]:
        """Normalize event structure across different sources"""
        normalized = {
            "event_type": "unknown",
            "source_ip": None,
            "dest_ip": None,
            "source_port": None,
            "dest_port": None,
            "protocol": None,
            "signature": None,
            "description": None,
            "confidence": 0.5,
        }

        if self.source == "suricata":
            alert = self.raw_event.get("alert", {})
            normalized.update(
                {
                    "event_type": "ids_alert",
                    "source_ip": self.raw_event.get("src_ip"),
                    "dest_ip": self.raw_event.get("dest_ip"),
                    "source_port": self.raw_event.get("src_port"),
                    "dest_port": self.raw_event.get("dest_port"),
                    "protocol": self.raw_event.get("proto"),
                    "signature": alert.get("signature"),
                    "description": alert.get("signature"),
                    "confidence": min(alert.get("severity", 1) / 3, 1.0),
                }
            )

        elif self.source == "zeek":
            normalized.update(
                {
                    "event_type": "network_analysis",
                    "source_ip": self.raw_event.get("id.orig_h"),
                    "dest_ip": self.raw_event.get("id.resp_h"),
                    "source_port": self.raw_event.get("id.orig_p"),
                    "dest_port": self.raw_event.get("id.resp_p"),
                    "protocol": self.raw_event.get("proto"),
                    "description": f"Zeek {self.raw_event.get('_path', 'unknown')} event",
                    "confidence": 0.7,
                }
            )

        elif self.source == "wazuh":
            rule = self.raw_event.get("rule", {})
            normalized.update(
                {
                    "event_type": "siem_alert",
                    "source_ip": self.raw_event.get("data", {}).get("srcip"),
                    "signature": rule.get("description"),
                    "description": rule.get("description"),
                    "confidence": min(rule.get("level", 1) / 15, 1.0),
                }
            )

        return normalized

    def _determine_severity(self) -> ThreatSeverity:
        """Determine threat severity based on normalized event"""
        confidence = self.normalized.get("confidence", 0)
        signature = self.normalized.get("signature", "").lower()

        # Critical indicators
        if any(
            keyword in signature
            for keyword in ["exploit", "backdoor", "trojan", "malware"]
        ):
            return ThreatSeverity.CRITICAL

        # High severity indicators
        if confidence > 0.8 or any(
            keyword in signature for keyword in ["attack", "intrusion", "breach"]
        ):
            return ThreatSeverity.HIGH

        # Medium severity
        if confidence > 0.5 or any(
            keyword in signature for keyword in ["suspicious", "anomaly", "scan"]
        ):
            return ThreatSeverity.MEDIUM

        return ThreatSeverity.LOW

    def _get_recommended_actions(self) -> List[Dict[str, Any]]:
        """Get recommended response actions"""
        actions = []
        source_ip = self.normalized.get("source_ip")

        if self.severity == ThreatSeverity.CRITICAL:
            actions.extend(
                [
                    {
                        "type": "block_ip",
                        "target": source_ip,
                        "description": f"Block malicious IP {source_ip}",
                        "command": f"iptables -A INPUT -s {source_ip} -j DROP",
                        "auto_execute": False,
                        "runbook": "https://maelstrom.local/runbooks/critical-threat-response",
                    },
                    {
                        "type": "isolate_host",
                        "target": self.normalized.get("dest_ip"),
                        "description": "Consider isolating affected host",
                        "auto_execute": False,
                    },
                ]
            )

        elif self.severity == ThreatSeverity.HIGH:
            actions.append(
                {
                    "type": "monitor_ip",
                    "target": source_ip,
                    "description": f"Enhanced monitoring of IP {source_ip}",
                    "auto_execute": True,
                }
            )

        # Always recommend investigation for medium+ threats
        if self.severity in [
            ThreatSeverity.MEDIUM,
            ThreatSeverity.HIGH,
            ThreatSeverity.CRITICAL,
        ]:
            actions.append(
                {
                    "type": "investigate",
                    "target": source_ip,
                    "description": "Manual investigation recommended",
                    "runbook": f"https://maelstrom.local/runbooks/{self.severity.value}-threat-investigation",
                }
            )

        return actions


class ThreatOrchestrator:
    """Main threat orchestration engine"""

    def __init__(self):
        self.threat_events: List[ThreatEvent] = []
        self.blocked_ips: List[str] = []

    async def process_threat(self, event: ThreatEvent) -> Dict[str, Any]:
        """Process threat event and coordinate response"""
        self.threat_events.append(event)

        logger.info(
            f"Processing {event.severity.value} threat from {event.source}: {event.id}"
        )

        response = {
            "event_id": event.id,
            "severity": event.severity.value,
            "actions_taken": [],
            "manual_actions_required": [],
            "notifications_sent": [],
        }

        # Log to Loki
        await self._log_to_loki(event)

        # Send notifications based on severity
        if event.severity in [ThreatSeverity.HIGH, ThreatSeverity.CRITICAL]:
            await self._send_slack_alert(event)
            response["notifications_sent"].append("slack")

        # Process recommended actions
        for action in event.recommended_actions:
            if action.get("auto_execute") and AUTO_BLOCK:
                # In this implementation, we don't auto-execute
                # All actions require approval
                response["manual_actions_required"].append(action)
            else:
                response["manual_actions_required"].append(action)

        return response

    async def _log_to_loki(self, event: ThreatEvent):
        """Log threat event to Loki"""
        try:
            log_entry = {
                "streams": [
                    {
                        "stream": {
                            "job": "threat-orchestrator",
                            "host": "maelstrom",
                            "service": "security",
                            "severity": event.severity.value,
                            "source": event.source,
                        },
                        "values": [
                            [
                                str(int(datetime.now().timestamp() * 1000000000)),
                                json.dumps(
                                    {
                                        "event_id": event.id,
                                        "severity": event.severity.value,
                                        "normalized": event.normalized,
                                        "actions": event.recommended_actions,
                                    }
                                ),
                            ]
                        ],
                    }
                ]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{LOKI_URL}/loki/api/v1/push", json=log_entry
                )
                if response.status_code == 204:
                    logger.info(f"Logged threat event {event.id} to Loki")
        except Exception as e:
            logger.error(f"Error logging to Loki: {e}")

    async def _send_slack_alert(self, event: ThreatEvent):
        """Send threat alert to Slack"""
        try:
            severity_emoji = {
                ThreatSeverity.LOW: "🟢",
                ThreatSeverity.MEDIUM: "🟡",
                ThreatSeverity.HIGH: "🟠",
                ThreatSeverity.CRITICAL: "🔴",
            }

            actions_text = "\n".join(
                [
                    f"• {action['type']}: {action['description']}"
                    for action in event.recommended_actions[
                        :3
                    ]  # Limit to first 3 actions
                ]
            )

            message = {
                "text": f"🛡️ Threat Detected - {event.severity.value.upper()}",
                "attachments": [
                    {
                        "color": (
                            "danger"
                            if event.severity == ThreatSeverity.CRITICAL
                            else "warning"
                        ),
                        "fields": [
                            {
                                "title": f"Severity {severity_emoji[event.severity]}",
                                "value": event.severity.value.upper(),
                                "short": True,
                            },
                            {
                                "title": "Source",
                                "value": event.source.upper(),
                                "short": True,
                            },
                            {
                                "title": "Source IP",
                                "value": event.normalized.get("source_ip", "unknown"),
                                "short": True,
                            },
                            {
                                "title": "Confidence",
                                "value": f"{event.normalized.get('confidence', 0):.1%}",
                                "short": True,
                            },
                            {
                                "title": "Description",
                                "value": event.normalized.get(
                                    "description", "No description"
                                ),
                                "short": False,
                            },
                            {
                                "title": "Recommended Actions",
                                "value": actions_text
                                or "Manual investigation recommended",
                                "short": False,
                            },
                        ],
                    }
                ],
            }

            if event.recommended_actions and any(
                action.get("runbook") for action in event.recommended_actions
            ):
                runbook = next(
                    (
                        action["runbook"]
                        for action in event.recommended_actions
                        if action.get("runbook")
                    ),
                    None,
                )
                if runbook:
                    message["attachments"][0]["fields"].append(
                        {
                            "title": "Runbook",
                            "value": f"<{runbook}|Investigation Procedures>",
                            "short": False,
                        }
                    )

            async with httpx.AsyncClient() as client:
                response = await client.post(SLACK_WEBHOOK, json=message)
                if response.status_code == 200:
                    logger.info(f"Sent threat alert {event.id} to Slack")
        except Exception as e:
            logger.error(f"Error sending to Slack: {e}")


orchestrator = ThreatOrchestrator()


@app.get("/")
async def root():
    return {
        "service": "Threat Orchestrator",
        "status": "running",
        "auto_block_enabled": AUTO_BLOCK,
        "events_processed": len(orchestrator.threat_events),
    }


@app.post("/webhook/suricata")
async def receive_suricata_event(
    event_data: Dict[str, Any], background_tasks: BackgroundTasks
):
    """Receive Suricata IDS events"""
    threat_event = ThreatEvent(event_data, "suricata")
    background_tasks.add_task(orchestrator.process_threat, threat_event)
    return {"status": "received", "event_id": threat_event.id}


@app.post("/webhook/zeek")
async def receive_zeek_event(
    event_data: Dict[str, Any], background_tasks: BackgroundTasks
):
    """Receive Zeek network analysis events"""
    threat_event = ThreatEvent(event_data, "zeek")
    background_tasks.add_task(orchestrator.process_threat, threat_event)
    return {"status": "received", "event_id": threat_event.id}


@app.post("/webhook/wazuh")
async def receive_wazuh_event(
    event_data: Dict[str, Any], background_tasks: BackgroundTasks
):
    """Receive Wazuh SIEM events"""
    threat_event = ThreatEvent(event_data, "wazuh")
    background_tasks.add_task(orchestrator.process_threat, threat_event)
    return {"status": "received", "event_id": threat_event.id}


@app.get("/threats")
async def get_recent_threats(limit: int = 10):
    """Get recent threat events"""
    recent_events = orchestrator.threat_events[-limit:]
    return {
        "threats": [
            {
                "id": event.id,
                "timestamp": event.timestamp,
                "source": event.source,
                "severity": event.severity.value,
                "description": event.normalized.get("description"),
                "source_ip": event.normalized.get("source_ip"),
                "actions": len(event.recommended_actions),
            }
            for event in recent_events
        ]
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5003)
