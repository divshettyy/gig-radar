"""Each feed parser against a small canned reply. No network."""
import pytest

import config
import sources

KEYS = {"id", "title", "company", "url", "date", "tags", "salary", "loc", "desc", "src"}


def shape_ok(jobs):
    for j in jobs:
        assert set(j) == KEYS
        assert isinstance(j["date"], int) and isinstance(j["tags"], list)
    return True


def test_strip_html_drops_tags_entities_and_runs_of_space():
    assert sources.strip_html("<p>Hi&nbsp;<b>there</b>\n\n &amp; all</p>") == "Hi there & all"
    assert sources.strip_html(None) == "" and sources.strip_html("") == ""
    assert "<script" not in sources.strip_html("<script>alert(1)</script>ok")


def test_every_request_uses_the_generic_user_agent(web):
    web("remotive.com", {"jobs": []})
    sources.src_remotive()
    headers = web.calls[0][2]["headers"]
    assert headers["User-Agent"] == config.USER_AGENT and "@" not in headers["User-Agent"]


def test_remoteok(web):
    web("remoteok.com/api", [
        {"legal": "terms"},
        {"id": 7, "position": "Python Dev", "company": "Acme", "url": "/remote-jobs/7",
         "epoch": 1700000000, "tags": list("abcdefgh"), "salary_min": 80000,
         "salary_max": 120000, "location": "", "description": "<b>Build</b> things"},
        {"id": 8, "position": "", "company": "NoTitle"},
        "garbage",
        {"slug": "s9", "position": "Writer", "apply_url": "https://apply.example/9",
         "salary_min": 999999999},
    ])
    jobs = sources.src_remoteok()
    assert shape_ok(jobs) and [j["id"] for j in jobs] == ["rok7", "roks9"]
    first, second = jobs
    assert first["salary"] == "$80k-$120k" and first["date"] == 1700000000000
    assert first["tags"] == list("abcdef") and first["loc"] == "Remote"
    assert first["desc"] == "Build things" and first["src"] == "RemoteOK"
    assert second["url"] == "https://apply.example/9" and second["salary"] is None


def test_remotive(web):
    web("remotive.com", {"jobs": [{
        "id": 3, "title": "Editor", "company_name": "Pub", "url": "https://remotive.com/3",
        "publication_date": "2024-05-01T10:00:00", "tags": ["writing"], "salary": "  ",
        "candidate_required_location": "Worldwide", "description": "<p>Edit</p>"}]})
    (j,) = sources.src_remotive()
    assert shape_ok([j]) and j["id"] == "rmt3" and j["company"] == "Pub"
    assert j["salary"] is None and j["loc"] == "Worldwide" and j["desc"] == "Edit"
    assert j["date"] == 1714557600000        # a date with no zone is read as UTC, on any machine


def test_arbeitnow_remote_flag_survives_a_city_location(web):
    web("arbeitnow.com", {"data": [
        {"slug": "a", "title": "Backend Dev", "company_name": "X", "url": "https://a/a",
         "created_at": 1700000000, "tags": ["python"], "job_types": ["contract"],
         "location": "Berlin", "remote": True, "description": "d"},
        {"slug": "b", "title": "Backend Dev", "company_name": "X", "url": "https://a/b",
         "created_at": 1700000000, "location": "Berlin", "remote": False},
        {"slug": "c", "title": "Backend Dev", "company_name": "X", "url": "https://a/c",
         "created_at": 1700000000, "location": "", "remote": True},
    ]})
    jobs = sources.src_arbeitnow()
    assert shape_ok(jobs) and jobs[0]["tags"] == ["python", "contract"]
    import classify
    kept = [j["id"] for j in jobs
            if classify.keep(j["title"], j["tags"], j["desc"], j["loc"], "Arbeitnow")]
    assert kept == ["arba", "arbc"]          # the remote job in Berlin is not thrown away
    assert "Berlin" in jobs[0]["loc"]


def test_jobicy(web):
    web("jobicy.com", {"jobs": [
        {"id": 1, "jobTitle": "SEO Writer", "companyName": "J", "url": "https://j/1",
         "pubDate": "2024-05-01T10:00:00+00:00", "jobIndustry": "Marketing",
         "jobType": ["full-time"], "salaryMin": 40000, "salaryMax": 60000,
         "salaryCurrency": "EUR", "jobGeo": "Europe", "jobExcerpt": "<i>write</i>"},
        {"id": 2, "jobTitle": "Analyst", "salaryMin": "50000", "jobDescription": "long"},
    ]})
    one, two = sources.src_jobicy()
    assert shape_ok([one, two])
    assert one["salary"] == "EUR40k-60k" and one["tags"] == ["Marketing", "full-time"]
    assert one["loc"] == "Europe" and one["desc"] == "write" and one["date"] == 1714557600000
    assert two["salary"] == "$50k-50k" and two["desc"] == "long" and two["loc"] == "Remote"


def test_weworkremotely_rss(web):
    items = "".join(
        "<item><title>Co%d: Role: Senior %d</title><link>https://wwr/%d</link>"
        "<guid>g%d</guid><pubDate>Wed, 01 May 2024 10:00:00 +0000</pubDate>"
        "<category>Programming</category><region>Anywhere</region>"
        "<description>&lt;p&gt;Hello&lt;/p&gt;</description></item>" % (i, i, i, i)
        for i in range(70))
    items += "<item><title>No company here</title><link>https://wwr/x</link></item>"
    web("weworkremotely.com", text="<rss><channel>%s</channel></rss>" % items)
    jobs = sources.src_wwr()
    assert shape_ok(jobs) and len(jobs) == 60
    j = jobs[0]
    assert j["id"] == "wwrg0" and j["company"] == "Co0" and j["title"] == "Role: Senior 0"
    assert j["date"] == 1714557600000 and j["tags"] == ["Programming"]
    assert j["loc"] == "Anywhere" and j["desc"] == "Hello"
    assert web.calls[0][2]["headers"]["Accept"] == "application/rss+xml"


def test_weworkremotely_item_without_company_or_guid(web):
    web("weworkremotely.com", text="<rss><channel><item><title>No company here</title>"
        "<link>https://wwr/x</link></item></channel></rss>")
    (j,) = sources.src_wwr()
    assert j["company"] == "" and j["title"] == "No company here"
    assert j["id"] == "wwrhttps://wwr/x" and j["date"] == 0 and j["tags"] == []


def test_hackernews_picks_the_hiring_thread_and_parses_comments(web):
    web("search_by_date", {"hits": [{"title": "Ask HN: Freelancer?", "objectID": "1"},
                                    {"title": "Ask HN: Who is hiring? (May)", "objectID": "42"}]})
    web("items/42", {"children": [
        {"id": 5, "created_at_i": 1700000000,
         "text": "Acme | Remote | Python<p>Apply: <a href=\"https://www.acme.io/jobs\">here</a>"},
        {"id": 6, "text": None}, None, {"id": 7, "text": "gone", "deleted": True},
        {"id": 8, "text": "No link here, just words"},
    ]})
    jobs = sources.src_hn()
    assert shape_ok(jobs) and [j["id"] for j in jobs] == ["hn5", "hn8"]
    assert jobs[0]["title"] == "Acme" and jobs[0]["company"] == "acme.io"
    assert jobs[0]["url"] == "https://www.acme.io/jobs" and jobs[0]["date"] == 1700000000000
    assert jobs[1]["company"] == "(see post)"
    assert jobs[1]["url"] == "https://news.ycombinator.com/item?id=8"


def test_hackernews_falls_back_when_search_fails(web):
    web("search_by_date", status=500)
    web("items/50338728", {"children": []})
    assert sources.src_hn() == []


def test_reddit_public_route_keeps_only_hiring_and_task_posts(web):
    web("www.reddit.com/r/forhire/new.json", {"data": {"children": [
        {"data": {"id": "a", "title": "[Hiring] Writer", "author": "bob", "permalink": "/r/a",
                  "created_utc": 1700000000.0, "link_flair_text": "Hiring",
                  "selftext": "x" * 500}},
        {"data": {"id": "b", "title": "[For Hire] Me", "author": "al", "permalink": "/r/b"}},
        {"data": {"id": "c", "title": "[TASK] Fix sheet", "author": "cy", "permalink": "/r/c"}},
    ]}})
    jobs = sources.src_reddit()
    assert shape_ok(jobs) and [j["id"] for j in jobs] == ["rdta", "rdtc"]
    assert jobs[0]["company"] == "u/bob" and jobs[0]["url"] == "https://www.reddit.com/r/a"
    assert len(jobs[0]["desc"]) == 240 and jobs[0]["loc"] == "Hiring"
    assert all(kind == "GET" for kind, _, _ in web.calls)      # no token request without keys


def test_reddit_uses_oauth_host_when_keys_are_set(web, monkeypatch):
    monkeypatch.setattr(config, "REDDIT_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "REDDIT_CLIENT_SECRET", "csecret")
    web("api/v1/access_token", {"access_token": "tok"})
    web("oauth.reddit.com/r/forhire/new?limit=50", {"data": {"children": []}})
    assert sources.src_reddit() == []
    kind, url, kw = web.calls[0]
    assert kind == "POST" and kw["auth"] == ("cid", "csecret")
    assert web.calls[1][2]["headers"]["Authorization"] == "Bearer tok"


def test_reddit_token_failure_falls_back_to_public_route(web, monkeypatch):
    monkeypatch.setattr(config, "REDDIT_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "REDDIT_CLIENT_SECRET", "csecret")
    web("api/v1/access_token", status=401)
    web("www.reddit.com/r/forhire/new.json", {"data": {"children": []}})
    assert sources.src_reddit() == []
    assert "Authorization" not in web.calls[1][2]["headers"]


def test_freelancer_and_upwork_make_no_call_without_a_token(web):
    assert sources.src_freelancer() == [] and sources.src_upwork() == []
    assert web.calls == []


def test_freelancer(web, monkeypatch):
    monkeypatch.setattr(config, "FREELANCER_OAUTH_TOKEN", "ftok")
    web("freelancer.com/api", {"result": {"projects": [
        {"id": 11, "title": "Scrape site", "seo_url": "python/scrape-site",
         "time_submitted": 1700000000, "budget": {"minimum": 30, "maximum": 250},
         "currency": {"sign": "€"}, "jobs": [{"name": "Python"}, {"name": None}],
         "preview_description": "need <b>data</b>"},
        {"id": 12, "title": "No budget"},
    ]}})
    one, two = sources.src_freelancer()
    assert shape_ok([one, two]) and one["id"] == "fln11" and one["salary"] == "€30-250"
    assert one["url"] == "https://www.freelancer.com/projects/python/scrape-site"
    assert one["tags"] == ["Python"] and one["desc"] == "need data" and two["salary"] is None
    assert web.calls[0][2]["headers"]["Freelancer-OAuth-V1"] == "ftok"


def test_upwork(web, monkeypatch):
    monkeypatch.setattr(config, "UPWORK_ACCESS_TOKEN", "utok")
    web("api.upwork.com", {"data": {"marketplaceJobPostingsSearch": {"edges": [
        {"node": {"title": "Deck", "description": "<p>" + "y" * 400 + "</p>",
                  "ciphertext": "~01ab", "createdDateTime": "2024-05-01T10:00:00Z",
                  "amount": {"rawValue": "500", "currency": "USD"}}},
        {"node": {"title": "No id"}},
    ]}}})
    jobs = sources.src_upwork()
    assert shape_ok(jobs) and len(jobs) == 1               # a posting with no id is skipped
    j = jobs[0]
    assert j["id"] == "upw~01ab" and j["url"] == "https://www.upwork.com/jobs/~01ab"
    assert j["salary"] == "500 USD" and len(j["desc"]) == 240 and j["date"] == 1714557600000
    assert web.calls[0][2]["headers"]["Authorization"] == "Bearer utok"


def test_upwork_empty_or_odd_reply_is_no_jobs(web, monkeypatch):
    monkeypatch.setattr(config, "UPWORK_ACCESS_TOKEN", "utok")
    web("api.upwork.com", {"errors": [{"message": "gated"}]})
    assert sources.src_upwork() == []


@pytest.mark.parametrize("fn,frag", [
    (sources.src_remoteok, "remoteok.com"), (sources.src_remotive, "remotive.com"),
    (sources.src_arbeitnow, "arbeitnow.com"), (sources.src_jobicy, "jobicy.com"),
])
def test_http_error_raises_so_the_poller_can_mark_the_source_bad(web, fn, frag):
    web(frag, status=503)
    with pytest.raises(RuntimeError):
        fn()


def test_time_helpers():
    assert sources._iso_ms("2024-05-01T10:00:00Z") == 1714557600000
    assert sources._iso_ms("2024-05-01T15:30:00+05:30") == 1714557600000
    assert sources._iso_ms("not a date") == 0 and sources._iso_ms(None) == 0
    assert sources._rfc_ms("Wed, 01 May 2024 10:00:00 +0000") == 1714557600000
    assert sources._rfc_ms("junk") == 0 and sources._rfc_ms("") == 0
    assert sources._host("https://www.acme.io/x") == "acme.io" and sources._host("") == ""


def test_source_table_names_are_unique_and_ttls_sane():
    names = [n for n, _, _ in sources.SOURCES]
    assert len(names) == len(set(names)) == 9
    assert dict((n, t) for n, _, t in sources.SOURCES)["Remotive"] >= 6 * 3600   # at most 4 calls a day
    assert all(callable(fn) and ttl >= 300 for _, fn, ttl in sources.SOURCES)
