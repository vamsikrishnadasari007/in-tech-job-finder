"""Internshala: fresher jobs and internships (entry level by design). Parsed from the listing pages.

Each listing link ends in the posting's Unix time (…-limited1793876592), so post times are exact.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from selectolax.lexbor import LexborHTMLParser as HTMLParser

import config
from collectors.http import client, get
from pipeline.filters import prefilter_reason
from pipeline.model import Job, html_to_text

BASE = "https://internshala.com"
CATEGORIES = [
    "software-development", "web-development", "computer-science", "data-science", "machine-learning",
    "artificial-intelligence-ai", "full-stack-development", "backend-development", "frontend-development",
    "python-django", "mobile-app-development", "android-app-development", "javascript-development",
    "node-js-development", "cloud-computing", "data-analytics", "software-testing",
]
MAX_DETAILS = 60
_TS = re.compile(r"(\d{10})$")
_MONEY = re.compile(r"[\d,]+")
_EXP = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*year|(\d+(?:\.\d+)?)\+?\s*year", re.I)


def _salary(text: str) -> str:
    t = " ".join((text or "").split())
    if not t or "unpaid" in t.lower():
        return "Unpaid" if "unpaid" in t.lower() else ""
    nums = [int(n.replace(",", "")) for n in _MONEY.findall(t) if n.replace(",", "").isdigit()]
    if not nums:
        return t
    lo, hi = nums[0], nums[-1]
    if "/month" in t or "month" in t.lower():
        return f"₹{lo:,}" + (f"–{hi:,}" if hi != lo else "") + " / month"
    if lo >= 10000:
        a, b = round(lo / 1e5, 1), round(hi / 1e5, 1)
        return f"₹{a:g}" + (f"–{b:g}" if b != a else "") + " LPA"
    return t


def _parse(card, kind: str) -> Job | None:
    iid = card.attributes.get("internshipid") or ""
    kind = "internship" if card.attributes.get("employment_type") == "internship" else kind
    href = card.attributes.get("data-href") or ""
    t = card.css_first("a.job-title-href")
    if not (iid and href and t):
        return None
    m = _TS.search(href)
    posted = datetime.fromtimestamp(int(m.group(1)), timezone.utc).isoformat() if m else ""
    co = card.css_first("p.company-name")
    locs = [a.text(strip=True) for a in card.css(".locations a")] or \
           [s.text(strip=True) for s in card.css(".locations span")]
    sal_node = card.css_first("span.stipend") or card.css_first("span.mobile") or card.css_first("span.desktop")
    exp_text = ""
    for item in card.css(".row-1-item"):
        if item.css_first("i.ic-16-briefcase"):
            exp_text = item.text(strip=True)
    exp_min = exp_max = None
    if kind == "job":
        if "no experience" in exp_text.lower():
            exp_min, exp_max = 0.0, 0.0
        else:
            em = _EXP.search(exp_text)
            if em:
                exp_min = float(em.group(1) or em.group(3))
                exp_max = float(em.group(2)) if em.group(2) else None
    about = card.css_first(".about_job .text")
    location = ", ".join(locs)
    return Job(
        platform="Internshala", platform_id=iid, title=t.text(strip=True),
        company=co.text(strip=True) if co else "", url=BASE + href, location=location, posted_at=posted,
        salary=_salary(sal_node.text() if sal_node else ""),
        work_type="Internship" if kind == "internship" else "Full time",
        work_mode="Remote" if "work from home" in location.lower() else "",
        description=about.text(strip=True) if about else "",
        skills=[s.text(strip=True) for s in card.css(".job_skill")],
        exp_min=exp_min, exp_max=exp_max, is_internship=kind == "internship",
    )


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    known = known or {}
    c = client()
    pages = 1 if mode == "quick" else 3
    cutoff = datetime.now(timezone.utc).timestamp() - config.DAYS_BACK * 86400
    found: dict[str, Job] = {}
    failures = total = 0
    for cat in CATEGORIES:
        for kind, path in (("job", f"/fresher-jobs/{cat}-jobs/"), ("internship", f"/internships/{cat}-internship/")):
            for page in range(1, pages + 1):
                total += 1
                try:
                    r = get(c, BASE + path + (f"page-{page}/" if page > 1 else ""))
                except Exception as e:
                    failures += 1
                    log(f"  Internshala {path} failed: {e}")
                    break
                batch = [j for j in (_parse(x, kind) for x in HTMLParser(r.text).css("div.individual_internship")) if j]
                for j in batch:
                    found.setdefault(j.platform_id, j)
                old = all(j.posted_at and datetime.fromisoformat(j.posted_at).timestamp() < cutoff for j in batch)
                if len(batch) < 20 or old or all(j.platform_id in known for j in batch):
                    break
    if total and failures == total:
        raise RuntimeError("every Internshala page failed")

    jobs = list(found.values())
    need = [j for j in jobs if not prefilter_reason(j) and not (known.get(j.platform_id) or {}).get("has_description")]
    log(f"  Internshala: {len(jobs)} postings, {len(need)} new & worth opening")
    for j in need[:MAX_DETAILS]:
        try:
            tree = HTMLParser(get(c, j.url).text)
        except Exception:
            continue
        node = tree.css_first("div.internship_details") or tree.css_first("div.text-container")
        if node:
            j.description = html_to_text(node.html)
    return jobs
