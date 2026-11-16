"""Map a job to a Claude-doable domain by keyword. Mirrors the dashboard."""
import re

DOMAINS = [
    ("ai", "AI / Chatbot / Automation",
     ["chatbot", "gpt", "llm", "prompt", "automation", "zapier", "make.com", "n8n",
      "ai agent", "openai", "anthropic", "rag", "workflow", "conversational"]),
    ("write", "Writing / Content",
     ["writer", "writing", "content", "blog", "copywriter", "copywriting", "article",
      "editor", "ghostwriter", "journalist", "seo content", "wordpress"]),
    ("code", "Coding / Dev / MVPs",
     ["developer", "engineer", "python", "javascript", "typescript", "react", "node",
      "scraper", "scraping", "api", "backend", "frontend", "full stack", "chrome extension",
      "shopify", "wordpress dev", "bug", "software"]),
    ("data", "Data / Research",
     ["data", "research", "analyst", "lead generation", "list building", "data entry",
      "market research", "competitor", "enrichment", "survey", "annotation"]),
    ("seo", "SEO / Programmatic",
     ["seo", "search engine", "programmatic", "meta description", "backlink", "keyword",
      "local seo", "google business"]),
    ("deck", "Slides / Decks",
     ["deck", "presentation", "slides", "powerpoint", "pitch", "keynote", "gamma"]),
    ("trans", "Translation / Localization",
     ["translation", "translate", "localization", "localisation", "subtitle",
      "proofread", "bilingual", "transcription", "transcribe"]),
    ("sheet", "Spreadsheet / Excel",
     ["excel", "spreadsheet", "google sheets", "vlookup", "pivot", "apps script", "macro"]),
    ("market", "Email / Ads / Marketing",
     ["email", "newsletter", "klaviyo", "marketing", "ad copy", "ads", "campaign",
      "social media", "ugc", "growth"]),
    ("admin", "Resume / Docs / Admin",
     ["resume", "cv", "cover letter", "linkedin", "virtual assistant", "documentation",
      "technical writer", "sop", "proposal", "grant"]),
    ("other", "Misc - try with Claude", []),
]

# Keywords match at a word START (so "developers"/"apis" still hit) but never
# mid-word: bare substring matching tagged "capital" as code (api), "storage"
# as AI (rag), "loads" as marketing (ads), "discover" as admin (cv)...
_DOMAIN_RES = [
    (key, re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in kws) + r")"))
    for key, _label, kws in DOMAINS if key != "other"
]

def classify(title, tags, desc):
    hay = (str(title) + " " + " ".join(tags or []) + " " + str(desc or "")).lower()
    for key, rx in _DOMAIN_RES:
        if rx.search(hay):
            return key
    return "other"

LABELS = {k: lbl for k, lbl, _ in DOMAINS}

# Roles that need hands/presence or can't be delivered by an AI agent remotely.
# Multi-word where a bare word would false-positive (e.g. "server" = web server).
# "cleaner" and "warehouse" are deliberately NOT bare here: they silently
# dropped legitimate remote gigs like "Freelance Data Cleaner" and "Data
# Warehouse Engineer (Remote)" (verified -- classify.keep() returned False
# for both before this fix). Spelled out as specific roles instead.
PHYSICAL = [
    "nurse", "nursing", "registered nurse", "lpn", "cna", "caregiver", "nanny",
    "babysitter", "housekeep", "janitor", "custodian", "house cleaner",
    "office cleaner", "commercial cleaner", "residential cleaner", "cleaning staff",
    "dishwasher", "barista", "bartender", "waiter", "waitress", "line cook", "chef",
    "kitchen staff", "food service", "restaurant server", "warehouse worker",
    "warehouse associate", "warehouse staff", "warehouse operative", "forklift",
    "picker packer", "material handler", "construction", "carpenter", "electrician",
    "plumber", "hvac", "welder", "mason", "roofer", "mechanic", "machinist",
    "machine operator", "assembly line", "factory worker", "production worker",
    "security guard", "cashier", "retail associate", "retail store", "store associate",
    "sales associate", "stocker", "farm worker", "landscap", "gardener", "hairdresser",
    "barber", "esthetician", "massage therapist", "phlebotom", "dentist",
    "dental assistant", "dental hygienist", "physician", "surgeon", "veterinar",
    "lifeguard", "delivery driver", "truck driver", "cdl", "rideshare", "chauffeur",
    "courier", "field technician", "field service", "equipment installer",
]

# Match at a word start only, with an optional plural, so "cna" does not fire on
# "CNAME" or "waiter" on "awaiter". Entries in _STEMS are prefixes on purpose
# ("housekeep" covers housekeeper and housekeeping).
_STEMS = {"housekeep", "landscap", "phlebotom", "veterinar"}
_PHYSICAL_RE = re.compile(
    r"\b(?:" + "|".join(
        re.escape(p) + ("" if p in _STEMS else r"(?:s|es)?\b")
        for p in sorted(set(PHYSICAL) | _STEMS, key=len, reverse=True)) + ")")

def keep(title, tags, desc, loc, src):
    """True if the gig is remote AND plausibly doable with an AI agent."""
    t = (str(title) + " " + " ".join(tags or []) + " " + str(desc or "") + " "
         + str(loc or "")).lower()
    if _PHYSICAL_RE.search(t):
        return False
    locl = str(loc or "").lower()
    # Arbeitnow mixes onsite EU roles: loc is "Remote" when remote, else a city.
    if src == "Arbeitnow" and "remote" not in locl:
        return False
    # HN posts tag ONSITE / REMOTE in the body.
    if src == "HackerNews":
        tl = (str(title) + " " + str(desc)).lower()
        if ("onsite" in tl or "on-site" in tl or "on site" in tl) and "remote" not in tl:
            return False
    return True
