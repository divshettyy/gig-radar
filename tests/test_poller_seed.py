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

    def test_one_job_with_a_non_string_tag_does_not_drop_the_whole_feed(self):
        # A malformed tag used to raise in keep()'s filter comprehension, which
        # poll_cycle's per-feed try/except swallowed -- losing every job in the
        # batch. Both good jobs must survive and get stored.
        _fresh_db()
        feed = [
            {"id": "b1", "title": "Remote Python developer", "company": "C1",
             "tags": [123, None, "python"], "desc": "", "loc": "Remote", "date": 2},
            {"id": "b2", "title": "Remote data analyst", "company": "C2",
             "tags": ["data"], "desc": "", "loc": "Remote", "date": 1},
        ]
        with mock.patch.object(poller, "SOURCES", [("A", lambda: list(feed), 0)]), \
                mock.patch.object(poller.notify, "alert"):
            poller.poll_cycle(force=True)  # first run seeds silently
        self.assertEqual(poller.STATUS["A"]["state"], "ok")
        self.assertEqual(poller.STATUS["A"]["n"], 2)
        ids = {r["id"] for r in store.recent()}
        self.assertEqual(ids, {"b1", "b2"})


if __name__ == "__main__":
    unittest.main()


class Concurrency(unittest.TestCase):
    def test_slow_feed_does_not_serialize_and_failure_is_isolated(self):
        import time
        _fresh_db()
        def slow():
            time.sleep(0.4)
            return [{"id": "s1", "title": "Python developer", "company": "S", "tags": [], "desc": "", "loc": "Remote", "date": 1}]
        def boom(): raise RuntimeError("down")
        srcs = [("S1", slow, 0), ("S2", slow, 0), ("S3", slow, 0), ("Bad", boom, 0)]
        t0 = time.time()
        with mock.patch.object(poller, "SOURCES", srcs), mock.patch.object(poller.notify, "alert"):
            poller.poll_cycle(force=True)
        self.assertLess(time.time() - t0, 1.0)          # serial would be >= 1.2 s
        self.assertEqual(poller.STATUS["Bad"]["state"], "bad")
        self.assertEqual(poller.STATUS["S1"]["state"], "ok")
