"""Fetch all due sources, store new jobs, send alerts. One cycle per call."""
import time

import store
import notify
from classify import classify, keep
from sources import SOURCES

STATUS = {}  # name -> {"state": ok|bad|skip, "n": int, "at": ts, "err": str}

def poll_cycle(force=False):
    store.init()
    now = time.time()
    collected = []
    for name, fn, ttl in SOURCES:
        if not force and (now - store.last_fetch(name)) < ttl:
            STATUS.setdefault(name, {})["state"] = STATUS.get(name, {}).get("state", "cached")
            continue
        try:
            jobs = fn()
            jobs = [j for j in jobs
                    if keep(j.get("title"), j.get("tags"), j.get("desc"), j.get("loc"), name)]
            for j in jobs:
                j["domain"] = classify(j.get("title"), j.get("tags"), j.get("desc"))
            collected.extend(jobs)
            store.mark_fetch(name)
            STATUS[name] = {"state": "ok", "n": len(jobs), "at": int(now), "err": ""}
        except Exception as e:
            STATUS[name] = {"state": "bad", "n": 0, "at": int(now), "err": str(e)[:160]}
            print("[poll] %s failed: %s" % (name, e))

    # dedupe within this batch by id
    seen_ids = set()
    uniq = []
    for j in collected:
        if j.get("id") and j["id"] not in seen_ids:
            seen_ids.add(j["id"])
            uniq.append(j)

    fresh = store.upsert_jobs(uniq)

    first_run = not store.seeded()
    if first_run:
        # Only seed once at least one source actually answered. Otherwise a
        # first run with every source down would mark the DB seeded with zero
        # jobs, and the next successful poll would alert on the whole backlog.
        if any(st.get("state") == "ok" and st.get("at") == int(now) for st in STATUS.values()):
            store.mark_seeded()
        print("[poll] first run: seeded %d jobs, no alerts this pass" % len(fresh))
        return []

    if fresh:
        fresh.sort(key=lambda j: j.get("date") or 0, reverse=True)
        print("[poll] %d new gig(s)" % len(fresh))
        notify.alert(fresh)
    return fresh

if __name__ == "__main__":
    import sys
    f = "--force" in sys.argv
    new = poll_cycle(force=f)
    print("done. new=%d total_recent=%d" % (len(new), len(store.recent())))
    for name, st in STATUS.items():
        print("  %-20s %s" % (name, st))
