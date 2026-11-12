"""Load configuration from .env (if present) and the environment."""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

def _get(k, d=""):
    return (os.environ.get(k) or d).strip()

POLL_INTERVAL = int(_get("POLL_INTERVAL", "1200") or 1200)
PORT = int(_get("PORT", "8787") or 8787)

# Generic client identity. We never put the user's personal email/name in
# outbound User-Agent headers (privacy); job boards only need a stable UA.
USER_AGENT = "gig-radar/1.0 (personal job aggregator)"

SMTP_USER = _get("SMTP_USER")
SMTP_APP_PASSWORD = _get("SMTP_APP_PASSWORD")
NOTIFY_EMAIL_TO = _get("NOTIFY_EMAIL_TO") or SMTP_USER

TWILIO_SID = _get("TWILIO_SID")
TWILIO_AUTH_TOKEN = _get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = _get("TWILIO_FROM")
TWILIO_TO = _get("TWILIO_TO")

REDDIT_CLIENT_ID = _get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = _get("REDDIT_CLIENT_SECRET")
FREELANCER_OAUTH_TOKEN = _get("FREELANCER_OAUTH_TOKEN")
UPWORK_ACCESS_TOKEN = _get("UPWORK_ACCESS_TOKEN")

def email_enabled():
    return bool(SMTP_USER and SMTP_APP_PASSWORD and NOTIFY_EMAIL_TO)

def sms_enabled():
    return bool(TWILIO_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM and TWILIO_TO)
