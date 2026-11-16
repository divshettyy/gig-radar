# Changelog

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
