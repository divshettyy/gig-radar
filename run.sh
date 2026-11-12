#!/usr/bin/env bash
# Start Gig Radar: sets up the venv on first run, then serves the dashboard.
set -e
cd "$(dirname "$0")"
if [ ! -d venv ]; then
  python3 -m venv venv
  ./venv/bin/pip install -q -r requirements.txt
fi
exec ./venv/bin/python server.py
