#!/usr/bin/env python3
"""
GitHub Issue Management for Maelstrom
Automatically creates and manages GitHub issues for infrastructure problems
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests


class GitHubIssueManager:
    def __init__(self):
        self.github_token = self._get_github_token()
        self.repo_owner = self._get_env_var("GITHUB_USERNAME", "millsmillsymills")
        self.repo_name = "maelstrom"
        self.api_base = "https://api.github.com"
        
    def _get_github_token(self) -> str:
        """Extract GitHub token from .env file"""
        try:
            with open("/home/mills/.env", "r") as f:
                for line in f:
                    if line.startswith("GITHUB_TOKEN="):
                        return line.split("=", 1)[1].strip().strip('"')
            raise ValueError("GITHUB_TOKEN not found in .env")
        except Exception as e:
            print(f"Error reading GitHub token: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _get_env_var(self, var_name: str, default: str) -> str:
        """Get environment variable with fallback"""
        try:
            with open("/home/mills/.env", "r") as f:
                for line in f:
                    if line.startswith(f"{var_name}="):
                        return line.split("=", 1)[1].strip().strip('"')
            return default
        except Exception:
            return default
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> requests.Response:
        """Make authenticated GitHub API request"""
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        url = f"{self.api_base}{endpoint}"
        
        if method.upper() == "GET":
            return requests.get(url, headers=headers)
        elif method.upper() == "POST":
            return requests.post(url, headers=headers, json=data)
        elif method.upper() == "PATCH":
            return requests.patch(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
    
    def get_open_issues(self, labels: List[str] = None) -> List[Dict]:
        """Get open issues with optional label filtering"""
        endpoint = f"/repos/{self.repo_owner}/{self.repo_name}/issues"
        params = {"state": "open"}
        
        if labels:
            params["labels"] = ",".join(labels)
        
        try:
            response = self._make_request("GET", endpoint)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching issues: {response.status_code}", file=sys.stderr)
                return []
        except Exception as e:
            print(f"Error fetching issues: {e}", file=sys.stderr)
            return []
    
    def create_infrastructure_issue(self, title: str, failing_services: List[str], 
                                  critical_alerts: List[str] = None) -> bool:
        """Create a GitHub issue for infrastructure problems"""
        
        # Check if similar issue already exists
        existing_issues = self.get_open_issues(labels=["infrastructure", "auto-generated"])
        for issue in existing_issues:
            if "Infrastructure Health Alert" in issue.get("title", ""):
                print("Similar infrastructure issue already exists, updating instead")
                return self._update_infrastructure_issue(issue["number"], failing_services, critical_alerts)
        
        # Create issue body
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        body_parts = [
            "## 🚨 Infrastructure Health Alert",
            "",
            f"**Detection Time:** {timestamp}",
            f"**Failing Services:** {len(failing_services)}",
            f"**Critical Alerts:** {len(critical_alerts or [])}",
            "",
            "### 📊 Service Status",
            ""
        ]
        
        if failing_services:
            body_parts.extend([
                "**Failing Services:**",
                ""
            ])
            for service in failing_services:
                body_parts.append(f"- ❌ `{service}`")
            body_parts.append("")
        
        if critical_alerts:
            body_parts.extend([
                "**Critical Alerts:**",
                ""
            ])
            for alert in critical_alerts:
                body_parts.append(f"- 🚨 `{alert}`")
            body_parts.append("")
        
        body_parts.extend([
            "### 🔧 Recommended Actions",
            "",
            "1. **Immediate:**",
            "   - [ ] SSH to Maelstrom server: `ssh mills@<server>`", 
            "   - [ ] Check service status: `docker ps`",
            "   - [ ] Review service logs: `docker-compose logs -f <service>`",
            "",
            "2. **Diagnosis:**",
            "   - [ ] Run health validation: `./validate_stack.sh --health-checks-only`",
            "   - [ ] Check resource usage: `docker stats`",
            "   - [ ] Verify network connectivity: `docker network ls`",
            "",
            "3. **Recovery:**",
            "   - [ ] Restart failing services: `docker-compose restart <service>`",
            "   - [ ] If needed, full stack restart: `./deploy_stack.sh`",
            "   - [ ] Validate recovery: `./validate_stack.sh`",
            "",
            "### 📋 Validation Checklist",
            "",
            "- [ ] All services return to healthy status",
            "- [ ] Critical alerts cleared",
            "- [ ] README.md status shows green",
            "- [ ] Monitor for 30 minutes to ensure stability",
            "",
            "---",
            "*This issue was automatically generated by the Maelstrom monitoring system.*",
            f"*Last updated: {timestamp}*"
        ])
        
        body = "\n".join(body_parts)
        
        # Create the issue
        issue_data = {
            "title": title,
            "body": body,
            "labels": ["infrastructure", "auto-generated", "urgent"]
        }
        
        try:
            response = self._make_request("POST", f"/repos/{self.repo_owner}/{self.repo_name}/issues", issue_data)
            if response.status_code == 201:
                issue = response.json()
                print(f"Created GitHub issue #{issue['number']}: {issue['html_url']}")
                return True
            else:
                print(f"Error creating issue: {response.status_code} - {response.text}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"Error creating issue: {e}", file=sys.stderr)
            return False
    
    def _update_infrastructure_issue(self, issue_number: int, failing_services: List[str],
                                   critical_alerts: List[str] = None) -> bool:
        """Update existing infrastructure issue"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        comment_body = f"""## 🔄 Status Update - {timestamp}

**Current Status:**
- Failing Services: {len(failing_services)}
- Critical Alerts: {len(critical_alerts or [])}

**Services Still Failing:**
{chr(10).join(f'- ❌ `{service}`' for service in failing_services)}

**Critical Alerts:**
{chr(10).join(f'- 🚨 `{alert}`' for alert in (critical_alerts or []))}

*Automated update from Maelstrom monitoring system*"""
        
        try:
            response = self._make_request(
                "POST", 
                f"/repos/{self.repo_owner}/{self.repo_name}/issues/{issue_number}/comments",
                {"body": comment_body}
            )
            if response.status_code == 201:
                print(f"Updated GitHub issue #{issue_number}")
                return True
            else:
                print(f"Error updating issue: {response.status_code}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"Error updating issue: {e}", file=sys.stderr)
            return False
    
    def close_infrastructure_issues(self) -> bool:
        """Close infrastructure issues when system is healthy"""
        infrastructure_issues = self.get_open_issues(labels=["infrastructure", "auto-generated"])
        
        success = True
        for issue in infrastructure_issues:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            # Add resolution comment
            comment_body = f"""## ✅ Issue Resolved - {timestamp}

The Maelstrom monitoring system has detected that all services are now healthy and all critical alerts have been cleared.

**Final Status:**
- ✅ All services healthy
- ✅ No critical alerts
- ✅ System monitoring operational

Automatically closing this issue.

*Automated resolution by Maelstrom monitoring system*"""
            
            # Add comment
            comment_response = self._make_request(
                "POST",
                f"/repos/{self.repo_owner}/{self.repo_name}/issues/{issue['number']}/comments",
                {"body": comment_body}
            )
            
            # Close issue
            close_response = self._make_request(
                "PATCH",
                f"/repos/{self.repo_owner}/{self.repo_name}/issues/{issue['number']}",
                {"state": "closed"}
            )
            
            if comment_response.status_code == 201 and close_response.status_code == 200:
                print(f"Closed GitHub issue #{issue['number']}: {issue['title']}")
            else:
                print(f"Error closing issue #{issue['number']}", file=sys.stderr)
                success = False
        
        return success


def main():
    """Main function to handle issue management"""
    if len(sys.argv) < 2:
        print("Usage: github_issue_manager.py <command> [args...]")
        print("Commands:")
        print("  create <title> <failing_services_json>")
        print("  close-healthy")
        print("  list")
        sys.exit(1)
    
    manager = GitHubIssueManager()
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) < 4:
            print("Usage: github_issue_manager.py create <title> <failing_services_json>")
            sys.exit(1)
        
        title = sys.argv[2]
        try:
            failing_services = json.loads(sys.argv[3])
            critical_alerts = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}", file=sys.stderr)
            sys.exit(1)
        
        success = manager.create_infrastructure_issue(title, failing_services, critical_alerts)
        sys.exit(0 if success else 1)
    
    elif command == "close-healthy":
        success = manager.close_infrastructure_issues()
        sys.exit(0 if success else 1)
    
    elif command == "list":
        issues = manager.get_open_issues(labels=["infrastructure"])
        for issue in issues:
            print(f"#{issue['number']}: {issue['title']}")
            print(f"  Created: {issue['created_at']}")
            print(f"  URL: {issue['html_url']}")
            print()
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()