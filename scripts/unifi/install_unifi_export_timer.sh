#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--user] [--system] [--enable] [--disable] [--with-rotate] [--with-pipeline] [--with-metrics-link] [--with-status]

Installs systemd unit+timer templates for UniFi exports.
Defaults to user services. Does not enable unless --enable is given.

Examples:
  # Install for current user and enable
  scripts/unifi/install_unifi_export_timer.sh --user --enable --with-rotate --with-pipeline --with-metrics-link --with-status

  # Disable and remove
  scripts/unifi/install_unifi_export_timer.sh --user --disable
USAGE
}

MODE="user"
ACTION="install"
ENABLE=false
DISABLE=false
WITH_ROTATE=false
WITH_PIPELINE=false
WITH_METRICS_LINK=false
WITH_STATUS=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) MODE="user"; shift ;;
    --system) MODE="system"; shift ;;
    --enable) ENABLE=true; shift ;;
    --disable) DISABLE=true; shift ;;
    --with-rotate) WITH_ROTATE=true; shift ;;
    --with-pipeline) WITH_PIPELINE=true; shift ;;
    --with-metrics-link) WITH_METRICS_LINK=true; shift ;;
    --with-status) WITH_STATUS=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
SERV_NAME="unifi-export"
if [[ "$MODE" == "user" ]]; then
  DEST_DIR="$HOME/.config/systemd/user"
  mkdir -p "$DEST_DIR"
  cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME.service" "$DEST_DIR/"
  cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME.timer" "$DEST_DIR/"
  if [[ "$WITH_ROTATE" == true ]]; then
    cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME-rotate.service" "$DEST_DIR/"
    cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME-rotate.timer" "$DEST_DIR/"
  fi
  if [[ "$WITH_PIPELINE" == true ]]; then
    cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME-pipeline.service" "$DEST_DIR/"
    cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME-pipeline.timer" "$DEST_DIR/"
  fi
  if [[ "$WITH_METRICS_LINK" == true ]]; then
    cp -f "$REPO/scripts/unifi/systemd/unifi-metrics-link.service" "$DEST_DIR/"
    cp -f "$REPO/scripts/unifi/systemd/unifi-metrics-link.timer" "$DEST_DIR/"
  fi
  if [[ "$WITH_STATUS" == true ]]; then
    cp -f "$REPO/scripts/unifi/systemd/unifi-export-status.service" "$DEST_DIR/"
    cp -f "$REPO/scripts/unifi/systemd/unifi-export-status.timer" "$DEST_DIR/"
  fi
  systemctl --user daemon-reload
  if [[ "$DISABLE" == true ]]; then
    systemctl --user disable --now "$SERV_NAME.timer" || true
    if [[ "$WITH_ROTATE" == true ]]; then
      systemctl --user disable --now "$SERV_NAME-rotate.timer" || true
    fi
    if [[ "$WITH_PIPELINE" == true ]]; then
      systemctl --user disable --now "$SERV_NAME-pipeline.timer" || true
    fi
    if [[ "$WITH_METRICS_LINK" == true ]]; then
      systemctl --user disable --now "unifi-metrics-link.timer" || true
    fi
    if [[ "$WITH_STATUS" == true ]]; then
      systemctl --user disable --now "unifi-export-status.timer" || true
    fi
    echo "User timer disabled: $SERV_NAME.timer"
    exit 0
  fi
  if [[ "$ENABLE" == true ]]; then
    systemctl --user enable --now "$SERV_NAME.timer"
    if [[ "$WITH_ROTATE" == true ]]; then
      systemctl --user enable --now "$SERV_NAME-rotate.timer"
    fi
    if [[ "$WITH_PIPELINE" == true ]]; then
      systemctl --user enable --now "$SERV_NAME-pipeline.timer"
    fi
    if [[ "$WITH_METRICS_LINK" == true ]]; then
      systemctl --user enable --now "unifi-metrics-link.timer"
    fi
    if [[ "$WITH_STATUS" == true ]]; then
      systemctl --user enable --now "unifi-export-status.timer"
    fi
    echo "User timer enabled: $SERV_NAME.timer"
  else
    echo "Installed user units. To enable: systemctl --user enable --now $SERV_NAME.timer"
  fi
else
  DEST_DIR="/etc/systemd/system"
  sudo cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME.service" "$DEST_DIR/"
  sudo cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME.timer" "$DEST_DIR/"
  if [[ "$WITH_ROTATE" == true ]]; then
    sudo cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME-rotate.service" "$DEST_DIR/"
    sudo cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME-rotate.timer" "$DEST_DIR/"
  fi
  if [[ "$WITH_PIPELINE" == true ]]; then
    sudo cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME-pipeline.service" "$DEST_DIR/"
    sudo cp -f "$REPO/scripts/unifi/systemd/$SERV_NAME-pipeline.timer" "$DEST_DIR/"
  fi
  if [[ "$WITH_METRICS_LINK" == true ]]; then
    sudo cp -f "$REPO/scripts/unifi/systemd/unifi-metrics-link.service" "$DEST_DIR/"
    sudo cp -f "$REPO/scripts/unifi/systemd/unifi-metrics-link.timer" "$DEST_DIR/"
  fi
  if [[ "$WITH_STATUS" == true ]]; then
    sudo cp -f "$REPO/scripts/unifi/systemd/unifi-export-status.service" "$DEST_DIR/"
    sudo cp -f "$REPO/scripts/unifi/systemd/unifi-export-status.timer" "$DEST_DIR/"
  fi
  sudo systemctl daemon-reload
  if [[ "$DISABLE" == true ]]; then
    sudo systemctl disable --now "$SERV_NAME.timer" || true
    if [[ "$WITH_ROTATE" == true ]]; then
      sudo systemctl disable --now "$SERV_NAME-rotate.timer" || true
    fi
    if [[ "$WITH_PIPELINE" == true ]]; then
      sudo systemctl disable --now "$SERV_NAME-pipeline.timer" || true
    fi
    if [[ "$WITH_METRICS_LINK" == true ]]; then
      sudo systemctl disable --now "unifi-metrics-link.timer" || true
    fi
    if [[ "$WITH_STATUS" == true ]]; then
      sudo systemctl disable --now "unifi-export-status.timer" || true
    fi
    echo "System timer disabled: $SERV_NAME.timer"
    exit 0
  fi
  if [[ "$ENABLE" == true ]]; then
    sudo systemctl enable --now "$SERV_NAME.timer"
    if [[ "$WITH_ROTATE" == true ]]; then
      sudo systemctl enable --now "$SERV_NAME-rotate.timer"
    fi
    if [[ "$WITH_PIPELINE" == true ]]; then
      sudo systemctl enable --now "$SERV_NAME-pipeline.timer"
    fi
    if [[ "$WITH_METRICS_LINK" == true ]]; then
      sudo systemctl enable --now "unifi-metrics-link.timer"
    fi
    if [[ "$WITH_STATUS" == true ]]; then
      sudo systemctl enable --now "unifi-export-status.timer"
    fi
    echo "System timer enabled: $SERV_NAME.timer"
  else
    echo "Installed system units. To enable: sudo systemctl enable --now $SERV_NAME.timer"
  fi
fi
