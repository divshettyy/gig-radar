"""Produce a dated Markdown digest of fresh, Claude-doable, remote gigs from the
public feeds. Used by the cloud routine (no secrets needed) and runnable locally.

Writes digests/<UTC-date>.md and prints a one-line summary.
"""
import os
import time
import datetime

from classify import classify, keep, LABELS
from sources import SOURCES

TOP = 60  # cap per digest

def collect():
    jobs, status = [], {}
    for name, fn, _ttl in SOURCES:
        try:
            got = fn()
            got = [j for j in got
                   if keep(j.get("title"), j.get("tags"), j.get("desc"), j.get("loc"), name)]
            for j in got:
                j["domain"] = classify(j.get("title"), j.get("tags"), j.get("desc"))
            jobs.extend(got)
            status[name] = len(got)
        except Exception as e:
            status[name] = "err: " + str(e)[:80]
    # dedupe
    seen, uniq = set(), []
    for j in jobs:
        if j.get("id") and j["id"] not in seen:
            seen.add(j["id"])
            uniq.append(j)
    uniq.sort(key=lambda j: j.get("date") or 0, reverse=True)
    return uniq, status

def _text(s):
    """Feed text is untrusted. One line, and no characters that can close a
    Markdown link or start a heading or list item."""
    s = " ".join(str(s or "").split())
    for ch in "[]()<>`|":
        s = s.replace(ch, " ")
    return " ".join(s.split()).lstrip("#-*+> ")

def _link(u):
    u = str(u or "").strip()
    if not u.lower().startswith(("http://", "https://")) or any(c in u for c in " \t\r\n<>"):
        return ""
    return u.replace("(", "%28").replace(")", "%29")

def to_md(jobs, status):
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    out = ["# Gig Radar digest - %s (UTC)" % today, ""]
    out.append("%d remote, Claude-doable gigs. Verify on the source before applying; "
               "never pay a training fee.\n" % min(len(jobs), TOP))
    by_dom = {}
    for j in jobs[:TOP]:
        by_dom.setdefault(j.get("domain", "other"), []).append(j)
    for dom, items in sorted(by_dom.items(), key=lambda kv: -len(kv[1])):
        out.append("## %s (%d)" % (LABELS.get(dom, dom), len(items)))
        for j in items:
            bits = [b for b in [_text(j.get("company")), _text(j.get("salary")),
                                _text(j.get("src"))] if b]
            meta = " - ".join(bits)
            title, url = _text(j.get("title")) or "untitled", _link(j.get("url"))
            out.append("- %s%s" % ("[%s](%s)" % (title, url) if url else title,
                                   (" - " + meta) if meta else ""))
        out.append("")
    srcline = ", ".join("%s: %s" % (k, v) for k, v in status.items())
    out.append("---\n_sources: %s_" % srcline)
    return today, "\n".join(out)

def main():
    jobs, status = collect()
    today, md = to_md(jobs, status)
    d = os.path.join(os.path.dirname(__file__), "digests")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, today + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print("wrote %s (%d gigs). sources=%s" % (path, min(len(jobs), TOP), status))

if __name__ == "__main__":
    main()
