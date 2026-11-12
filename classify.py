"""Map a job to a Claude-doable domain by keyword. Mirrors the dashboard."""

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
    ("other", "Other remote", []),
]

def classify(title, tags, desc):
    hay = (str(title) + " " + " ".join(tags or []) + " " + str(desc or "")).lower()
    for key, _label, kws in DOMAINS:
        if key == "other":
            continue
        if any(w in hay for w in kws):
            return key
    return "other"

LABELS = {k: lbl for k, lbl, _ in DOMAINS}
