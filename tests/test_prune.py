import time

import store


def _job(i, **kw):
    d = {"id": "j%d" % i, "title": "Role %d" % i, "company": "Co%d" % i, "url": "u", "date": 1}
    d.update(kw)
    return d


def test_prune_removes_old_keeps_recent_and_blocks_realert():
    store.init()
    store.upsert_jobs([_job(1), _job(2)])
    old = int(time.time()) - 90 * 86400
    with store._lock, store._conn() as c:
        c.execute("UPDATE jobs SET first_seen=? WHERE id='j1'", (old,))
    assert store.prune(days=60) == 1
    ids = {j["id"] for j in store.recent()}
    assert ids == {"j2"}
    # the pruned gig re-appearing under a new id is still a known duplicate
    assert store.upsert_jobs([_job(1, id="other")]) == []


def test_prune_noop_when_all_recent():
    store.init()
    store.upsert_jobs([_job(3)])
    assert store.prune() == 0
