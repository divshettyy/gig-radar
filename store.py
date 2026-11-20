"""SQLite persistence: jobs + source fetch timestamps."""
import os
import re
import json
import sqlite3
import threading
import time

DB = os.path.join(os.path.dirname(__file__), "gigradar.db")
_lock = threading.Lock()

def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with _lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, title TEXT, company TEXT, url TEXT, date INTEGER,
            tags TEXT, salary TEXT, loc TEXT, descr TEXT, src TEXT, domain TEXT,
            first_seen INTEGER)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_date ON jobs(date DESC, first_seen DESC)")
        c.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, val TEXT)")
        # Cross-feed duplicate detection: the same gig is often posted on
        # several feeds under different ids.
        c.execute("CREATE TABLE IF NOT EXISTS seen_keys(key TEXT PRIMARY KEY)")
        for r in c.execute("SELECT title, company, url FROM jobs").fetchall():
            for k in (content_key(r["title"], r["company"]), url_key(r["url"])):
                if k:
                    c.execute("INSERT OR IGNORE INTO seen_keys(key) VALUES(?)", (k,))

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_NOISE = re.compile(r"\b(remote|worldwide|freelance|contract|full[- ]?time|part[- ]?time|m/f/d|f/m/d)\b")

def content_key(title, company):
    """Normalised (company, title) identity used to collapse cross-posted gigs."""
    t = _NON_ALNUM.sub(" ", _NOISE.sub(" ", str(title or "").lower())).strip()
    c = _NON_ALNUM.sub(" ", str(company or "").lower()).strip()
    return (c + "|" + t) if (t and c) else ""

_TRACKING = re.compile(r"^(utm_.*|ref|ref_src|source|src|fbclid|gclid|mc_.*)$", re.I)

def url_key(url):
    """Canonical form of a posting URL (scheme/www/fragment/trailing slash and
    tracking params stripped) so the same gig linked from two feeds collapses
    even when title/company text differs. Returns "" for non-http or empty urls."""
    from urllib.parse import urlsplit, parse_qsl, urlencode
    u = str(url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return ""
    sp = urlsplit(u)
    host = sp.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    path = sp.path.rstrip("/")
    q = sorted((k, v) for k, v in parse_qsl(sp.query) if not _TRACKING.match(k))
    if not host or (not path and not q):
        return ""          # bare homepage links identify nothing
    return "url:" + host + path + ("?" + urlencode(q) if q else "")

def get_meta(key, default=None):
    with _lock, _conn() as c:
        r = c.execute("SELECT val FROM meta WHERE key=?", (key,)).fetchone()
        return r["val"] if r else default

def set_meta(key, val):
    with _lock, _conn() as c:
        c.execute("INSERT INTO meta(key,val) VALUES(?,?) "
                  "ON CONFLICT(key) DO UPDATE SET val=excluded.val", (key, str(val)))

def last_fetch(src):
    v = get_meta("fetch:" + src)
    return int(v) if v else 0

def mark_fetch(src):
    set_meta("fetch:" + src, int(time.time()))

def seeded():
    return get_meta("seeded") == "1"

def mark_seeded():
    set_meta("seeded", "1")

def upsert_jobs(jobs):
    """Insert jobs not already stored. Returns the list that were new."""
    now = int(time.time())
    fresh = []
    with _lock, _conn() as c:
        for j in jobs:
            if not j.get("id"):
                continue
            exists = c.execute("SELECT 1 FROM jobs WHERE id=?", (j["id"],)).fetchone()
            if exists:
                continue
            keys = [k for k in (content_key(j.get("title"), j.get("company")),
                                url_key(j.get("url"))) if k]
            if any(c.execute("SELECT 1 FROM seen_keys WHERE key=?", (k,)).fetchone()
                   for k in keys):
                continue  # same gig already stored/alerted via another feed
            for k in keys:
                c.execute("INSERT OR IGNORE INTO seen_keys(key) VALUES(?)", (k,))
            c.execute("""INSERT INTO jobs
                (id,title,company,url,date,tags,salary,loc,descr,src,domain,first_seen)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (j["id"], j.get("title", ""), j.get("company", ""), j.get("url", ""),
                 int(j.get("date") or 0), json.dumps(j.get("tags") or []),
                 j.get("salary"), j.get("loc", ""), j.get("desc", ""),
                 j.get("src", ""), j.get("domain", "other"), now))
            fresh.append(j)
    return fresh

RETENTION_DAYS = 60

def prune(days=RETENTION_DAYS):
    """Delete jobs first seen more than `days` ago so the DB and the dashboard
    query stay small. seen_keys is deliberately kept: a pruned gig that gets
    re-listed on a feed is still recognised as a duplicate and never re-alerts.
    Returns the number of rows removed."""
    cutoff = int(time.time()) - int(days) * 86400
    with _lock, _conn() as c:
        return c.execute("DELETE FROM jobs WHERE first_seen < ?", (cutoff,)).rowcount

def recent(limit=400):
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM jobs ORDER BY date DESC, first_seen DESC "
                         "LIMIT ?", (limit,)).fetchall()
    out = []
    cutoff = int(time.time()) - 24 * 3600
    for r in rows:
        out.append({
            "id": r["id"], "title": r["title"], "company": r["company"], "url": r["url"],
            "date": r["date"], "tags": json.loads(r["tags"] or "[]"), "salary": r["salary"],
            "loc": r["loc"], "desc": r["descr"], "src": r["src"], "dom": r["domain"],
            "isNew": r["first_seen"] >= cutoff,
        })
    return out
