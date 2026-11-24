"""A failing feed backs off exponentially instead of being retried every cycle."""
import poller
import store


def _setup(monkeypatch, calls):
    def bad():
        calls.append(1)
        raise RuntimeError("429")
    monkeypatch.setattr(poller, "SOURCES", [("Flaky", bad, 60)])
    poller.STATUS.clear()
    poller.FAILS.clear()


def test_backoff_doubles_and_caps():
    poller.FAILS.clear()
    poller.FAILS["x"] = (1, 1000)
    assert poller.backoff_remaining("x", 1000) == poller.BACKOFF_BASE
    poller.FAILS["x"] = (3, 1000)
    assert poller.backoff_remaining("x", 1000) == poller.BACKOFF_BASE * 4
    poller.FAILS["x"] = (20, 1000)
    assert poller.backoff_remaining("x", 1000) == poller.BACKOFF_MAX
    assert poller.backoff_remaining("x", 1000 + poller.BACKOFF_MAX + 1) == 0
    assert poller.backoff_remaining("unknown", 5) == 0


def test_failed_feed_is_skipped_until_backoff_expires(monkeypatch):
    calls = []
    _setup(monkeypatch, calls)
    poller.poll_cycle()
    poller.poll_cycle()
    assert len(calls) == 1            # second cycle skipped by backoff
    poller.poll_cycle(force=True)
    assert len(calls) == 2            # force bypasses it


def test_success_clears_backoff(monkeypatch):
    poller.FAILS["Good"] = (2, 0)
    monkeypatch.setattr(poller, "SOURCES", [("Good", lambda: [], 60)])
    poller.poll_cycle(force=True)
    assert "Good" not in poller.FAILS
