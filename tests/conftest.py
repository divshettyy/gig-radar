"""Shared test setup. Nothing here may reach the network, the mail server, the
SMS provider or the real database.

config.py loads the user's real .env on import, so every secret is blanked for
each test and the outbound calls are replaced with ones that fail loudly. A test
that wants an outbound call replaces these again with its own fake.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import store  # noqa: E402

SECRETS = ["SMTP_USER", "SMTP_APP_PASSWORD", "NOTIFY_EMAIL_TO", "TWILIO_SID",
           "TWILIO_AUTH_TOKEN", "TWILIO_FROM", "TWILIO_TO", "REDDIT_CLIENT_ID",
           "REDDIT_CLIENT_SECRET", "FREELANCER_OAUTH_TOKEN", "UPWORK_ACCESS_TOKEN"]


def _blocked(*a, **k):
    raise AssertionError("a test tried a real outbound call")


@pytest.fixture(autouse=True)
def sealed(monkeypatch, tmp_path):
    import smtplib
    import requests
    for name in SECRETS:
        monkeypatch.setattr(config, name, "")
    monkeypatch.setattr(smtplib, "SMTP_SSL", _blocked)
    monkeypatch.setattr(requests, "get", _blocked)
    monkeypatch.setattr(requests, "post", _blocked)
    monkeypatch.setattr(store, "DB", str(tmp_path / "test.db"))
    store.init()


class Reply:
    """Stand-in for a requests response."""

    def __init__(self, payload=None, text="", status=200):
        self.payload, self.text, self.status_code = payload, text, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %d" % self.status_code)


@pytest.fixture
def web(monkeypatch):
    """Serve canned replies by URL fragment; records every call made."""
    import requests
    routes, calls = [], []

    def serve(kind):
        def handler(url, **kw):
            calls.append((kind, url, kw))
            for frag, reply in routes:
                if frag in url:
                    return reply
            raise AssertionError("no canned reply for " + url)
        return handler

    monkeypatch.setattr(requests, "get", serve("GET"))
    monkeypatch.setattr(requests, "post", serve("POST"))

    def add(frag, payload=None, text="", status=200):
        routes.append((frag, Reply(payload, text, status)))

    add.calls = calls
    return add


def job(i, **over):
    j = {"id": "t%s" % i, "title": "Python developer %s" % i, "company": "Acme",
         "url": "https://example.com/%s" % i, "date": 1000 * i, "tags": [],
         "salary": None, "loc": "Remote", "desc": "", "src": "RemoteOK"}
    j.update(over)
    return j
