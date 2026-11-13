# Gig Radar (local backend)

A small local service that aggregates freelance/part-time gigs from public feeds
**and your own authenticated accounts**, dedupes them, shows them on a local
dashboard, and pushes **email / SMS alerts** when new ones appear.

It is the private, authenticated companion to the shareable read-only dashboard
artifact. Secrets (tokens, app passwords) live only in a local `.env` and never
leave this machine.

## What it pulls

**Public (no account):** RemoteOK, Remotive, Arbeitnow, Jobicy, We Work Remotely,
Hacker News "Who is hiring".

**Authenticated (optional, your own account/token):**
- **Reddit r/forhire** — `[Hiring]` / `[Task]` posts. Easiest and safest.
- **Freelancer.com** — active projects via your OAuth token.
- **Upwork** — *advanced*. Upwork's public API needs an approved key + OAuth2;
  access is gated and often not granted to individuals. If you get an access
  token, paste it in `.env`; if it fails, Upwork is skipped automatically.

Platforms with **no public job-search API** (Fiverr, Outlier, Internshala, most
microtask sites) can't be polled this way — open those in the Platforms tab of
the main dashboard and check them manually.

## Setup

```bash
cd ~/gig-radar
cp .env.example .env        # then edit .env (all fields optional)
./run.sh                    # first run builds the venv, then serves
```

Open http://localhost:8787

With an empty `.env` the 6 public feeds work immediately. Add tokens to unlock more.

### Email alerts (Gmail)
1. Turn on 2-Step Verification on the Google account.
2. Create an **App Password**: https://myaccount.google.com/apppasswords
3. Put the 16-char app password + your address in `.env`
   (`SMTP_USER`, `SMTP_APP_PASSWORD`, `NOTIFY_EMAIL_TO`).

> Use an **App Password**, never your real Google password.

### SMS alerts (optional, Twilio free trial)
Sign up at https://www.twilio.com/try-twilio, then copy your Account SID, Auth
Token, and trial "from" number into `.env` (`TWILIO_*`). Trial accounts can only
text your own verified number.

### Reddit (optional)
https://www.reddit.com/prefs/apps → **create app** → type **script**. Copy the
client id (under the app name) and secret into `REDDIT_CLIENT_ID` /
`REDDIT_CLIENT_SECRET`. Read-only, app-only — no account password is stored.

### Freelancer.com (optional)
https://accounts.freelancer.com/settings/develop → generate an OAuth token →
`FREELANCER_OAUTH_TOKEN`.

## Run it in the background / on a schedule

Keep it running (simple):
```bash
nohup ./run.sh > gigradar.log 2>&1 &
```

Or run one poll from cron without the web server:
```bash
# every 20 min
*/20 * * * * cd ~/gig-radar && ./venv/bin/python poller.py >> gigradar.log 2>&1
```

## Safety notes
- Never share your `.env`. It is git-ignored.
- All job text is treated as untrusted and shown as plain text; it is never fed
  to an LLM.
- Respect each platform's rate limits and terms. This tool reads your own feeds;
  it does not scrape behind logins with your password.
- Alert pay figures and listings are third-party — verify on the source before
  applying or paying. Never pay a "training fee".

## Security

This has been reviewed for the risks that matter for a credential-holding
local service:
- **No committed secrets.** `.env` (and the DB/logs/venv) are git-ignored and
  were never tracked; only `.env.example` with empty placeholder values is in
  the repo. There is no real token, password, or phone number anywhere in the
  current tree or git history.
- **No SSRF surface.** Every outbound request target in `sources.py` is a
  hardcoded API/feed URL baked into the source — the app never fetches a URL
  supplied by a user, job listing, or request parameter, so there's nothing
  to allowlist.
- **No stored/DOM XSS.** Third-party job titles/descriptions/tags are
  untrusted by design (see `sources.py` docstring) and the dashboard
  (`dashboard.html`) only ever writes them via `el()`/`textContent`, never
  `innerHTML`, so a malicious listing can't inject script into the page.
  Links are set via the `href` property, not interpolated into markup.
- **Local-only web surface.** `server.py` binds Flask to `127.0.0.1` only; the
  dashboard and its `/api/*` routes (including the no-auth `POST
  /api/refresh`) are never reachable from the network, so the lack of
  auth/CSRF tokens on them is intentional, not an oversight.
- **Templating is plain text.** Email/SMS bodies (`notify.py`) are built with
  `%`-formatting into a `MIMEText` plaintext message and a size-capped SMS
  body — no HTML/template-injection surface in the alert path.
- **RSS parsing.** `sources.py` parses the We Work Remotely feed with
  `xml.etree.ElementTree`, which does not resolve external entities, so it
  isn't exposed to classic XXE.

Residual, accepted risk: Reddit/Freelancer/Upwork calls send your token or
app credentials over HTTPS to each platform's own API — that's inherent to
"authenticated feeds," not a bug, and is why those three are opt-in.

## Run 24/7 on boot (systemd, WSL2)

systemd is already enabled here. Install the service once (needs sudo password):

```bash
sudo bash ~/gig-radar/install-service.sh
```

Then it starts automatically whenever the WSL distro boots and restarts on crash.

Manage it:
```bash
systemctl status gig-radar      # health
journalctl -u gig-radar -f      # live logs
sudo systemctl restart gig-radar
sudo systemctl disable --now gig-radar   # turn off
```

### Make WSL itself start at Windows login (optional)
A WSL systemd service only runs while the distro is running, and WSL starts when
you first open it. To have it come up at Windows logon, add a Task Scheduler task
(run in Windows PowerShell, not WSL):

```powershell
schtasks /create /tn "WSL Gig Radar" /tr "wsl.exe -d Ubuntu -e true" /sc onlogon /rl highest
```

Replace `Ubuntu` with your distro name from `wsl -l -q`. The `-e true` just boots
the distro; systemd then starts gig-radar.
