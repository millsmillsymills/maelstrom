#!/bin/bash
# Health check script for network analysis services (Suricata, Zeek, ntopng)
# Returns 0 if packet capture is active, 1 otherwise

set -euo pipefail

SERVICE_NAME="${1:-unknown}"

case "$SERVICE_NAME" in
    "suricata")
        # Check if Suricata is capturing packets by looking for active threads
        if pgrep -f "Suricata-Main" > /dev/null 2>&1; then
            # Check if log files are being written (recent activity)
            if find /var/log/suricata -name "*.json" -mmin -5 2>/dev/null | grep -q .; then
                exit 0
            fi
        fi
        exit 1
        ;;
    "zeek")
        # Check if Zeek process is running and capturing
        if pgrep -f "zeek.*-i" > /dev/null 2>&1; then
            # Check if logs are being written
            if find /usr/local/zeek/logs/current -name "*.log" -mmin -5 2>/dev/null | grep -q .; then
                exit 0
            fi
        fi
        exit 1
        ;;
    "ntopng")
        # Check if ntopng is running and interface is active
        if pgrep -f "ntopng" > /dev/null 2>&1; then
            # Check if the web interface responds
            if curl -sf http://localhost:3000/lua/rest/v1/get/ntopng/status.lua > /dev/null 2>&1; then
                exit 0
            fi
        fi
        exit 1
        ;;
    *)
        echo "Unknown service: $SERVICE_NAME"
        exit 1
        ;;
esac