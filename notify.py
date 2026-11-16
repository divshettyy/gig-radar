"""Email + SMS alerts for new gigs. Safe no-ops if unconfigured."""
import smtplib
from email.mime.text import MIMEText
import requests

import config

def _digest(jobs, limit=15):
    lines = []
    for j in jobs[:limit]:
        bits = [str(j.get("title") or "")]
        if j.get("company"):
            bits.append(j["company"])
        bits.append(j.get("src", ""))
        lines.append(" | ".join(b for b in bits if b) + "\n" + (j.get("url") or ""))
    extra = len(jobs) - limit
    if extra > 0:
        lines.append("...and %d more in the dashboard." % extra)
    return "\n\n".join(lines)

def send_email(jobs):
    if not config.email_enabled() or not jobs:
        return False
    body = "%d new gig(s) on Gig Radar:\n\n%s" % (len(jobs), _digest(jobs))
    msg = MIMEText(body)
    msg["Subject"] = "[Gig Radar] %d new gig%s" % (len(jobs), "s" if len(jobs) != 1 else "")
    msg["From"] = config.SMTP_USER
    msg["To"] = config.NOTIFY_EMAIL_TO
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
            s.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
            s.sendmail(config.SMTP_USER, [config.NOTIFY_EMAIL_TO], msg.as_string())
        return True
    except Exception as e:
        print("[notify] email failed:", e)
        return False

def send_sms(jobs):
    if not config.sms_enabled() or not jobs:
        return False
    top = jobs[0]
    body = "Gig Radar: %d new gig(s). Top: %s%s" % (
        len(jobs), str(top.get("title") or "")[:80],
        (" @ " + top["company"]) if top.get("company") else "")
    try:
        r = requests.post(
            "https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json" % config.TWILIO_SID,
            auth=(config.TWILIO_SID, config.TWILIO_AUTH_TOKEN),
            data={"From": config.TWILIO_FROM, "To": config.TWILIO_TO, "Body": body[:300]},
            timeout=20)
        r.raise_for_status()
        return True
    except Exception as e:
        print("[notify] sms failed:", e)
        return False

def alert(jobs):
    if not jobs:
        return
    send_email(jobs)
    send_sms(jobs)
