"""More of classify.keep() and classify.classify(): wrong drops and wrong keeps."""
import pytest

import classify


@pytest.mark.parametrize("title,desc", [
    ("DevOps engineer", "Manage DNS: A, AAAA and CNAME records for 40 domains."),
    ("Async Rust developer", "You will write a custom awaiter and executor."),
    ("Technical writer", "Document our API. Scanalytics background a plus."),
])
def test_tech_words_that_contain_a_physical_word_are_kept(title, desc):
    assert classify.keep(title, [], desc, "Remote", "RemoteOK") is True


@pytest.mark.parametrize("title", [
    "CNA - night shift", "LPN, home visits", "CDL driver", "Line cooks wanted",
    "Electricians (commercial)", "Housekeeping lead", "Landscaping crew",
    "Veterinary assistant", "Phlebotomist", "Delivery Driver", "Security guards",
])
def test_physical_roles_are_dropped_in_any_form(title):
    assert classify.keep(title, [], "", "Remote", "RemoteOK") is False


def test_physical_word_in_tags_or_location_field_drops():
    assert classify.keep("Assistant", ["Nursing"], "", "Remote", "Jobicy") is False


def test_missing_fields_do_not_crash_and_are_kept():
    assert classify.keep(None, None, None, None, "Remotive") is True


@pytest.mark.parametrize("tags", [
    [123, None, "python"],      # numeric + null tags from messy feed JSON
    [{"name": "backend"}],      # a dict tag
    (1, 2, 3),                  # a non-list iterable of ints
])
def test_non_string_tags_do_not_crash_keep(tags):
    # keep() must coerce tags like classify() does. Before the fix a single
    # non-string tag raised TypeError inside poller/digest's keep() filter
    # comprehension, which the per-feed try/except swallowed -- silently
    # dropping EVERY job from that feed for the whole cycle, not just the one
    # bad listing.
    assert classify.keep("Remote Python Developer", tags, "desc", "Remote", "RemoteOK") is True


def test_non_string_physical_tag_still_drops():
    # Coercion must not weaken the physical-role filter: a physical keyword in
    # the tags still drops the gig even when other tags are non-strings.
    assert classify.keep("Assistant", [None, "nursing", 7], "", "Remote", "Jobicy") is False


def test_arbeitnow_needs_remote_in_location_other_sources_do_not():
    assert classify.keep("Python developer", [], "", "Munich", "Arbeitnow") is False
    assert classify.keep("Python developer", [], "", "Munich", "Remotive") is True
    assert classify.keep("Python developer", [], "", "Remote (Munich)", "Arbeitnow") is True


@pytest.mark.parametrize("body,kept", [
    ("ONSITE | NYC", False), ("On-site only, Austin", False), ("on site, London", False),
    ("ONSITE or REMOTE (US)", True), ("Full-time, Berlin", True),
])
def test_hackernews_onsite_rule(body, kept):
    assert classify.keep("Acme", [], body, "", "HackerNews") is kept


def test_onsite_rule_is_only_for_hackernews():
    assert classify.keep("Engineer", [], "ONSITE | NYC", "Remote", "RemoteOK") is True


@pytest.mark.parametrize("title,tags,desc,domain", [
    ("Build a GPT chatbot", [], "", "ai"),
    ("Blog writer", [], "", "write"),
    ("Python scraper", [], "", "code"),
    ("Market research assistant", [], "", "data"),
    ("Backlink outreach", [], "", "seo"),
    ("Pitch deck designer", [], "", "deck"),
    ("Subtitle translation EN-DE", [], "", "trans"),
    ("Excel VLOOKUP fix", [], "", "sheet"),
    ("Newsletter campaign", [], "", "market"),
    ("Resume rewrite", [], "", "admin"),
    ("Voice actor", [], "", "other"),
    ("Helper", ["Python"], "", "code"),
    ("Helper", [], "Needs Zapier", "ai"),
])
def test_classify_domains(title, tags, desc, domain):
    assert classify.classify(title, tags, desc) == domain
    assert domain in classify.LABELS


def test_classify_first_domain_wins_and_handles_none():
    assert classify.classify("Prompt writer", None, None) == "ai"   # ai is listed before write
    assert classify.classify(None, None, None) == "other"


def test_physical_words_in_description_do_not_drop_software_gigs():
    assert classify.keep("Python Developer", ["python"],
                         "Build a scheduling chatbot for nursing homes and electricians", "Remote", "RemoteOK") is True


def test_physical_words_in_title_still_drop():
    assert classify.keep("Registered Nurse", [], "remote triage", "Remote", "RemoteOK") is False
