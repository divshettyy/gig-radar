"""Regression tests for classify.keep() -- the signal-to-noise filter that
drops physical/onsite roles from the aggregated feed.

Why this matters: keyword substring-matching is easy to get wrong in both
directions, but a false NEGATIVE (a legitimate remote, AI-doable gig
silently dropped) is worse than a false positive here, because the user
never sees what was filtered out to notice the mistake. Two of the
PHYSICAL list's bare words -- "cleaner" and "warehouse" -- did exactly
that: "Freelance Data Cleaner" and "Data Warehouse Engineer (Remote)" were
both being dropped as if they were a house cleaner or a warehouse worker,
directly undermining the project's own "highest signal-to-noise ratio"
goal. Confirmed with classify.keep() before writing the fix; these tests
pin the corrected behavior down so it can't regress silently again.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import classify  # noqa: E402


class TestKeepFalsePositives(unittest.TestCase):
    """Legitimate remote/tech gigs that must NOT be filtered out."""

    def test_data_warehouse_engineer_is_kept(self):
        self.assertTrue(classify.keep(
            "Data Warehouse Engineer (Remote)", [],
            "Build and maintain our data warehouse pipelines.",
            "Remote", "RemoteOK"))

    def test_data_cleaner_is_kept(self):
        self.assertTrue(classify.keep(
            "Freelance Data Cleaner needed", [],
            "Clean up messy CSV lead lists for a sales team.",
            "Remote", "RemoteOK"))

    def test_warehouse_management_system_consultant_is_kept(self):
        self.assertTrue(classify.keep(
            "Remote Warehouse Management System Consultant", [],
            "Configure WMS software remotely.",
            "Remote", "RemoteOK"))


class TestKeepTruePositivesStillFiltered(unittest.TestCase):
    """Genuine physical/onsite roles must still be dropped after the fix."""

    def test_warehouse_worker_onsite_is_dropped(self):
        self.assertFalse(classify.keep(
            "Warehouse Worker (Onsite, Ohio)", [],
            "Pick and pack orders in our distribution center.",
            "Columbus, OH", "RemoteOK"))

    def test_house_cleaner_is_dropped(self):
        self.assertFalse(classify.keep(
            "House Cleaner needed weekly", [],
            "Clean residential homes in the Austin area.",
            "Austin, TX", "RemoteOK"))

    def test_office_cleaner_is_dropped(self):
        self.assertFalse(classify.keep(
            "Office Cleaner, evenings", [],
            "Commercial office cleaning, in person.",
            "Chicago, IL", "RemoteOK"))

    def test_forklift_operator_is_dropped(self):
        self.assertFalse(classify.keep(
            "Forklift Operator", [],
            "Warehouse forklift operation.",
            "Dallas, TX", "RemoteOK"))

    def test_nurse_is_dropped(self):
        self.assertFalse(classify.keep(
            "Registered Nurse", [], "Hospital floor nursing.", "Remote", "RemoteOK"))


class TestSourceSpecificRules(unittest.TestCase):
    def test_arbeitnow_onsite_city_is_dropped(self):
        self.assertFalse(classify.keep(
            "Backend Developer", [], "", "Berlin, Germany", "Arbeitnow"))

    def test_arbeitnow_remote_is_kept(self):
        self.assertTrue(classify.keep(
            "Backend Developer", [], "", "Remote", "Arbeitnow"))

    def test_hackernews_onsite_without_remote_is_dropped(self):
        self.assertFalse(classify.keep(
            "Senior Engineer", [], "ONSITE | San Francisco, CA",
            "", "HackerNews"))

    def test_hackernews_remote_mentioned_is_kept(self):
        self.assertTrue(classify.keep(
            "Senior Engineer", [], "REMOTE | Full-time", "", "HackerNews"))


if __name__ == "__main__":
    unittest.main()
