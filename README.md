# First Tech Job (India)

A phone-friendly list of **entry-level software, AI and data jobs in India** (freshers, 0–2 years,
and internships), refreshed every 30 minutes.

## Sources

| Site | How | Post time |
|---|---|---|
| Company career pages (Greenhouse, Lever, Ashby: 55 companies) | public JSON | exact |
| Naukri | JSON search API, filtered to 1 year of experience | exact |
| foundit (Monster India) | JSON search, 0–1 years | exact |
| Instahyre | JSON search, 0 years | first seen |
| Internshala (fresher jobs + internships) | listing pages | exact |
| Indeed India, Glassdoor India | python-jobspy | date |
| LinkedIn (internship + entry level) | public guest pages | approx. |

## What gets hidden

- **Not a developer job:** sales, support, HR, teaching, data entry, other engineering branches and similar.
- **Senior roles:** Senior, Lead, Staff, Architect, SDE-2 and above, and anything asking for **2+ years**. Postings asking 0–2 or 1–3 years are kept.
- **Outside India.**
- **Asks the candidate for money:** registration or training fees, deposits, "100% placement" courses.

Warnings are tagged but not hidden: **service bonds** ("Bond: 2 years") and **consultancies**.
The rules are in `config.py` and `pipeline/filters.py`, and the tests are in `tests/test_filters.py`.

## Running it

```
pip install -r requirements.txt
python -m pytest -q tests/test_filters.py
python run_scrape.py --dry-run --only naukri        # collect + filter, print, write nothing
python run_scrape.py --mode quick                   # needs SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
node dev_server.js                                  # site + API on http://localhost:4321
```

## How it runs

- **Database:** Supabase, schema `jobfinder_in` (`supabase/schema.sql`). RLS is on with no policies, so only the server-side service key can read or write.
- **Scraper:** GitHub Actions (`.github/workflows/scrape.yml`).
- **Timer:** Supabase `pg_cron` calls `/api/tick` at :22 and :52, which starts the workflow (`supabase/002_timer.sql`). The nightly full sweep runs at 2:17 AM IST.
- **Website:** Vercel. Static `site/`, plus `api/*.js`.

Vercel environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `APP_PIN`, `CRON_SECRET`,
`GITHUB_TOKEN` (fine-grained, Actions: write on this repo), `GITHUB_REPO`.
