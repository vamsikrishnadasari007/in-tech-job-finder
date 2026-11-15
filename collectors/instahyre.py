"""Instahyre: product companies and startups. Its search API filtered to candidates with 0 years.

Instahyre does not publish post dates, so these jobs are dated by when we first saw them
(shown on the site as "first seen …").
"""
from __future__ import annotations

from datetime import datetime, timezone

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from collectors.http import RateLimited, client, get
from pipeline.filters import prefilter_reason
from pipeline.model import Job, html_to_text

SEARCH = "https://www.instahyre.com/api/v1/job_search"
PAGE = 35
MAX_DETAILS = 60


def _parse(x: dict, now: str) -> Job | None:
    if not x.get("id") or not x.get("title"):
        return None
    emp = x.get("employer") or {}
    return Job(
        platform="Instahyre", platform_id=str(x["id"]), title=x["title"].strip(),
        company=(emp.get("company_name") or "").strip(), url=x.get("public_url") or "",
        location=x.get("locations") or "", posted_at=now, posted_precision="seen",
        skills=[k for k in (x.get("keywords") or []) if isinstance(k, str)][:12], exp_min=0.0,
    )


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    known = known or {}
    c = client(Accept="application/json")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    pages = 4 if mode == "quick" else 40
    found: dict[str, Job] = {}
    for page in range(pages):
        try:
            r = get(c, SEARCH, params=dict(years=0, offset=page * PAGE, limit=PAGE), pause=(2.0, 4.0))
        except RateLimited:
            if not found:
                raise
            log(f"  Instahyre: rate-limited after {page} pages; keeping what we have")
            break
        rows = r.json().get("objects") or []
        batch = [j for j in (_parse(x, now) for x in rows) if j]
        for j in batch:
            found.setdefault(j.platform_id, j)
        if len(rows) < PAGE or (mode == "quick" and all(j.platform_id in known for j in batch)):
            break
    jobs = list(found.values())
    # Already stored: keep the first-seen date we gave it the first time.
    for j in jobs:
        k = known.get(j.platform_id)
        if k and k.get("first_seen"):
            j.posted_at = k["first_seen"]
    need = [j for j in jobs if not prefilter_reason(j) and not (known.get(j.platform_id) or {}).get("has_description")]
    log(f"  Instahyre: {len(jobs)} postings, {len(need)} new & worth opening")
    for j in need[:MAX_DETAILS]:
        try:
            tree = HTMLParser(get(c, j.url, pause=(1.5, 3.0)).text)
        except RateLimited:
            break
        except Exception:
            continue
        node = tree.css_first("div.job-description, #job-description, div.description, section.job-details")
        if node is None:
            meta = tree.css_first('meta[name="description"]')
            j.description = meta.attributes.get("content", "") if meta else ""
        else:
            j.description = html_to_text(node.html)
    return jobs
