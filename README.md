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
