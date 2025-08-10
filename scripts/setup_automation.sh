#!/bin/bash
# Setup complete automation for Maelstrom GitHub integration
# Creates cron jobs for autonomous operation

set -euo pipefail
source /usr/local/lib/codex_env.sh 2>/dev/null || true

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

PROJECT_ROOT="/home/mills"

log "Setting up complete Maelstrom automation..."

# Ensure we're in the right directory
cd "$PROJECT_ROOT" || exit 1

# Create cron jobs
CRON_JOBS=(
    # README status updates every 15 minutes
    "*/15 * * * * cd $PROJECT_ROOT && python3 scripts/update_readme_status.py >/dev/null 2>&1"
    
    # Daily configuration backup at 2 AM
    "0 2 * * * cd $PROJECT_ROOT && ./scripts/git_backup.sh 'Automated daily backup' >/dev/null 2>&1"
    
    # Weekly comprehensive validation and backup on Sundays at 3 AM  
    "0 3 * * 0 cd $PROJECT_ROOT && ./validate_stack.sh --quick && ./scripts/git_backup.sh 'Weekly validation backup' >/dev/null 2>&1"
    
    # Monthly security scan and backup on 1st of month at 4 AM
    "0 4 1 * * cd $PROJECT_ROOT && ./scripts/scan_images.sh && ./scripts/git_backup.sh 'Monthly security scan backup' >/dev/null 2>&1"
    
    # Health check and issue management every 30 minutes
    "*/30 * * * * cd $PROJECT_ROOT && python3 scripts/update_readme_status.py >/dev/null 2>&1"
    
    # Log rotation weekly on Saturdays at 1 AM
    "0 1 * * 6 find $PROJECT_ROOT/logs -name '*.log' -mtime +7 -delete >/dev/null 2>&1"
)

# Backup existing crontab
log "Backing up existing crontab..."
if crontab -l >/dev/null 2>&1; then
    crontab -l > "$PROJECT_ROOT/crontab.backup.$(date +%Y%m%d_%H%M%S)"
    success "Existing crontab backed up"
fi

# Create new crontab
log "Installing automation cron jobs..."
{
    # Preserve existing cron jobs (if any) that aren't Maelstrom related
    crontab -l 2>/dev/null | grep -v "$PROJECT_ROOT" || true
    
    # Add header comment
    echo "# Maelstrom Monitoring Stack Automation - Installed $(date)"
    
    # Add new jobs
    for job in "${CRON_JOBS[@]}"; do
        echo "$job"
    done
    
} | crontab -

success "Cron jobs installed successfully"

# Display installed jobs
log "Installed automation jobs:"
echo ""
echo "📅 SCHEDULED AUTOMATION:"
echo "  • README status updates: Every 15 minutes"
echo "  • Configuration backup: Daily at 2:00 AM"
echo "  • Comprehensive validation: Weekly on Sundays at 3:00 AM"
echo "  • Security scanning: Monthly on 1st at 4:00 AM"
echo "  • Health monitoring: Every 30 minutes"
echo "  • Log cleanup: Weekly on Saturdays at 1:00 AM"
echo ""

# Create systemd service for monitoring dashboard (optional)
log "Creating systemd service for monitoring dashboard..."

SERVICE_CONTENT=$(cat <<EOF
[Unit]
Description=Maelstrom Monitoring Dashboard
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=mills
WorkingDirectory=$PROJECT_ROOT
ExecStart=$PROJECT_ROOT/scripts/monitoring_dashboard.sh
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
)

if write_root "/etc/systemd/system/maelstrom-dashboard.service" "$SERVICE_CONTENT" 2>/dev/null; then
    sysctl_wrap daemon-reload || true
    success "Systemd service created (enable with: ${SUDO:+${SUDO} }systemctl enable maelstrom-dashboard)"
else
    warning "Could not create systemd service (no non-interactive ${SUDO} access)"
fi

# Verify cron service is running
if sysctl_wrap is-active --quiet cron 2>/dev/null || sysctl_wrap is-active --quiet crond 2>/dev/null; then
    success "Cron service is running"
else
    warning "Cron service may not be running - please check system configuration"
fi

# Test automation components
log "Testing automation components..."

# Test README status update
if python3 scripts/update_readme_status.py; then
    success "README status update: Working"
else
    warning "README status update: Failed"
fi

# Test Git backup (dry run)
if ./scripts/git_backup.sh --dry-run --skip-health >/dev/null 2>&1; then
    success "Git backup system: Working"
else
    warning "Git backup system: May need GitHub repository setup"
fi

# Test validation
if ./validate_stack.sh --health-checks-only --quick >/dev/null 2>&1; then
    success "Stack validation: Working"
else
    warning "Stack validation: Some issues detected"
fi

echo ""
success "Maelstrom automation setup completed!"
echo ""
echo "🎯 NEXT STEPS:"
echo "  1. Create GitHub repository: https://github.com/new"
echo "  2. Push initial commit: git push -u origin main"
echo "  3. Configure GitHub Actions secrets (SSH keys, etc.)"
echo "  4. Monitor automation: tail -f logs/git_backup_error.log"
echo "  5. Start monitoring dashboard: ./scripts/monitoring_dashboard.sh"
echo ""
echo "🔧 MANAGEMENT COMMANDS:"
echo "  • View cron jobs: crontab -l"
echo "  • Edit automation: crontab -e" 
echo "  • Manual backup: ./scripts/git_backup.sh 'Manual backup'"
echo "  • Check GitHub issues: python3 scripts/github_issue_manager.py list"
echo "  • Start dashboard: ./scripts/monitoring_dashboard.sh"
echo ""

log "Automation setup complete. The system will now operate autonomously!"