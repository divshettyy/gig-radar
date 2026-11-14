import os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store, poller


def _fresh_db():
    store.DB = os.path.join(tempfile.mkdtemp(), "t.db")
    store.init()
    poller.STATUS.clear()


class Seeding(unittest.TestCase):
    def test_all_sources_down_does_not_seed(self):
        _fresh_db()
        def boom(): raise RuntimeError("down")
        with mock.patch.object(poller, "SOURCES", [("A", boom, 0)]), mock.patch.object(poller.notify, "alert") as al:
            poller.poll_cycle(force=True)
        self.assertFalse(store.seeded())
        al.assert_not_called()

    def test_first_good_run_seeds_without_alert_then_alerts_new(self):
        _fresh_db()
        job = lambda i: {"id": "a%d" % i, "title": "Python developer %d" % i, "company": "C%d" % i, "tags": [], "desc": "", "loc": "Remote", "date": 1}
        feed = [job(1)]
        with mock.patch.object(poller, "SOURCES", [("A", lambda: list(feed), 0)]), mock.patch.object(poller.notify, "alert") as al:
            poller.poll_cycle(force=True)
            self.assertTrue(store.seeded()); al.assert_not_called()
            feed.append(job(2))
            poller.poll_cycle(force=True)
            al.assert_called_once()


if __name__ == "__main__":
    unittest.main()
