"""Fetch all due sources, store new jobs, send alerts. One cycle per call."""
import time
from concurrent.futures import ThreadPoolExecutor

import store
import notify
from classify import classify, keep
from sources import SOURCES

STATUS = {}  # name -> {"state": ok|bad|skip, "n": int, "at": ts, "err": str}
FAILS = {}   # name -> (consecutive failures, last failure ts); in-memory backoff
BACKOFF_BASE = 120       # seconds after the first failure
BACKOFF_MAX = 3600       # never wait longer than an hour between retries


def backoff_remaining(name, now):
    """Seconds a failing feed must still wait before a retry (0 = go ahead).
    Doubles per consecutive failure, so a feed that is down or rate-limiting
    (e.g. Reddit 429) isn't hammered every cycle and can't slow the others."""
    n, at = FAILS.get(name, (0, 0))
    if not n:
        return 0
    wait = min(BACKOFF_MAX, BACKOFF_BASE * 2 ** (n - 1))
    return max(0, at + wait - now)


def poll_cycle(force=False):
    store.init()
    now = time.time()
    collected = []
    succeeded = 0
    backlog = set()   # sources fetched for the first time: their jobs are old, not news
    due = []
    for name, fn, ttl in SOURCES:
        if not force and (now - store.last_fetch(name)) < ttl:
            STATUS.setdefault(name, {})["state"] = STATUS.get(name, {}).get("state", "cached")
            continue
        if not force and backoff_remaining(name, now) > 0:
            continue
        due.append((name, fn))

    # Fetch every due feed concurrently: one slow/timing-out feed (15 s timeout)
    # no longer delays alerts from all the others. Network I/O only; results are
    # consumed below in SOURCES order so processing stays deterministic and all
    # SQLite access stays on this thread.
    def _fetch(item):
        try:
            return item[1](), None
        except Exception as e:
            return None, e

    with ThreadPoolExecutor(max_workers=max(1, min(len(due), 8))) as pool:
        results = list(pool.map(_fetch, due))

    for (name, _fn), (jobs, err) in zip(due, results):
        try:
            if err is not None:
                raise err
            jobs = [j for j in jobs
                    if keep(j.get("title"), j.get("tags"), j.get("desc"), j.get("loc"), name)]
            for j in jobs:
                j["domain"] = classify(j.get("title"), j.get("tags"), j.get("desc"))
            if not store.last_fetch(name):
                backlog.add(name)
            for j in jobs:
                j["_feed"] = name
            collected.extend(jobs)
            succeeded += 1
            store.mark_fetch(name)
            FAILS.pop(name, None)
            STATUS[name] = {"state": "ok", "n": len(jobs), "at": int(now), "err": ""}
        except Exception as e:
            FAILS[name] = (FAILS.get(name, (0, 0))[0] + 1, now)
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
    try:
        store.prune()
    except Exception as e:   # housekeeping must never block alerts
        print("[poll] prune failed: %s" % e)
    stored = len(fresh)
    # A feed's first successful fetch is its whole back catalogue. Alerting on it
    # would send dozens of old gigs when a feed that was down comes back.
    fresh = [j for j in fresh if j.pop("_feed", None) not in backlog]
    for j in uniq:
        j.pop("_feed", None)

    first_run = not store.seeded()
    if first_run:
        if succeeded:   # with every feed down nothing is seeded yet; try again next cycle
            store.mark_seeded()
        print("[poll] first run: seeded %d jobs, no alerts this pass" % stored)
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
