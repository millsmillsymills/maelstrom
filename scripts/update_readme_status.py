#!/usr/bin/env python3
"""
README Status Update Script for Maelstrom Monitoring Stack
Updates the dynamic status block in README.md with current service health information
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import json as _json_for_api
import os as _os


BASE_COMPOSE_PATH = "/home/mills/base.yml"


def _get_base_project_container_ids() -> List[str]:
    """Return container IDs for services defined by base.yml using docker compose.

    Falls back to empty list if compose is unavailable or returns nothing.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                BASE_COMPOSE_PATH,
                "ps",
                "-q",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return ids
    except Exception:
        return []


def get_docker_service_status() -> Tuple[int, int, List[str]]:
    """Get Docker service status information, focusing on core (base.yml) services.

    Preference order:
      1) Use `docker compose -f base.yml ps -q` container IDs
      2) Fallback to all containers from `docker ps` (legacy)
    """
    try:
        container_ids = _get_base_project_container_ids()

        # Build a map of services in base.yml that are gated behind profiles
        service_profiles: Dict[str, bool] = {}
        try:
            with open(BASE_COMPOSE_PATH, "r") as f:
                lines = f.readlines()
            in_services = False
            current_service = None
            for raw in lines:
                line = raw.rstrip("\n")
                if line.strip() == "services:":
                    in_services = True
                    current_service = None
                    continue
                if not in_services:
                    continue
                # Detect new service block (two-space indent, name:)
                if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
                    name = line.strip()[:-1]
                    current_service = name
                    # Initialize as not having profiles
                    service_profiles[current_service] = False
                    continue
                # Inside a service block, detect a profiles key
                if current_service and line.strip().startswith("profiles:"):
                    service_profiles[current_service] = True
                # Heuristic: if dedented back to top-level, leave services section
                if line and not line.startswith("  ") and not line.startswith(" "):
                    in_services = False
                    current_service = None
        except Exception:
            # On any parsing issue, default to empty map (count all)
            service_profiles = {}

        entries: List[Tuple[str, str, str]] = []  # (name, status, state)

        if container_ids:
            for cid in container_ids:
                insp = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        cid,
                        "--format",
                        "{{.Name}}:{{.State.Status}}:{{ index .Config.Labels \"com.docker.compose.service\" }}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                line = insp.stdout.strip().lstrip("/")
                if not line:
                    continue
                parts = line.split(":")
                name = parts[0]
                state = parts[1] if len(parts) > 1 else "unknown"
                svc = parts[2] if len(parts) > 2 else ""
                # Skip containers for services that are profile-gated in base.yml
                if svc and service_profiles.get(svc, False):
                    continue
                # Normalize to legacy tuple format
                entries.append((name, state, state))
        else:
            # Fallback: all containers (older behavior)
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}:{{.Status}}:{{.State}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":")
                # name, status (human), state (machine)
                if len(parts) >= 3:
                    entries.append((parts[0], parts[1], parts[2]))

        healthy_count = 0
        unhealthy_services = []
        total_services = 0

        for name, status, state in entries:
            total_services += 1

            # Only treat running containers as candidates; else failing
            if state == "running":
                # Check health status for containers with health checks
                health_result = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        name,
                        "--format",
                        "{{if .State.Health}}{{.State.Health.Status}}{{end}}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                health_status = (health_result.stdout or "").strip()
                if health_status in ("healthy", ""):
                    healthy_count += 1
                elif health_status == "starting":
                    healthy_count += 1  # grace period
                elif health_status == "unhealthy":
                    unhealthy_services.append(f"{name} (unhealthy)")
                else:
                    # Unknown health — treat as healthy if running
                    healthy_count += 1
            else:
                unhealthy_services.append(f"{name} ({state})")

        failing_count = total_services - healthy_count
        return healthy_count, failing_count, unhealthy_services
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting Docker status: {e}", file=sys.stderr)
        return 0, 0, ["Docker command failed"]
    except Exception as e:
        print(f"Unexpected error getting Docker status: {e}", file=sys.stderr)
        return 0, 0, ["Status check failed"]


def get_alertmanager_alerts() -> Tuple[int, List[str]]:
    """Get active alerts from Alertmanager"""
    try:
        # Lazy import to avoid hard dependency if requests is unavailable
        try:
            import requests  # type: ignore
        except Exception:
            return 0, []
        response = requests.get("http://localhost:9093/api/v1/alerts", timeout=5)
        if response.status_code == 200:
            alerts_data = response.json()
            alerts = alerts_data.get('data', [])
            
            critical_alerts = []
            for alert in alerts:
                if alert.get('state') == 'active':
                    severity = alert.get('labels', {}).get('severity', 'unknown')
                    alertname = alert.get('labels', {}).get('alertname', 'Unknown Alert')
                    
                    if severity.lower() in ['critical', 'high']:
                        critical_alerts.append(f"{alertname} ({severity})")
            
            return len(critical_alerts), critical_alerts
        else:
            return 0, []
            
    except requests.RequestException:
        # Alertmanager might not be running or accessible
        return 0, []
    except Exception as e:
        print(f"Error checking alerts: {e}", file=sys.stderr)
        return 0, []


def determine_overall_health(healthy_services: int, failing_services: int, critical_alerts: int) -> str:
    """Determine overall stack health status"""
    if failing_services == 0 and critical_alerts == 0:
        return "🟢 Healthy"
    elif failing_services <= 2 and critical_alerts == 0:
        return "🟡 Degraded"
    elif failing_services <= 5 and critical_alerts <= 2:
        return "🟠 Impaired"
    else:
        return "🔴 Critical"


def generate_status_table(
    overall_health: str,
    critical_alerts: int,
    failing_services: int,
    timestamp: str,
    alert_details: List[str] = None,
    unhealthy_details: List[str] = None
) -> str:
    """Generate the status table markup"""
    
    # Format alert status
    if critical_alerts == 0:
        alert_status = "✅ None"
    else:
        alert_status = f"🚨 {critical_alerts}"
    
    # Base table
    table = f"""| Key Metric       | Value             |
|------------------|------------------|
| Stack Health     | {overall_health} |
| Critical Alerts  | {alert_status} |
| Failing Services | {failing_services} |
| Last Check       | {timestamp} |"""
    
    # Add details if there are issues
    details = []
    
    if alert_details and critical_alerts > 0:
        details.append("\n**Active Critical Alerts:**")
        for alert in alert_details[:5]:  # Limit to 5 alerts
            details.append(f"- {alert}")
    
    if unhealthy_details and failing_services > 0:
        details.append("\n**Failing Services:**")
        for service in unhealthy_details[:5]:  # Limit to 5 services
            details.append(f"- {service}")
    
    if details:
        table += "\n" + "\n".join(details)
    
    return table


def manage_github_issues(failing_count: int, unhealthy_services: List[str], critical_alerts: List[str]):
    """Manage GitHub issues via scripts/github_api.sh (no secrets printed)."""
    try:
        import subprocess

        repo_owner = "millsmillsymills"
        repo_name = "maelstrom"
        api_base = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        gh_api = "/home/mills/scripts/github_api.sh"

        # Ensure auth is configured; ignore output
        subprocess.run(["/home/mills/scripts/github_auth.sh"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if failing_count > 2 or len(critical_alerts) > 0:
            title = f"🚨 Infrastructure Health Alert - {failing_count} services failing"
            body = {
                "title": title,
                "body": "\n".join([
                    "## Infrastructure Health Alert",
                    f"Failing services: {failing_count}",
                    "",
                    "### Failing Services",
                    *[f"- {s}" for s in unhealthy_services[:10]],
                    "",
                    "### Critical Alerts",
                    *[f"- {a}" for a in critical_alerts[:10]],
                    "",
                    "*Automated alert from Maelstrom*",
                ]),
                "labels": ["infrastructure", "auto-generated", "urgent"],
            }

            data = _json_for_api.dumps(body)
            subprocess.run(
                ["bash", "-lc", f"'{gh_api}' -X POST '{api_base}/issues' --data @-"],
                input=data.encode(),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        elif failing_count == 0 and len(critical_alerts) == 0:
            # List open infra issues
            proc = subprocess.run(
                ["bash", "-lc", f"'{gh_api}' -X GET '{api_base}/issues?state=open&labels=infrastructure,auto-generated'"],
                check=False,
                capture_output=True,
            )
            try:
                issues = _json_for_api.loads(proc.stdout.decode() or "[]")
            except Exception:
                issues = []
            for issue in issues:
                number = issue.get("number")
                if not number:
                    continue
                comment = {"body": "✅ System healthy. Auto-closing by Maelstrom."}
                subprocess.run(
                    ["bash", "-lc", f"'{gh_api}' -X POST '{api_base}/issues/{number}/comments' --data @-"],
                    input=_json_for_api.dumps(comment).encode(),
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.run(
                    ["bash", "-lc", f"'{gh_api}' -X PATCH '{api_base}/issues/{number}' --data @-"],
                    input=_json_for_api.dumps({"state": "closed"}).encode(),
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

    except Exception as e:
        print(f"Warning: GitHub issue management failed: {e}", file=sys.stderr)


def update_readme_status():
    """Main function to update README.md status block"""
    try:
        # Get current status information
        healthy_count, failing_count, unhealthy_services = get_docker_service_status()
        critical_alert_count, critical_alerts = get_alertmanager_alerts()
        
        # Determine overall health
        overall_health = determine_overall_health(healthy_count, failing_count, critical_alert_count)
        
        # Generate timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        # GitHub issue management based on health status
        manage_github_issues(failing_count, unhealthy_services, critical_alerts)
        
        # Generate status table
        status_table = generate_status_table(
            overall_health,
            critical_alert_count,
            failing_count,
            timestamp,
            critical_alerts,
            unhealthy_services
        )
        
        # Read current README.md
        readme_path = "/home/mills/README.md"
        try:
            with open(readme_path, 'r') as f:
                readme_content = f.read()
        except FileNotFoundError:
            print(f"README.md not found at {readme_path}", file=sys.stderr)
            return False
        
        # Find and replace the status section
        status_pattern = r'(<!-- STATUS-BEGIN -->).*?(<!-- STATUS-END -->)'
        replacement = f'<!-- STATUS-BEGIN -->\n{status_table}\n<!-- STATUS-END -->'
        
        if re.search(status_pattern, readme_content, re.DOTALL):
            # Update the status markers section
            updated_content = re.sub(status_pattern, replacement, readme_content, flags=re.DOTALL)
        else:
            print("Status markers not found in README.md", file=sys.stderr)
            return False
        
        # Write updated content back to README.md
        with open(readme_path, 'w') as f:
            f.write(updated_content)
        
        # Print status summary
        print(f"README.md status updated successfully")
        print(f"Overall Health: {overall_health}")
        print(f"Services: {healthy_count} healthy, {failing_count} failing")
        print(f"Critical Alerts: {critical_alert_count}")
        print(f"Timestamp: {timestamp}")
        
        return True
        
    except Exception as e:
        print(f"Error updating README status: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = update_readme_status()
    sys.exit(0 if success else 1)
