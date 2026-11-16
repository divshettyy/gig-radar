import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import classify, store


class WordBoundary(unittest.TestCase):
    def test_no_midword_matches(self):
        self.assertEqual(classify.classify("Capital markets associate", [], "storage and loads"), "other")

    def test_prefix_forms_still_match(self):
        self.assertEqual(classify.classify("Python developers wanted", [], ""), "code")
        self.assertEqual(classify.classify("Build chatbots", [], ""), "ai")


class Dedupe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        store.DB = os.path.join(self.tmp, "t.db")
        store.init()

    def test_cross_feed_duplicate_is_dropped(self):
        a = {"id": "rok1", "title": "Senior Python Developer (Remote)", "company": "Acme, Inc."}
        b = {"id": "rem9", "title": "Senior Python Developer", "company": "Acme Inc"}
        self.assertEqual(len(store.upsert_jobs([a])), 1)
        self.assertEqual(len(store.upsert_jobs([b])), 0)

    def test_same_batch_duplicate_and_distinct(self):
        jobs = [{"id": "1", "title": "Writer", "company": "X"},
                {"id": "2", "title": "Writer", "company": "X"},
                {"id": "3", "title": "Writer", "company": "Y"}]
        self.assertEqual(len(store.upsert_jobs(jobs)), 2)


if __name__ == "__main__":
    unittest.main()
