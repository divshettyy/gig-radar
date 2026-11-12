"""Serves the local dashboard and runs the poll loop in a background thread.
Run:  python server.py   ->  http://localhost:<PORT>
"""
import os
import threading
import time

from flask import Flask, jsonify, send_from_directory

import config
import store
from poller import poll_cycle, STATUS

app = Flask(__name__)
HERE = os.path.dirname(__file__)

@app.route("/")
def index():
    return send_from_directory(HERE, "dashboard.html")

@app.route("/api/jobs")
def api_jobs():
    return jsonify(store.recent(400))

@app.route("/api/sources")
def api_sources():
    return jsonify({
        "status": STATUS,
        "email": config.email_enabled(),
        "sms": config.sms_enabled(),
        "interval": config.POLL_INTERVAL,
    })

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    fresh = poll_cycle(force=True)
    return jsonify({"new": len(fresh)})

def loop():
    while True:
        try:
            poll_cycle(force=False)
        except Exception as e:
            print("[loop] error:", e)
        time.sleep(max(300, config.POLL_INTERVAL))

if __name__ == "__main__":
    store.init()
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("Gig Radar running at http://localhost:%d  (email=%s sms=%s)" % (
        config.PORT, config.email_enabled(), config.sms_enabled()))
    app.run(host="127.0.0.1", port=config.PORT, debug=False, use_reloader=False)
