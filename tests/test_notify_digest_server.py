"""Alert text and switches, the Markdown digest, and the local API. Mail and SMS are fakes."""
import pytest

import config
import digest
import notify
from conftest import Reply, job


class FakeSMTP:
    sent = []
    fail_login = False

    def __init__(self, host, port, timeout=None):
        self.where = (host, port)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, password):
        if FakeSMTP.fail_login:
            raise RuntimeError("535 bad credentials")
        self.creds = (user, password)

    def sendmail(self, frm, to, text):
        FakeSMTP.sent.append({"where": self.where, "creds": self.creds, "from": frm,
                              "to": to, "text": text})


@pytest.fixture
def mail(monkeypatch):
    import smtplib
    FakeSMTP.sent, FakeSMTP.fail_login = [], False
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(config, "SMTP_USER", "me@example.com")
    monkeypatch.setattr(config, "SMTP_APP_PASSWORD", "app-pass")
    monkeypatch.setattr(config, "NOTIFY_EMAIL_TO", "to@example.com")
    return FakeSMTP


@pytest.fixture
def sms(monkeypatch):
    import requests
    posts = []
    state = {"status": 200}

    def post(url, **kw):
        posts.append((url, kw))
        return Reply({}, status=state["status"])

    monkeypatch.setattr(requests, "post", post)
    for k, v in [("TWILIO_SID", "ACxyz"), ("TWILIO_AUTH_TOKEN", "tw-token"),
                 ("TWILIO_FROM", "+15550001"), ("TWILIO_TO", "+15550002")]:
        monkeypatch.setattr(config, k, v)
    posts_state = (posts, state)
    return posts_state


def test_nothing_is_sent_when_unconfigured():
    # conftest blanks every secret and makes any outbound call an error
    assert config.email_enabled() is False and config.sms_enabled() is False
    assert notify.send_email([job(1)]) is False and notify.send_sms([job(1)]) is False
    assert notify.alert([job(1)]) is None


@pytest.mark.parametrize("missing", ["SMTP_USER", "SMTP_APP_PASSWORD", "NOTIFY_EMAIL_TO"])
def test_email_needs_every_setting(mail, monkeypatch, missing):
    monkeypatch.setattr(config, missing, "")
    assert notify.send_email([job(1)]) is False and mail.sent == []


@pytest.mark.parametrize("missing", ["TWILIO_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM", "TWILIO_TO"])
def test_sms_needs_every_setting(sms, monkeypatch, missing):
    monkeypatch.setattr(config, missing, "")
    assert notify.send_sms([job(1)]) is False and sms[0] == []


def test_no_jobs_sends_nothing(mail, sms):
    assert notify.send_email([]) is False and notify.send_sms([]) is False
    notify.alert([])
    assert mail.sent == [] and sms[0] == []


def test_email_content_and_route(mail):
    assert notify.send_email([job(1), job(2, company="")]) is True
    (m,) = mail.sent
    assert m["where"] == ("smtp.gmail.com", 465) and m["creds"] == ("me@example.com", "app-pass")
    assert m["from"] == "me@example.com" and m["to"] == ["to@example.com"]
    assert "Subject: [Gig Radar] 2 new gigs" in m["text"]
    assert "Python developer 1 | Acme | RemoteOK\nhttps://example.com/1" in m["text"]
    assert "Python developer 2 | RemoteOK" in m["text"]
    assert "app-pass" not in m["text"]


def test_email_subject_singular(mail):
    notify.send_email([job(1)])
    assert "Subject: [Gig Radar] 1 new gig\n" in mail.sent[0]["text"]


def test_email_lists_fifteen_and_counts_the_rest():
    text = notify._digest([job(i) for i in range(1, 41)])
    assert text.count("https://example.com/") == 15
    assert text.endswith("...and 25 more in the dashboard.")
    assert "more in the dashboard" not in notify._digest([job(i) for i in range(1, 16)])


def test_email_failure_is_reported_not_raised(mail):
    mail.fail_login = True
    assert notify.send_email([job(1)]) is False and mail.sent == []


def test_a_title_cannot_add_mail_headers(mail):
    notify.send_email([job(1, title="x\r\nBcc: attacker@evil.example")])
    head = mail.sent[0]["text"].split("\n\n")[0]
    assert "Bcc:" not in head


def test_sms_content_and_route(sms):
    posts, _ = sms
    assert notify.send_sms([job(1, title="T" * 200), job(2)]) is True
    url, kw = posts[0]
    assert url == "https://api.twilio.com/2010-04-01/Accounts/ACxyz/Messages.json"
    assert kw["auth"] == ("ACxyz", "tw-token")
    assert kw["data"]["From"] == "+15550001" and kw["data"]["To"] == "+15550002"
    body = kw["data"]["Body"]
    assert body.startswith("Gig Radar: 2 new gig(s). Top: " + "T" * 80 + " @ Acme")
    assert len(body) <= 300 and "T" * 81 not in body


def test_sms_failure_is_reported_not_raised(sms):
    sms[1]["status"] = 401
    assert notify.send_sms([job(1)]) is False


def test_sms_survives_a_job_with_no_title(sms):
    assert notify.send_sms([job(1, title=None, company=None)]) is True


def test_alert_sends_both_and_an_email_failure_does_not_block_the_sms(mail, sms):
    mail.fail_login = True
    notify.alert([job(1)])
    assert mail.sent == [] and len(sms[0]) == 1
    mail.fail_login = False
    notify.alert([job(1)])
    assert len(mail.sent) == 1 and len(sms[0]) == 2


# ---- digest ----------------------------------------------------------------

def table(monkeypatch, **by_name):
    def make(v):
        def fn():
            if isinstance(v, Exception):
                raise v
            return [dict(j) for j in v]
        return fn
    monkeypatch.setattr(digest, "SOURCES", [(n, make(v), 0) for n, v in by_name.items()])


def test_collect_filters_classifies_dedupes_and_sorts(monkeypatch):
    table(monkeypatch,
          RemoteOK=[job(1), job(2, title="Forklift operator"), job(3, title="Blog writer")],
          Jobicy=[job(3, title="Blog writer"), job(9), {"title": "no id", "loc": "Remote"}],
          Remotive=RuntimeError("HTTP 429 too many"))
    jobs, status = digest.collect()
    assert [j["id"] for j in jobs] == ["t9", "t3", "t1"]
    assert [j["domain"] for j in jobs] == ["code", "write", "code"]
    assert status["RemoteOK"] == 2 and status["Jobicy"] == 3
    assert status["Remotive"].startswith("err: HTTP 429")


def test_digest_groups_by_domain_biggest_first_and_caps_at_sixty(monkeypatch):
    jobs = [job(i, domain="code") for i in range(100, 150)] + \
           [job(i, domain="write", title="Blog writer %d" % i) for i in range(1, 40)]
    today, md = digest.to_md(jobs, {"RemoteOK": 89})
    assert md.startswith("# Gig Radar digest - %s (UTC)" % today)
    assert "60 remote, Claude-doable gigs" in md
    assert md.count("\n- [") == 60
    assert md.index("## Coding / Dev / MVPs (50)") < md.index("## Writing / Content (10)")
    assert md.rstrip().endswith("_sources: RemoteOK: 89_")


def test_digest_line_shows_company_salary_and_source():
    _, md = digest.to_md([job(1, domain="code", salary="$5k"), job(2, domain="code", company="")], {})
    assert "- [Python developer 1](https://example.com/1) - Acme - $5k - RemoteOK" in md
    assert "- [Python developer 2](https://example.com/2) - RemoteOK" in md


def test_digest_with_no_jobs_still_has_a_header_and_sources():
    _, md = digest.to_md([], {"RemoteOK": "err: down"})
    assert "0 remote, Claude-doable gigs" in md and "_sources: RemoteOK: err: down_" in md
    assert "\n- [" not in md


def test_a_hostile_title_cannot_forge_a_link_or_a_heading():
    bad = job(1, domain="code", company="Acme](https://evil.example)",
              title="Dev](https://evil.example)\n## Urgent: pay the training fee\n- [x",
              url="javascript:alert(1)")
    _, md = digest.to_md([bad], {})
    assert "](https://evil.example)" not in md
    assert "\n## Urgent" not in md and md.count("\n## ") == 1
    assert "javascript:" not in md
    assert md.count("\n- ") == 1 and "[" not in md.split("\n- ")[1]


def test_a_url_with_brackets_cannot_close_the_link_early():
    _, md = digest.to_md([job(1, domain="code", url="https://example.com/a)(b")], {})
    assert "(https://example.com/a%29%28b)" in md


def test_main_writes_the_dated_file(monkeypatch, tmp_path, capsys):
    table(monkeypatch, RemoteOK=[job(1)])
    monkeypatch.setattr(digest, "__file__", str(tmp_path / "digest.py"))
    digest.main()
    today, _ = digest.to_md([], {})
    text = (tmp_path / "digests" / (today + ".md")).read_text(encoding="utf-8")
    assert "Python developer 1" in text and "(1 gigs)" in capsys.readouterr().out


# ---- local API -------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    import server
    return server.app.test_client(), server


def test_api_jobs_returns_stored_gigs(client):
    import store
    store.upsert_jobs([job(1), job(2)])
    c, _ = client
    data = c.get("/api/jobs").get_json()
    assert [r["id"] for r in data] == ["t2", "t1"] and data[0]["isNew"] is True


def test_api_sources_reports_switches_but_never_the_secrets(client, mail, sms):
    c, _ = client
    raw = c.get("/api/sources").get_data(as_text=True)
    data = c.get("/api/sources").get_json()
    assert data["email"] is True and data["sms"] is True and data["interval"] == config.POLL_INTERVAL
    for secret in ("app-pass", "tw-token", "ACxyz", "+15550002", "me@example.com"):
        assert secret not in raw


def test_api_refresh_forces_a_cycle_and_is_post_only(client, monkeypatch):
    c, server = client
    seen = []
    monkeypatch.setattr(server, "poll_cycle", lambda force=False: seen.append(force) or [1, 2, 3])
    assert c.post("/api/refresh").get_json() == {"new": 3} and seen == [True]
    assert c.get("/api/refresh").status_code == 405


def test_dashboard_is_served_and_other_files_are_not(client):
    c, _ = client
    assert c.get("/").status_code == 200
    for path in ("/.env", "/gigradar.db", "/config.py", "/../.env"):
        assert c.get(path).status_code == 404


def test_config_switches(monkeypatch):
    assert config.email_enabled() is False
    for k in ("SMTP_USER", "SMTP_APP_PASSWORD", "NOTIFY_EMAIL_TO"):
        monkeypatch.setattr(config, k, "x")
    assert config.email_enabled() is True
    assert "@" not in config.USER_AGENT
