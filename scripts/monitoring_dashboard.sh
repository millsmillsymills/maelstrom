#!/bin/bash
# Advanced Monitoring Dashboard for Maelstrom
# Real-time infrastructure monitoring with GitHub integration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configuration
REFRESH_INTERVAL=30
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="/home/mills"

# Clear screen function
clear_screen() {
    clear
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                    🌊 MAELSTROM MONITORING DASHBOARD                   ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Get service status with health checks
get_service_status() {
    echo -e "${BLUE}📊 SERVICE STATUS${NC}"
    echo "────────────────────────────────────────────────────────────────────────"
    
    local healthy=0
    local unhealthy=0
    local starting=0
    
    # Get container status
    while IFS= read -r line; do
        if [[ -z "$line" ]]; then
            continue
        fi
        
        local name status state health
        name=$(echo "$line" | cut -d: -f1)
        status=$(echo "$line" | cut -d: -f2)
        state=$(echo "$line" | cut -d: -f3)
        
        # Get health status
        health=$(docker inspect "$name" --format '{{.State.Health.Status}}' 2>/dev/null || echo "none")
        
        # Determine display status
        local display_status color
        if [[ "$state" == "running" ]]; then
            case "$health" in
                "healthy")
                    display_status="🟢 HEALTHY"
                    color="$GREEN"
                    ((healthy++))
                    ;;
                "unhealthy")
                    display_status="🔴 UNHEALTHY"
                    color="$RED"
                    ((unhealthy++))
                    ;;
                "starting")
                    display_status="🟡 STARTING"
                    color="$YELLOW"
                    ((starting++))
                    ;;
                *)
                    display_status="🟢 RUNNING"
                    color="$GREEN"
                    ((healthy++))
                    ;;
            esac
        else
            display_status="🔴 $state"
            color="$RED"
            ((unhealthy++))
        fi
        
        printf "${color}%-25s${NC} %s\n" "$name" "$display_status"
        
    done < <(docker ps --format "{{.Names}}:{{.Status}}:{{.State}}" 2>/dev/null || true)
    
    echo ""
    echo -e "${GREEN}✅ Healthy: $healthy${NC}  ${YELLOW}🟡 Starting: $starting${NC}  ${RED}❌ Unhealthy: $unhealthy${NC}"
    echo ""
}

# Get resource usage
get_resource_usage() {
    echo -e "${BLUE}💾 RESOURCE USAGE${NC}"
    echo "────────────────────────────────────────────────────────────────────────"
    
    # System resources
    local cpu_usage mem_usage disk_usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    mem_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    echo -e "${PURPLE}System Resources:${NC}"
    printf "  CPU: %s%%  Memory: %s%%  Disk: %s%%\n" "$cpu_usage" "$mem_usage" "$disk_usage"
    echo ""
    
    # Docker stats (top 10 by memory)
    echo -e "${PURPLE}Top Containers by Memory:${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null | \
        head -11 | tail -10 | while read -r line; do
        echo "  $line"
    done
    echo ""
}

# Get alert status
get_alert_status() {
    echo -e "${BLUE}🚨 ALERT STATUS${NC}"
    echo "────────────────────────────────────────────────────────────────────────"
    
    # Check Prometheus alerts
    local prom_alerts
    if prom_alerts=$(curl -s http://localhost:9090/api/v1/alerts 2>/dev/null); then
        local active_count
        active_count=$(echo "$prom_alerts" | jq -r '.data[] | select(.state=="firing") | .labels.alertname' 2>/dev/null | wc -l || echo "0")
        
        if [[ $active_count -gt 0 ]]; then
            echo -e "${RED}🚨 $active_count active Prometheus alerts${NC}"
            echo "$prom_alerts" | jq -r '.data[] | select(.state=="firing") | "  - \(.labels.alertname): \(.labels.severity // "unknown")"' 2>/dev/null || true
        else
            echo -e "${GREEN}✅ No active Prometheus alerts${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Prometheus not accessible${NC}"
    fi
    
    # Check Alertmanager
    local am_alerts
    if am_alerts=$(curl -s http://localhost:9093/api/v1/alerts 2>/dev/null); then
        local am_active_count
        am_active_count=$(echo "$am_alerts" | jq -r '.data[] | select(.status.state=="active") | .labels.alertname' 2>/dev/null | wc -l || echo "0")
        
        if [[ $am_active_count -gt 0 ]]; then
            echo -e "${RED}🚨 $am_active_count active Alertmanager alerts${NC}"
        else
            echo -e "${GREEN}✅ No active Alertmanager alerts${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Alertmanager not accessible${NC}"
    fi
    
    echo ""
}

# Get GitHub integration status
get_github_status() {
    echo -e "${BLUE}🔗 GITHUB INTEGRATION${NC}"
    echo "────────────────────────────────────────────────────────────────────────"
    
    # Check Git status
    cd "$PROJECT_ROOT" || return 1
    
    local git_status branch
    if git_status=$(git status --porcelain 2>/dev/null); then
        branch=$(git branch --show-current 2>/dev/null || echo "unknown")
        echo -e "${GREEN}📋 Git Status: Connected (branch: $branch)${NC}"
        
        if [[ -n "$git_status" ]]; then
            local changes
            changes=$(echo "$git_status" | wc -l)
            echo -e "${YELLOW}📝 Uncommitted changes: $changes files${NC}"
        else
            echo -e "${GREEN}✅ Working directory clean${NC}"
        fi
        
        # Last commit info
        local last_commit
        last_commit=$(git log -1 --pretty=format:"%h %s (%cr)" 2>/dev/null || echo "No commits")
        echo -e "${CYAN}📅 Last commit: $last_commit${NC}"
    else
        echo -e "${RED}❌ Git repository not accessible${NC}"
    fi
    
    # Check GitHub connectivity
    if python3 scripts/github_issue_manager.py list >/dev/null 2>&1; then
        echo -e "${GREEN}🌐 GitHub API: Connected${NC}"
    else
        echo -e "${RED}❌ GitHub API: Connection failed${NC}"
    fi
    
    # Recent backup status
    if [[ -f "logs/git_backup_error.log" ]]; then
        local last_backup
        last_backup=$(tail -1 logs/git_backup_error.log 2>/dev/null | cut -d']' -f1 | tr -d '[' || echo "Never")
        echo -e "${CYAN}💾 Last backup attempt: $last_backup${NC}"
    else
        echo -e "${YELLOW}💾 No backup log found${NC}"
    fi
    
    echo ""
}

# Get service endpoints status
get_endpoints_status() {
    echo -e "${BLUE}🌐 SERVICE ENDPOINTS${NC}"
    echo "────────────────────────────────────────────────────────────────────────"
    
    local endpoints=(
        "Grafana:http://localhost:3000/api/health"
        "Prometheus:http://localhost:9090/-/ready"
        "Alertmanager:http://localhost:9093/-/ready"
        "InfluxDB:http://localhost:8086/ping"
        "Loki:http://localhost:3100/ready"
    )
    
    for endpoint in "${endpoints[@]}"; do
        local name url
        name=$(echo "$endpoint" | cut -d: -f1)
        url=$(echo "$endpoint" | cut -d: -f2-)
        
        if curl -f -s --max-time 5 "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $name${NC} - Accessible"
        else
            echo -e "${RED}❌ $name${NC} - Not responding"
        fi
    done
    
    echo ""
}

# Get recent logs summary
get_logs_summary() {
    echo -e "${BLUE}📋 RECENT ACTIVITY${NC}"
    echo "────────────────────────────────────────────────────────────────────────"
    
    # Validation log
    local validation_log
    validation_log=$(ls -t /tmp/stack_validation_*.log 2>/dev/null | head -1 || echo "")
    if [[ -n "$validation_log" ]]; then
        local validation_time
        validation_time=$(stat -c %y "$validation_log" 2>/dev/null | cut -d. -f1 || echo "Unknown")
        echo -e "${CYAN}🔍 Last validation: $validation_time${NC}"
        
        if tail -5 "$validation_log" 2>/dev/null | grep -q "SUCCESS"; then
            echo -e "${GREEN}   ✅ Validation passed${NC}"
        else
            echo -e "${RED}   ❌ Validation issues detected${NC}"
        fi
    else
        echo -e "${YELLOW}🔍 No recent validation logs${NC}"
    fi
    
    # Docker events (last 10)
    echo -e "${CYAN}🐳 Recent Docker events:${NC}"
    docker events --since="5m" --format "{{.Time}} {{.Action}} {{.Actor.Attributes.name}}" 2>/dev/null | tail -5 | \
        while read -r line; do
            echo "   $line"
        done || echo "   No recent events"
    
    echo ""
}

# Interactive menu
show_menu() {
    echo -e "${PURPLE}ACTIONS:${NC}"
    echo "────────────────────────────────────────────────────────────────────────"
    echo "  [v] Run validation      [b] Backup config       [d] Deploy stack"
    echo "  [r] Restart service     [l] View logs           [g] Git status"  
    echo "  [i] GitHub issues       [s] Security scan       [h] Help"
    echo "  [q] Quit               [ENTER] Refresh"
    echo ""
}

# Handle user input
handle_input() {
    local choice
    read -t 1 -n 1 choice || return 0
    
    case "$choice" in
        "v"|"V")
            echo -e "\n${BLUE}Running validation...${NC}"
            ./validate_stack.sh --health-checks-only
            read -p "Press Enter to continue..."
            ;;
        "b"|"B")
            echo -e "\n${BLUE}Backing up configuration...${NC}"
            ./scripts/git_backup.sh "Manual backup from dashboard"
            read -p "Press Enter to continue..."
            ;;
        "d"|"D")
            echo -e "\n${BLUE}Available deployment options:${NC}"
            echo "1) Base stack only"
            echo "2) With ML analytics" 
            echo "3) With security stack"
            echo "4) All profiles"
            read -p "Choose option (1-4): " deploy_choice
            case "$deploy_choice" in
                1) ./deploy_stack.sh --base-only ;;
                2) ./deploy_stack.sh ml-analytics ;;
                3) ./deploy_stack.sh security-stack ;;
                4) ./deploy_stack.sh --all-profiles ;;
                *) echo "Invalid choice" ;;
            esac
            read -p "Press Enter to continue..."
            ;;
        "r"|"R")
            read -p "Enter service name to restart: " service_name
            if [[ -n "$service_name" ]]; then
                docker-compose restart "$service_name"
                echo "Restarted $service_name"
            fi
            read -p "Press Enter to continue..."
            ;;
        "l"|"L")
            read -p "Enter service name for logs: " service_name
            if [[ -n "$service_name" ]]; then
                docker-compose logs --tail=50 -f "$service_name"
            fi
            ;;
        "g"|"G")
            git status
            read -p "Press Enter to continue..."
            ;;
        "i"|"I")
            python3 scripts/github_issue_manager.py list
            read -p "Press Enter to continue..."
            ;;
        "s"|"S")
            echo -e "\n${BLUE}Running security scan...${NC}"
            ./scripts/scan_images.sh --severity HIGH,CRITICAL
            read -p "Press Enter to continue..."
            ;;
        "h"|"H")
            echo -e "\n${BLUE}Maelstrom Monitoring Dashboard Help${NC}"
            echo "This dashboard provides real-time monitoring of your infrastructure."
            echo "Commands refresh automatically every $REFRESH_INTERVAL seconds."
            echo "Use the action keys for interactive operations."
            read -p "Press Enter to continue..."
            ;;
        "q"|"Q")
            echo -e "\n${GREEN}Goodbye!${NC}"
            exit 0
            ;;
    esac
}

# Main dashboard loop
main() {
    echo -e "${GREEN}Starting Maelstrom Monitoring Dashboard...${NC}"
    sleep 2
    
    while true; do
        clear_screen
        
        # Update README status silently
        python3 scripts/update_readme_status.py >/dev/null 2>&1 || true
        
        # Display all sections
        get_service_status
        get_resource_usage
        get_alert_status
        get_github_status
        get_endpoints_status
        get_logs_summary
        show_menu
        
        echo -e "${CYAN}Last updated: $(date)${NC} | Auto-refresh in ${REFRESH_INTERVAL}s"
        
        # Handle input with timeout
        handle_input
    done
}

# Cleanup on exit
trap 'echo -e "\n${GREEN}Dashboard stopped${NC}"; exit 0' INT TERM

# Start dashboard
main