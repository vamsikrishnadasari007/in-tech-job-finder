"""Company career boards (Greenhouse, Lever, Ashby): official listings with exact post times.

Each board is one request that returns every open job of that company worldwide; we keep only
the ones located in India (or remote in India), in a developer role, and posted recently.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import config
from collectors.http import client
from pipeline.filters import areas_of, match_roles
from pipeline.model import Job, html_to_text

_INDIA = re.compile(r"\bindia\b|\bIN\b")


def _in_india(loc: str) -> bool:
    return bool(areas_of(loc) and [a for a in areas_of(loc) if a != "Remote"]) or bool(_INDIA.search(loc or ""))


def _greenhouse(c, slug: str) -> list[Job]:
    r = c.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        offices = ", ".join(o.get("location") or o.get("name") or "" for o in j.get("offices") or [])
        place = loc if _in_india(loc) else offices
        if not _in_india(place):
            continue
        out.append(Job(
            platform="Company site", platform_id=f"gh:{slug}:{j['id']}", title=j.get("title", "").strip(),
            company=j.get("company_name") or slug, url=j.get("absolute_url", ""), location=place,
            posted_at=j.get("first_published") or j.get("updated_at") or "",
            description=html_to_text(_unescape(j.get("content") or "")),
        ))
    return out


def _unescape(s: str) -> str:
    import html
    return html.unescape(s)


def _lever(c, slug: str) -> list[Job]:
    r = c.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    r.raise_for_status()
    out = []
    for j in r.json():
        cat = j.get("categories") or {}
        place = ", ".join(cat.get("allLocations") or [cat.get("location") or ""])
        if not (_in_india(place) or j.get("country") == "IN"):
            continue
        commit = (cat.get("commitment") or "")
        created = j.get("createdAt")
        out.append(Job(
            platform="Company site", platform_id=f"lv:{slug}:{j['id']}", title=(j.get("text") or "").strip(),
            company=slug.capitalize(), url=j.get("hostedUrl", ""), location=place or "India",
            posted_at=datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else "",
            work_type="Internship" if "intern" in commit.lower() else commit.title(),
            work_mode={"remote": "Remote", "hybrid": "Hybrid", "onsite": "Office"}.get((j.get("workplaceType") or "").lower(), ""),
            description="\n".join(filter(None, [j.get("descriptionPlain"), *[f"{l.get('text')}\n{html_to_text(l.get('content', ''))}" for l in j.get("lists") or []], j.get("additionalPlain")])),
        ))
    return out


def _ashby(c, slug: str) -> list[Job]:
    r = c.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        places = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        addr = json.dumps(j.get("address") or {})
        india = [p for p in places if _in_india(p)]
        if not india and "India" not in addr:
            continue
        et = j.get("employmentType") or ""
        out.append(Job(
            platform="Company site", platform_id=f"ab:{slug}:{j['id']}", title=(j.get("title") or "").strip(),
            company=slug.capitalize(), url=j.get("jobUrl", ""), location=", ".join(india) or "India",
            posted_at=j.get("publishedAt") or "",
            work_type="Internship" if et == "Intern" else {"FullTime": "Full time", "Contract": "Contract"}.get(et, et),
            work_mode="Remote" if j.get("isRemote") else {"Hybrid": "Hybrid", "OnSite": "Office"}.get(j.get("workplaceType") or "", ""),
            description=j.get("descriptionPlain") or "",
        ))
    return out


ATS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby}


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    c = client(Accept="application/json")
    cutoff = datetime.now(timezone.utc).timestamp() - config.KEEP_DAYS * 86400
    tasks = [(ats, slug) for ats, slugs in config.BOARDS.items() for slug in slugs]

    def one(t):
        ats, slug = t
        try:
            return ATS[ats](c, slug), ""
        except Exception as e:
            return [], f"{ats}/{slug}: {str(e)[:80]}"

    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(one, tasks))
    errors = [e for _, e in results if e]
    jobs = []
    for batch, _ in results:
        for j in batch:
            try:
                ts = datetime.fromisoformat(j.posted_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
            if ts >= cutoff and match_roles(j.title):
                j.posted_at = datetime.fromtimestamp(ts, timezone.utc).isoformat()
                jobs.append(j)
    if errors:
        log(f"  Company sites: {len(errors)} board(s) failed: {'; '.join(errors[:5])}")
    if len(errors) == len(tasks):
        raise RuntimeError("every company board failed")
    log(f"  Company sites: {len(tasks) - len(errors)} boards, {len(jobs)} recent India developer jobs")
    return jobs
