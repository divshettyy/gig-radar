# Changelog

## Unreleased

- **Failure backoff**: a feed that errors (down, 429 rate-limit) now waits 2 min, doubling per consecutive failure up to 1 h, before the next retry, instead of being hit every cycle. Success resets it; `--force` bypasses it. 3 new tests.

- **Alert latency**: due feeds are now fetched concurrently (up to 8 threads) instead of one after another, so a slow or timing-out feed (15 s timeout) no longer delays alerts from every other source; a poll cycle now takes roughly the slowest feed rather than the sum. Results are still processed in `SOURCES` order on one thread (SQLite stays single-threaded) and a failing feed stays isolated. 1 new test.

- **Scam filter precision**: the bare `gift cards?` pattern dropped legitimate gigs ("developer for a gift card marketplace"). It now only fires on payment-context phrases (buy/purchase/pay in/send/redeem gift cards). 2 new tests.

- **Scam/low-quality filter**: `classify.is_scammy()` drops pay-to-apply (registration/training fees, starter kits), commission-only/MLM/downline, guaranteed-income, forex/crypto-signal and cheque-cashing postings in `keep()` before they reach the dashboard or alerts. Patterns are specific multi-word phrases so legitimate gigs ("crypto exchange backend developer", "base plus commission") are kept. 12 new tests.

- **URL-based dedupe**: the same gig reached through two feeds is now collapsed by canonical posting URL (tracking params, www, fragment and trailing slash ignored) in addition to company+title, which also catches company-less feeds. Existing jobs are backfilled into `seen_keys` on init. 4 new tests.

- **Retention pruning**: jobs first seen >60 days ago are deleted each poll cycle (`store.prune`), keeping the DB and dashboard query small; `seen_keys` is retained so pruned gigs never re-alert. Added a date index on `jobs`. 2 new tests.
- **Classifier is now score-based, not first-match**: domain keyword hits are weighted title (5) > tags (3) > description (1) and the best domain wins (ties keep the DOMAINS order). A stray "workflow"/"email" in a job body no longer overrides a clear title like "Senior Copywriter". +4 tests.

## 2026-11-20: discoverability and dependency-hygiene pass (no code behaviour change)

Part of a repository-wide polish effort. On top of the earlier README badges, topic
tags and issue/PR templates, this pass adds a Dependabot configuration that opens
grouped weekly pull requests for Python packages and GitHub Actions, an `.editorconfig`
for consistent formatting across contributors, and upper version bounds on the three
runtime dependencies (`requests<3`, `flask<4`, `python-dotenv<2`) so a future breaking
major cannot land silently. The poller, classifier, store and notifier are unchanged.

## 2026-11-15: tests, CI, and the faults the tests found

Tests went from 12 to 122 (6 of them from the 14 November nightly change, merged here) (`./venv/bin/python -m pytest -q`). They cover the onsite/physical
filter, domain classification, every feed parser against a canned reply, storage and
de-duplication, which gigs raise an alert, the email and SMS text and switches, the Markdown
digest, and the local API. Nothing in the suite reaches the network, the mail server, the SMS
provider or the real database: `tests/conftest.py` blanks every secret and makes any real
outbound call an error.

Fixed
- **Remote Arbeitnow jobs were thrown away.** Arbeitnow gives a city as the location even for
  remote jobs and marks them with a separate flag. The flag was ignored when a city was present,
  so the filter dropped the job as onsite. Location now reads "Remote (Berlin)".
- **Alert flood when a feed comes back.** Only the very first cycle was treated as a silent
  seed. A feed that was down on that cycle sent its whole back catalogue as "new" on its first
  success, and if every feed was down on the first cycle the next cycle alerted on everything.
  A feed's first successful fetch is now stored without an alert.
- **Filter matched inside other words.** "cna" dropped anything mentioning a DNS CNAME, "waiter"
  dropped "awaiter". Physical-role words now match at a word start, with plurals.
- **Digest could be forged by a feed.** Titles, companies and URLs went into the Markdown
  unescaped, so a title could close the link, point it elsewhere, or add a heading. Text is now
  one line with link characters removed, and only http(s) URLs become links.
- **Dates without a time zone** (Remotive) were read in the machine's zone, 5.5 hours off in
  India. They are read as UTC.
- **One odd record could take out a feed or an alert**: a Jobicy salary sent as text, and an SMS
  for a gig with no title, both raised errors. Upwork postings with no id all shared one id and
  collapsed into a single gig; they are skipped.

Added
- `requirements-dev.txt` (pytest), GitHub Actions workflow running the suite on Python 3.11 and 3.13.

Known limits, not fixed
- Cross-feed duplicate detection is permanent: a company that posts the same title again months
  later is treated as already seen.
- The filter still drops a few remote tech gigs that use a physical-role word: "Chef" (the
  DevOps tool), "game mechanics", "Courier" (the font), "Nurse Educator" content work.
- Untested: `dashboard.html` (browser code), `run.sh`, `install-service.sh`, the background loop
  in `server.py`, and the live feeds themselves (a feed changing its format is only seen at run time).

## 2026-11-14
- Domain keywords match at a word start ("capital" is no longer coding because of "api").
- The same gig posted on several feeds under different ids is stored and alerted once (same company and title).
- Background loop wakes every 1-5 minutes; per-feed limits still decide what is fetched.

## 2026-11-13
- MIT license, digests and database ignored by git, README polish, Security section from the audit.

## 2026-11-12
- Local backend: six public feeds plus Reddit r/forhire, Freelancer.com and Upwork with your own
  tokens; SQLite store; email (Gmail app password) and SMS (Twilio) alerts; local dashboard.
- systemd service and installer for a 24/7 start at boot.
- Onsite and physical roles filtered out; Platforms and Claude playbook tabs in the dashboard.
- Catch-all domain renamed "Misc - try with Claude".
- `digest.py`: dated Markdown digest of Claude-doable remote gigs.
- Fix: "cleaner" and "warehouse" no longer drop "Data Cleaner" and "Data Warehouse Engineer".
