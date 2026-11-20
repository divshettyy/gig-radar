"""Cross-feed duplicates are also caught by canonical posting URL."""
import store
from conftest import job


def test_url_key_strips_tracking_and_noise():
    a = store.url_key("https://www.Example.com/jobs/42/?utm_source=x&ref=y#top")
    b = store.url_key("http://example.com/jobs/42")
    assert a == b == "url:example.com/jobs/42"


def test_url_key_keeps_identifying_query():
    assert store.url_key("https://news.ycombinator.com/item?id=5") != \
        store.url_key("https://news.ycombinator.com/item?id=6")


def test_url_key_ignores_homepages_and_junk():
    assert store.url_key("https://example.com/") == ""
    assert store.url_key("") == ""
    assert store.url_key(None) == ""
    assert store.url_key("mailto:a@b.c") == ""


def test_same_url_different_title_company_is_duplicate():
    a = job(1, title="Build a Shopify store", company="")
    b = job(2, title="Shopify developer needed", company="Acme")
    a["url"] = "https://example.com/gig/9?utm_campaign=z"
    b["url"] = "https://www.example.com/gig/9"
    assert len(store.upsert_jobs([a])) == 1
    assert store.upsert_jobs([b]) == []
