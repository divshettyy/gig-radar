"""Job source fetchers. Public feeds need no auth; others use tokens from .env.

Every fetcher returns a list of normalized dicts:
  {id,title,company,url,date(ms),tags[],salary|None,loc,desc,src}
All descriptions/titles come from third parties and are treated as untrusted
text: we strip HTML to plain text and never feed them to an LLM.
"""
import re
import html
import time
import xml.etree.ElementTree as ET
import requests

import config

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

def strip_html(s):
    if not s:
        return ""
    s = TAG_RE.sub(" ", str(s))
    s = html.unescape(s)
    return WS_RE.sub(" ", s).strip()

def _get(url, headers=None, timeout=15):
    h = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    if headers:
        h.update(headers)
    r = requests.get(url, headers=h, timeout=timeout)
    r.raise_for_status()
    return r

# ---------------- public feeds (no key, server-side = no CORS issue) --------

def src_remoteok():
    data = _get("https://remoteok.com/api").json()
    out = []
    for j in data[1:]:
        if not isinstance(j, dict) or not j.get("position"):
            continue
        smin = j.get("salary_min") or 0
        salary = None
        if isinstance(smin, (int, float)) and 0 < smin < 2e7:
            smax = j.get("salary_max") or smin
            salary = "$%dk-$%dk" % (round(smin / 1000), round(smax / 1000))
        out.append({
            "id": "rok" + str(j.get("id") or j.get("slug")),
            "title": j.get("position", ""), "company": j.get("company", ""),
            "url": j.get("apply_url") or j.get("url") or "https://remoteok.com" + (j.get("url") or ""),
            "date": int((j.get("epoch") or 0) * 1000),
            "tags": (j.get("tags") or [])[:6], "salary": salary,
            "loc": j.get("location") or "Remote", "desc": strip_html(j.get("description")),
            "src": "RemoteOK"})
    return out

def src_remotive():
    data = _get("https://remotive.com/api/remote-jobs?limit=80").json()
    out = []
    for j in data.get("jobs", []):
        sal = (j.get("salary") or "").strip()
        out.append({
            "id": "rmt" + str(j.get("id")), "title": j.get("title", ""),
            "company": j.get("company_name", ""), "url": j.get("url", ""),
            "date": _iso_ms(j.get("publication_date")), "tags": (j.get("tags") or [])[:6],
            "salary": sal or None, "loc": j.get("candidate_required_location") or "Remote",
            "desc": strip_html(j.get("description")), "src": "Remotive"})
    return out

def src_arbeitnow():
    data = _get("https://www.arbeitnow.com/api/job-board-api").json()
    out = []
    for j in data.get("data", []):
        out.append({
            "id": "arb" + str(j.get("slug") or j.get("url")), "title": j.get("title", ""),
            "company": j.get("company_name", ""), "url": j.get("url", ""),
            "date": int((j.get("created_at") or 0) * 1000),
            "tags": ((j.get("tags") or []) + (j.get("job_types") or []))[:6], "salary": None,
            "loc": j.get("location") or ("Remote" if j.get("remote") else ""),
            "desc": strip_html(j.get("description")), "src": "Arbeitnow"})
    return out

def src_jobicy():
    data = _get("https://jobicy.com/api/v2/remote-jobs?count=60").json()
    out = []
    for j in data.get("jobs", []):
        salary = None
        if j.get("salaryMin"):
            cur = j.get("salaryCurrency") or "$"
            salary = "%s%dk-%dk" % (cur, round(j["salaryMin"] / 1000),
                                    round((j.get("salaryMax") or j["salaryMin"]) / 1000))
        industry = j.get("jobIndustry") or []
        jtype = j.get("jobType") or []
        if isinstance(industry, str):
            industry = [industry]
        if isinstance(jtype, str):
            jtype = [jtype]
        out.append({
            "id": "job" + str(j.get("id")), "title": j.get("jobTitle", ""),
            "company": j.get("companyName", ""), "url": j.get("url", ""),
            "date": _iso_ms(j.get("pubDate")), "tags": (industry + jtype)[:6], "salary": salary,
            "loc": j.get("jobGeo") or "Remote",
            "desc": strip_html(j.get("jobExcerpt") or j.get("jobDescription")), "src": "Jobicy"})
    return out

def src_wwr():
    xml = _get("https://weworkremotely.com/remote-jobs.rss",
               headers={"Accept": "application/rss+xml"}).text
    root = ET.fromstring(xml)
    out = []
    for item in root.iter("item"):
        def g(t):
            e = item.find(t)
            return e.text if e is not None and e.text else ""
        title = g("title")
        parts = title.split(": ")
        out.append({
            "id": "wwr" + (g("guid") or g("link")),
            "title": ": ".join(parts[1:]) if len(parts) > 1 else title,
            "company": parts[0] if len(parts) > 1 else "", "url": g("link"),
            "date": _rfc_ms(g("pubDate")),
            "tags": [g("category")] if g("category") else [], "salary": None,
            "loc": g("region") or "Remote", "desc": strip_html(g("description")),
            "src": "WeWorkRemotely"})
    return out[:60]

def src_hn():
    sid = "50338728"  # fallback: Nov 2026 "Who is hiring"
    try:
        s = _get("https://hn.algolia.com/api/v1/search_by_date?query=who%20is%20hiring"
                 "&tags=story&hitsPerPage=20").json()
        for h in s.get("hits", []):
            if "who is hiring" in (h.get("title") or "").lower():
                sid = h["objectID"]
                break
    except Exception:
        pass
    item = _get("https://hn.algolia.com/api/v1/items/" + str(sid)).json()
    out = []
    for c in (item.get("children") or [])[:80]:
        if not c or not c.get("text") or c.get("deleted"):
            continue
        txt = strip_html(c["text"])
        m = re.search(r"https?://[^\s\"'<)]+", c["text"])
        first_url = m.group(0) if m else ""
        head = re.split(r"\s[|•\-]\s", txt)[0][:90]
        out.append({
            "id": "hn" + str(c["id"]), "title": head or txt[:80],
            "company": _host(first_url) or "(see post)",
            "url": first_url or "https://news.ycombinator.com/item?id=" + str(c["id"]),
            "date": int((c.get("created_at_i") or 0) * 1000), "tags": [], "salary": None,
            "loc": "", "desc": txt[:240], "src": "HackerNews"})
    return out

# ---------------- authenticated feeds (your own account/token) --------------

def src_reddit():
    """r/forhire client posts. App-only OAuth if client id/secret present, else
    public JSON (works from a residential IP). Filters to [Hiring]/[Task]."""
    headers = {"User-Agent": config.USER_AGENT}
    base = "https://www.reddit.com"
    if config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET:
        try:
            tok = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=(config.REDDIT_CLIENT_ID, config.REDDIT_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": config.USER_AGENT}, timeout=15)
            tok.raise_for_status()
            at = tok.json().get("access_token")
            if at:
                headers["Authorization"] = "Bearer " + at
                base = "https://oauth.reddit.com"
        except Exception:
            pass
    url = base + "/r/forhire/new.json?limit=50" if base.endswith(".com") and "oauth" not in base \
        else base + "/r/forhire/new?limit=50"
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    out = []
    for ch in r.json().get("data", {}).get("children", []):
        d = ch.get("data", {})
        title = d.get("title", "")
        low = title.lower()
        if not (low.startswith("[hiring") or low.startswith("[task")):
            continue
        out.append({
            "id": "rdt" + d.get("id", ""), "title": title,
            "company": "u/" + d.get("author", ""),
            "url": "https://www.reddit.com" + d.get("permalink", ""),
            "date": int((d.get("created_utc") or 0) * 1000), "tags": ["reddit"],
            "salary": None, "loc": d.get("link_flair_text") or "",
            "desc": strip_html(d.get("selftext"))[:240], "src": "Reddit r/forhire"})
    return out

def src_freelancer():
    if not config.FREELANCER_OAUTH_TOKEN:
        return []
    r = requests.get(
        "https://www.freelancer.com/api/projects/0.1/projects/active/"
        "?limit=50&job_details=true&full_description=false",
        headers={"Freelancer-OAuth-V1": config.FREELANCER_OAUTH_TOKEN,
                 "User-Agent": config.USER_AGENT}, timeout=20)
    r.raise_for_status()
    projs = r.json().get("result", {}).get("projects", []) or []
    out = []
    for p in projs:
        b = p.get("budget") or {}
        cur = (p.get("currency") or {}).get("sign", "$")
        salary = None
        if b.get("minimum"):
            salary = "%s%s-%s" % (cur, b.get("minimum"), b.get("maximum") or "")
        jobs = [j.get("name") for j in (p.get("jobs") or []) if j.get("name")]
        out.append({
            "id": "fln" + str(p.get("id")), "title": p.get("title", ""), "company": "",
            "url": "https://www.freelancer.com/projects/" + (p.get("seo_url") or ""),
            "date": int((p.get("time_submitted") or 0) * 1000), "tags": jobs[:6],
            "salary": salary, "loc": "Remote",
            "desc": strip_html((p.get("preview_description") or "")), "src": "Freelancer.com"})
    return out

def src_upwork():
    """Upwork public API is gated (approved key + OAuth2). Best-effort: if a token
    is provided, query the GraphQL job search; any failure skips Upwork cleanly."""
    if not config.UPWORK_ACCESS_TOKEN:
        return []
    query = {"query": """query { marketplaceJobPostingsSearch(
        marketPlaceJobFilter: { searchExpression_eq: "" },
        searchType: USER_JOBS_SEARCH, sortAttributes: [{field: RECENCY}]
      ) { edges { node { title description ciphertext createdDateTime
        amount { rawValue currency } } } } }"""}
    r = requests.post("https://api.upwork.com/graphql", json=query, timeout=20,
                      headers={"Authorization": "Bearer " + config.UPWORK_ACCESS_TOKEN,
                               "User-Agent": config.USER_AGENT})
    r.raise_for_status()
    edges = (((r.json() or {}).get("data") or {})
             .get("marketplaceJobPostingsSearch") or {}).get("edges") or []
    out = []
    for e in edges:
        n = e.get("node") or {}
        amt = n.get("amount") or {}
        cipher = n.get("ciphertext") or ""
        out.append({
            "id": "upw" + cipher, "title": n.get("title", ""), "company": "",
            "url": "https://www.upwork.com/jobs/" + cipher,
            "date": _iso_ms(n.get("createdDateTime")), "tags": [],
            "salary": (str(amt.get("rawValue")) + " " + amt.get("currency", "")) if amt.get("rawValue") else None,
            "loc": "Remote", "desc": strip_html(n.get("description"))[:240], "src": "Upwork"})
    return out

# ---------------- helpers ---------------------------------------------------

def _host(u):
    m = re.match(r"https?://([^/]+)", u or "")
    return m.group(1).replace("www.", "") if m else ""

def _iso_ms(s):
    if not s:
        return 0
    try:
        s = s.replace("Z", "+00:00")
        import datetime
        return int(datetime.datetime.fromisoformat(s).timestamp() * 1000)
    except Exception:
        return 0

def _rfc_ms(s):
    if not s:
        return 0
    try:
        from email.utils import parsedate_to_datetime
        return int(parsedate_to_datetime(s).timestamp() * 1000)
    except Exception:
        return 0

# name, fn, ttl seconds
SOURCES = [
    ("RemoteOK", src_remoteok, 3 * 3600),
    ("Remotive", src_remotive, 12 * 3600),
    ("Arbeitnow", src_arbeitnow, 3 * 3600),
    ("Jobicy", src_jobicy, 3 * 3600),
    ("WeWorkRemotely", src_wwr, 3 * 3600),
    ("HackerNews", src_hn, 6 * 3600),
    ("Reddit r/forhire", src_reddit, 900),
    ("Freelancer.com", src_freelancer, 900),
    ("Upwork", src_upwork, 900),
]
