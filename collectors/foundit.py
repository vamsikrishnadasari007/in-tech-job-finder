"""foundit (formerly Monster India): JSON search API filtered to 0–1 years, exact post times."""
from __future__ import annotations

from datetime import datetime, timezone

import config
from collectors.http import client, get
from pipeline.filters import prefilter_reason
from pipeline.model import Job, html_to_text, lpa

BASE = "https://www.foundit.in"
SEARCH = f"{BASE}/middleware/jobsearch"
DETAIL = f"{BASE}/middleware/jobdetail/{{id}}"
MAX_DETAILS = 80


def _years(v):
    return (v or {}).get("years") if isinstance(v, dict) else None


def _parse(x: dict) -> Job | None:
    if not x.get("title") or not x.get("id"):
        return None                                      # ad / promo rows
    lo, hi = _years(x.get("minimumExperience")), _years(x.get("maximumExperience"))
    # Jobs foundit copied from other sites carry 0/0 with no text: that means "unknown", not "fresher".
    known_exp = bool(x.get("exp")) or bool(hi)
    created = x.get("createdAt") or x.get("freshness")
    smin = (x.get("minimumSalary") or {}).get("absoluteValue") or 0
    smax = (x.get("maximumSalary") or {}).get("absoluteValue") or 0
    types = " ".join((x.get("jobTypes") or []) + (x.get("employmentTypes") or []))
    return Job(
        platform="foundit", platform_id=str(x["id"]), title=x["title"].strip(), company=(x.get("companyName") or "").strip(),
        url=BASE + (x.get("seoJdUrl") or x.get("jdUrl") or ""), location=x.get("locations") or "",
        posted_at=datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else "",
        salary="" if x.get("hideSalary") else lpa(smin, smax, "year"),
        work_type="Internship" if "intern" in types.lower() else ", ".join(x.get("employmentTypes") or []),
        work_mode="Remote" if "work from home" in types.lower() else "",
        skills=[s.strip() for s in (x.get("skills") or "").split(",") if s.strip()][:12],
        exp_min=float(lo) if known_exp and lo is not None else None,
        exp_max=float(hi) if known_exp and hi is not None else None,
        company_url=x.get("redirectUrl") or "",
    )


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    known = known or {}
    c = client(Accept="application/json", Referer=BASE + "/")
    pages = 1 if mode == "quick" else 4
    cutoff = datetime.now(timezone.utc).timestamp() - config.DAYS_BACK * 86400
    found: dict[str, Job] = {}
    failures = 0
    for kw in config.SEARCH_KEYWORDS:
        try:
            for page in range(pages):
                r = get(c, SEARCH, params=dict(sort=1, limit=50, start=page * 50, query=kw,
                                               experienceRanges="0~1", locations="India"))
                rows = (r.json().get("jobSearchResponse") or {}).get("data") or []
                batch = [j for j in (_parse(x) for x in rows) if j]
                for j in batch:
                    found.setdefault(j.platform_id, j)
                old = all(j.posted_at and datetime.fromisoformat(j.posted_at).timestamp() < cutoff for j in batch)
                if len(rows) < 40 or old or all(j.platform_id in known for j in batch):
                    break
        except Exception as e:
            failures += 1
            log(f"  foundit '{kw}' failed: {e}")
    if failures == len(config.SEARCH_KEYWORDS):
        raise RuntimeError("every foundit search failed")

    jobs = list(found.values())
    need = [j for j in jobs if not prefilter_reason(j) and not (known.get(j.platform_id) or {}).get("has_description")]
    log(f"  foundit: {len(jobs)} postings, {len(need)} new & worth opening")
    for j in need[:MAX_DETAILS]:
        try:
            d = (get(c, DETAIL.format(id=j.platform_id)).json() or {}).get("jobDetailResponse") or {}
        except Exception:
            continue
        j.description = html_to_text(d.get("description") or "")
        venue = d.get("walkInVenue") or {}
        if isinstance(venue, dict) and venue.get("address"):
            j.address = venue["address"]
        phone = str(d.get("recruiterContactNumber") or "")
        if phone and phone != "None" and d.get("showContactDetails"):
            j.description += f"\nRecruiter phone: {phone}"
    return jobs
