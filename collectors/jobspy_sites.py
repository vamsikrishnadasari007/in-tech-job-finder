"""Indeed India and Glassdoor India, via the python-jobspy library (descriptions come with the results)."""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone

import config
from pipeline.filters import match_roles
from pipeline.model import Job, lpa

GLASSDOOR_CITIES = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Gurgaon", "Noida", "Mumbai"]
GLASSDOOR_KEYWORDS = ["software engineer", "software developer", "ai engineer", "data engineer"]


def _s(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return str(v).strip()


def _n(v):
    try:
        v = float(v)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def _salary(row) -> str:
    cur = _s(row.get("currency")) or "INR"
    if cur != "INR":
        return ""
    per = _s(row.get("interval")) or "yearly"
    return lpa(_n(row.get("min_amount")), _n(row.get("max_amount")), "month" if per.startswith("month") else per)


def _jobs(df, platform: str) -> list[Job]:
    out = []
    for row in df.to_dict("records"):
        posted = row.get("date_posted")
        posted = datetime(posted.year, posted.month, posted.day, tzinfo=timezone.utc).isoformat() if hasattr(posted, "year") else ""
        jt = _s(row.get("job_type"))
        out.append(Job(
            platform=platform, platform_id=_s(row.get("id")), title=_s(row.get("title")),
            company=_s(row.get("company")), url=_s(row.get("job_url")), location=_s(row.get("location")),
            posted_at=posted, posted_precision="date", salary=_salary(row),
            work_type="Internship" if "intern" in jt.lower() else jt.replace("fulltime", "Full time"),
            work_mode="Remote" if row.get("is_remote") is True else "",
            description=_s(row.get("description")), address=_s(row.get("company_addresses")),
            company_url=_s(row.get("company_url_direct")),
        ))
    return out


def _run(platform: str, searches: list[dict], hours: int, wanted: int, log) -> list[Job]:
    from jobspy import scrape_jobs
    jobs, failures = [], 0
    for q in searches:
        try:
            df = scrape_jobs(results_wanted=wanted, hours_old=hours, country_indeed="india",
                             description_format="markdown", verbose=0, **q)
        except Exception as e:
            log(f"  {platform} {q.get('search_term')!r} failed: {str(e)[:120]}")
            failures += 1
            continue
        jobs += _jobs(df, platform)
        time.sleep(2)
    if failures == len(searches):
        raise RuntimeError(f"every {platform} search failed (probably blocked)")
    jobs = [j for j in jobs if j.platform_id and match_roles(j.title)]
    log(f"  {platform}: {len(jobs)} postings match the roles")
    return jobs


class indeed:  # noqa: N801 (module-like namespace used by run_scrape)
    @staticmethod
    def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
        hours = 3 if mode == "quick" else config.DAYS_BACK * 24          # quick runs are hourly
        wanted = 30 if mode == "quick" else 100
        searches = [dict(site_name=["indeed"], search_term=kw, location="India") for kw in config.SEARCH_KEYWORDS_LIGHT]
        return _run("Indeed", searches, hours, wanted, log)


class glassdoor:  # noqa: N801
    @staticmethod
    def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
        hours = 24 if mode == "quick" else config.DAYS_BACK * 24          # Glassdoor only knows days
        wanted = 20 if mode == "quick" else 60
        searches = [dict(site_name=["glassdoor"], search_term=kw, location=city)
                    for kw in GLASSDOOR_KEYWORDS for city in GLASSDOOR_CITIES]
        return _run("Glassdoor", searches, hours, wanted, log)
