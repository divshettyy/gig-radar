#!/usr/bin/env bash
# Installs Gig Radar as a systemd service that starts on WSL boot and
# auto-restarts on crash. Run once:  sudo bash install-service.sh
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/gig-radar.service"
cp "$SRC" /etc/systemd/system/gig-radar.service
systemctl daemon-reload
systemctl enable --now gig-radar
echo "Installed. Status:"
systemctl --no-pager --full status gig-radar | head -12
