#!/usr/bin/env python3
"""
AutoOps Service - Maelstrom Monitoring Plane
Consumes Prometheus alerts and proposes infrastructure actions
"""

import json
import logging
import httpx
import os
from datetime import datetime
from typing import Dict, List, Any
from fastapi import FastAPI, BackgroundTasks
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AutoOps Service", version="1.0.0")

# Configuration
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "http://slack-notifier:5001/webhook")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
APPROVAL_REQUIRED = os.getenv("APPROVAL_REQUIRED", "true").lower() == "true"
DOCKER_BIN = os.getenv("DOCKER", "docker")


class ActionProposer:
    """Proposes actions based on alert patterns"""

    def __init__(self):
        self.action_history: List[Dict] = []

    def analyze_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze alert and propose action"""
        labels = alert.get("labels", {})

        alertname = labels.get("alertname", "")
        host = labels.get("host", "")
        service = labels.get("service", "")
        severity = labels.get("severity", "")

        proposal = {
            "alert_id": f"{alertname}_{host}_{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "alert_name": alertname,
            "host": host,
            "service": service,
            "severity": severity,
            "proposed_actions": [],
            "confidence": 0.0,
            "requires_approval": True,
        }

        # Action proposals based on alert patterns
        if "Down" in alertname or "Unreachable" in alertname:
            proposal["proposed_actions"].append(
                {
                    "type": "restart_service",
                    "target": service or host,
                    "command": f"{DOCKER_BIN} compose restart {service}",
                    "rationale": f"Service {service} appears to be down",
                }
            )
            proposal["confidence"] = 0.8

        elif "High" in alertname and "CPU" in alertname:
            proposal["proposed_actions"].append(
                {
                    "type": "scale_resources",
                    "target": host,
                    "command": "investigate_cpu_usage",
                    "rationale": "High CPU usage detected, investigation needed",
                }
            )
            proposal["confidence"] = 0.6

        elif "Memory" in alertname and "High" in alertname:
            proposal["proposed_actions"].append(
                {
                    "type": "memory_cleanup",
                    "target": host,
                    "command": "docker system prune -f",
                    "rationale": "High memory usage, cleanup recommended",
                }
            )
            proposal["confidence"] = 0.7

        elif "Disk" in alertname and ("Full" in alertname or "High" in alertname):
            proposal["proposed_actions"].append(
                {
                    "type": "disk_cleanup",
                    "target": host,
                    "command": "cleanup_logs_and_cache",
                    "rationale": "Disk space issue detected",
                }
            )
            proposal["confidence"] = 0.9

        else:
            proposal["proposed_actions"].append(
                {
                    "type": "investigate",
                    "target": host or "unknown",
                    "command": "manual_investigation_required",
                    "rationale": f"Unknown alert pattern: {alertname}",
                }
            )
            proposal["confidence"] = 0.3

        return proposal

    async def log_proposal_to_loki(self, proposal: Dict[str, Any]):
        """Log action proposal to Loki"""
        try:
            log_entry = {
                "streams": [
                    {
                        "stream": {
                            "job": "autoops",
                            "host": "maelstrom",
                            "service": "autoops",
                            "level": "info",
                        },
                        "values": [
                            [
                                str(int(datetime.now().timestamp() * 1000000000)),
                                json.dumps(proposal),
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
                    logger.info(f"Logged proposal {proposal['alert_id']} to Loki")
                else:
                    logger.error(f"Failed to log to Loki: {response.status_code}")
        except Exception as e:
            logger.error(f"Error logging to Loki: {e}")

    async def notify_slack(self, proposal: Dict[str, Any]):
        """Send action proposal to Slack"""
        try:
            actions_text = "\n".join(
                [
                    f"• {action['type']}: {action['rationale']}"
                    for action in proposal["proposed_actions"]
                ]
            )

            confidence_emoji = (
                "🟢"
                if proposal["confidence"] > 0.7
                else "🟡" if proposal["confidence"] > 0.4 else "🔴"
            )

            message = {
                "text": "🤖 AutoOps Action Proposal",
                "attachments": [
                    {
                        "color": "warning" if proposal["requires_approval"] else "good",
                        "fields": [
                            {
                                "title": "Alert",
                                "value": f"{proposal['alert_name']} on {proposal['host']}",
                                "short": True,
                            },
                            {
                                "title": "Severity",
                                "value": proposal["severity"].upper(),
                                "short": True,
                            },
                            {
                                "title": f"Confidence {confidence_emoji}",
                                "value": f"{proposal['confidence']:.1%}",
                                "short": True,
                            },
                            {
                                "title": "Approval Required",
                                "value": (
                                    "✅ Yes"
                                    if proposal["requires_approval"]
                                    else "❌ No"
                                ),
                                "short": True,
                            },
                            {
                                "title": "Proposed Actions",
                                "value": actions_text,
                                "short": False,
                            },
                        ],
                    }
                ],
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(SLACK_WEBHOOK, json=message)
                if response.status_code == 200:
                    logger.info(f"Sent proposal {proposal['alert_id']} to Slack")
                else:
                    logger.error(f"Failed to send to Slack: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending to Slack: {e}")


proposer = ActionProposer()


@app.get("/")
async def root():
    return {
        "service": "AutoOps",
        "status": "running",
        "approval_mode": APPROVAL_REQUIRED,
    }


@app.post("/webhook/prometheus")
async def receive_prometheus_alert(
    alert_data: Dict[str, Any], background_tasks: BackgroundTasks
):
    """Receive Prometheus webhooks and process alerts"""
    logger.info(f"Received alert webhook: {alert_data}")

    alerts = alert_data.get("alerts", [])
    for alert in alerts:
        if alert.get("status") == "firing":
            proposal = proposer.analyze_alert(alert)
            proposer.action_history.append(proposal)

            # Log and notify in background
            background_tasks.add_task(proposer.log_proposal_to_loki, proposal)
            background_tasks.add_task(proposer.notify_slack, proposal)

    return {"status": "processed", "alerts_count": len(alerts)}


@app.get("/proposals")
async def get_proposals():
    """Get recent action proposals"""
    return {"proposals": proposer.action_history[-10:]}  # Last 10 proposals


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5002)
