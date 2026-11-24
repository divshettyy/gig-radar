"""Storage, de-duplication and the rule for which gigs raise an alert."""
import time

import pytest

import notify
import poller
import store
from conftest import job


@pytest.fixture
def alerts(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "alert", lambda jobs: sent.append(list(jobs)))
    poller.STATUS.clear()
    poller.FAILS.clear()
    return sent


def feeds(monkeypatch, **by_name):
    """Replace the source table. A value is a job list or an exception to raise."""
    def make(v):
        def fn():
            if isinstance(v, Exception):
                raise v
            return [dict(j) for j in v]
        return fn
    table = [(name.replace("_", " "), make(v), 3600) for name, v in by_name.items()]
    monkeypatch.setattr(poller, "SOURCES", table)


def test_upsert_returns_only_new_rows_and_skips_missing_ids():
    assert [j["id"] for j in store.upsert_jobs([job(1), job(2), {"title": "no id"}])] == ["t1", "t2"]
    assert [j["id"] for j in store.upsert_jobs([job(2), job(3)])] == ["t3"]
    assert len(store.recent()) == 3


def test_upsert_does_not_overwrite_a_stored_job():
    store.upsert_jobs([job(1, title="first")])
    store.upsert_jobs([job(1, title="second")])
    assert store.recent()[0]["title"] == "first"


def test_recent_is_newest_first_limited_and_round_trips_fields():
    store.upsert_jobs([job(i, tags=["a", "b"], salary="$1k", domain="code") for i in range(1, 6)])
    rows = store.recent(limit=3)
    assert [r["id"] for r in rows] == ["t5", "t4", "t3"]
    assert rows[0]["tags"] == ["a", "b"] and rows[0]["salary"] == "$1k"
    assert rows[0]["dom"] == "code" and rows[0]["isNew"] is True


def test_is_new_turns_off_after_a_day(monkeypatch):
    store.upsert_jobs([job(1)])
    real = time.time()
    monkeypatch.setattr(time, "time", lambda: real + 25 * 3600)
    assert store.recent()[0]["isNew"] is False


def test_meta_and_fetch_marks():
    assert store.last_fetch("X") == 0 and store.seeded() is False
    store.mark_fetch("X"); store.mark_seeded(); store.set_meta("k", 1); store.set_meta("k", 2)
    assert store.last_fetch("X") > 0 and store.seeded() is True and store.get_meta("k") == "2"
    assert store.get_meta("absent", "dflt") == "dflt"


def test_first_cycle_stores_everything_and_alerts_nothing(monkeypatch, alerts):
    feeds(monkeypatch, RemoteOK=[job(1), job(2)])
    assert poller.poll_cycle(force=True) == []
    assert alerts == [] and len(store.recent()) == 2 and store.seeded()


def test_second_cycle_alerts_only_the_new_gigs_newest_first(monkeypatch, alerts):
    feeds(monkeypatch, RemoteOK=[job(1), job(2)])
    poller.poll_cycle(force=True)
    feeds(monkeypatch, RemoteOK=[job(1), job(2), job(3), job(9)])
    fresh = poller.poll_cycle(force=True)
    assert [j["id"] for j in fresh] == ["t9", "t3"]
    assert [[j["id"] for j in batch] for batch in alerts] == [["t9", "t3"]]


def test_nothing_new_means_no_alert(monkeypatch, alerts):
    feeds(monkeypatch, RemoteOK=[job(1)])
    poller.poll_cycle(force=True)
    assert poller.poll_cycle(force=True) == [] and alerts == []


def test_same_gig_from_two_feeds_is_stored_and_alerted_once(monkeypatch, alerts):
    feeds(monkeypatch, RemoteOK=[job(1)], Jobicy=[job(1)])
    poller.poll_cycle(force=True)
    feeds(monkeypatch, RemoteOK=[job(1), job(5)], Jobicy=[job(5), job(5)])
    fresh = poller.poll_cycle(force=True)
    assert [j["id"] for j in fresh] == ["t5"] and len(alerts[0]) == 1
    assert len(store.recent()) == 2


def test_filtered_gigs_are_neither_stored_nor_alerted(monkeypatch, alerts):
    feeds(monkeypatch, RemoteOK=[job(1)])
    poller.poll_cycle(force=True)
    feeds(monkeypatch, RemoteOK=[job(1), job(2, title="Registered Nurse"), job(3, title="Blog writer")])
    fresh = poller.poll_cycle(force=True)
    assert [j["id"] for j in fresh] == ["t3"] and fresh[0]["domain"] == "write"
    assert {r["id"] for r in store.recent()} == {"t1", "t3"}


def test_a_failing_feed_does_not_stop_the_others(monkeypatch, alerts):
    feeds(monkeypatch, RemoteOK=[job(1)], Jobicy=RuntimeError("HTTP 503"))
    poller.poll_cycle(force=True)
    assert poller.STATUS["RemoteOK"]["state"] == "ok" and poller.STATUS["RemoteOK"]["n"] == 1
    assert poller.STATUS["Jobicy"]["state"] == "bad" and "503" in poller.STATUS["Jobicy"]["err"]
    assert store.last_fetch("Jobicy") == 0 and store.last_fetch("RemoteOK") > 0


def test_feed_that_was_down_on_the_first_cycle_does_not_flood_alerts_later(monkeypatch, alerts):
    """A feed's first successful fetch is its back catalogue, not news."""
    feeds(monkeypatch, RemoteOK=[job(1)], Jobicy=RuntimeError("down"))
    poller.poll_cycle(force=True)
    old = [job(i, src="Jobicy") for i in range(100, 160)]
    feeds(monkeypatch, RemoteOK=[job(1), job(2)], Jobicy=old)
    fresh = poller.poll_cycle(force=True)
    assert [j["id"] for j in fresh] == ["t2"]                  # only the real news
    assert [[j["id"] for j in b] for b in alerts] == [["t2"]]
    assert len(store.recent()) == 62                           # the back catalogue is still stored
    feeds(monkeypatch, RemoteOK=[job(1), job(2)], Jobicy=old + [job(200, src="Jobicy")])
    assert [j["id"] for j in poller.poll_cycle(force=True)] == ["t200"]   # from now on it alerts


def test_all_feeds_down_on_the_first_cycle_does_not_flood_on_the_next(monkeypatch, alerts):
    feeds(monkeypatch, RemoteOK=RuntimeError("no network"))
    assert poller.poll_cycle(force=True) == []
    feeds(monkeypatch, RemoteOK=[job(i) for i in range(1, 80)])
    assert poller.poll_cycle(force=True) == [] and alerts == []
    assert len(store.recent()) == 79


def test_feed_inside_its_ttl_is_not_fetched_unless_forced(monkeypatch, alerts):
    hits = []
    monkeypatch.setattr(poller, "SOURCES", [("RemoteOK", lambda: hits.append(1) or [job(1)], 3600)])
    poller.poll_cycle()
    poller.poll_cycle()
    assert len(hits) == 1
    poller.poll_cycle(force=True)
    assert len(hits) == 2
