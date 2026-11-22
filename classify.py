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

# A keyword in the title says far more about the gig than one buried in the
# description ("... we use a workflow tool" must not outvote a title of
# "Senior Copywriter"), so hits are weighted by where they occur.
W_TITLE, W_TAGS, W_DESC = 5, 3, 1

def _hits(rx, text):
    return len(set(m.group(0) for m in rx.finditer(text))) if text else 0

def classify(title, tags, desc):
    """Highest-scoring domain; ties go to the earlier entry in DOMAINS."""
    t = str(title or "").lower()
    g = " ".join(str(x) for x in (tags or [])).lower()
    d = str(desc or "").lower()
    best, best_score = "other", 0
    for key, rx in _DOMAIN_RES:
        score = W_TITLE * _hits(rx, t) + W_TAGS * _hits(rx, g) + W_DESC * _hits(rx, d)
        if score > best_score:
            best, best_score = key, score
    return best

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

# Scam / low-quality patterns. Deliberately specific multi-word phrases: a bare
# word like "commission" or "crypto" would drop legitimate gigs ("crypto
# exchange backend developer", "sales role with commission").
_SCAM_PATTERNS = [
    r"registration fee", r"training fee", r"security deposit", r"pay (?:a |an )?(?:fee|deposit) to (?:apply|start)",
    r"(?:buy|purchase) (?:your own |a )?(?:starter )?(?:kit|equipment) (?:to|before)",
    r"commission[- ]only", r"100% commission",
    r"multi[- ]?level marketing", r"\bmlm\b", r"network marketing", r"downline",
    r"earn \$?\d[\d,]*\+? (?:per|a|/) ?(?:day|daily|hour) (?:from home|guaranteed|easily)",
    r"guaranteed (?:income|earnings|\$)", r"get rich", r"passive income (?:system|opportunity)",
    r"(?:whats ?app|telegram) (?:only|to apply)", r"no experience (?:needed|necessary|required),? (?:earn|make) \$",
    r"forex signals?", r"crypto signals?", r"pump (?:and|&) dump",
    r"send (?:us )?(?:a )?(?:payment|money|gift card)", r"cash (?:a )?check",
    r"(?:buy|purchase|pay(?:ment)?(?: in| with| by)?|send|wire|redeem|scratch) (?:us |the |some |your )?(?:\w+ )?gift ?cards?",
]
_SCAM_RE = re.compile("|".join(_SCAM_PATTERNS), re.I)

def is_scammy(title, desc):
    """True if the posting matches a known pay-to-work / MLM / get-rich pattern."""
    return bool(_SCAM_RE.search((str(title or "") + " " + str(desc or ""))))

def keep(title, tags, desc, loc, src):
    """True if the gig is remote AND plausibly doable with an AI agent."""
    t = (str(title) + " " + " ".join(tags or []) + " " + str(desc or "") + " "
         + str(loc or "")).lower()
    if _PHYSICAL_RE.search(t):
        return False
    if is_scammy(title, desc):
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
