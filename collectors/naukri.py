"""Naukri: its JSON search API, signed the same way python-jobspy does it (an RSA 'nkparam' token).

The search itself filters by experience (experience=1 → postings open to someone with 1 year,
which covers 0–1, 0–2, 1–3 …) and gives exact post times, min/max experience, salary and skills.
The full description is opened only for new postings that pass the cheap pre-filter.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone

import config
from pipeline.filters import prefilter_reason
from pipeline.model import Job, html_to_text, lpa

BASE = "https://www.naukri.com"
SEARCH = f"{BASE}/jobapi/v3/search"
DETAIL = f"{BASE}/jobapi/v4/job/{{id}}"
IST = timezone(timedelta(hours=5, minutes=30))
MAX_DETAILS = 80          # per run; the rest are opened next run


class Blocked(Exception):
    pass


def _session():
    from jobspy.model import ScraperInput, Site
    from jobspy.util import TLSRotating, create_session
    return create_session(TLSRotating(None), ScraperInput(site_type=[Site.NAUKRI]))


def _token(page: str) -> str:
    from jobspy.naukri.util import generate_nkparam
    return generate_nkparam(page)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _salary(row: dict, label: str) -> str:
    s = row.get("salaryDetail") or {}
    if s and not s.get("hideSalary") and (s.get("minimumSalary") or s.get("maximumSalary")):
        return lpa(_num(s.get("minimumSalary")), _num(s.get("maximumSalary")), "year")
    label = (label or "").strip()
    if not label or "not disclosed" in label.lower():
        return ""
    return label.replace("Lacs PA", "LPA").replace("Lacs P.A.", "LPA")


def _parse(row: dict, internship: bool) -> Job | None:
    labels = {p.get("type"): p.get("label", "") for p in row.get("placeholders") or []}
    loc = labels.get("location", "")
    mode, _, city = loc.rpartition(" - ")
    work_mode = {"hybrid": "Hybrid", "remote": "Remote", "work from office": "Office"}.get(mode.strip().lower(), "")
    if city.strip().lower() == "remote":
        work_mode = "Remote"
    created = row.get("createdDate")
    posted = datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else ""
    jid = str(row.get("jobId") or "")
    if not jid or not row.get("title"):
        return None
    return Job(
        platform="Naukri", platform_id=jid, title=row["title"].strip(), company=(row.get("companyName") or "").strip(),
        url=BASE + (row.get("jdURL") or f"/job-listings-{jid}"), location=city.strip() or loc, posted_at=posted,
        salary=_salary(row, labels.get("salary", "")), work_mode=work_mode,
        work_type="Internship" if internship else "",
        description=html_to_text(row.get("jobDescription") or ""),
        company_url=f"{BASE}/{row['staticUrl']}" if row.get("staticUrl") else "",
        skills=[s.strip() for s in (row.get("tagsAndSkills") or "").split(",") if s.strip()],
        exp_min=_num(row.get("minimumExperience")), exp_max=_num(row.get("maximumExperience")),
        is_internship=internship,
    )


def _search(s, kw: str, page: int, age_days: int, internship: bool) -> tuple[list[dict], int]:
    params = {"noOfResults": 20, "urlType": "search_by_keyword", "searchType": "adv", "keyword": kw,
              "pageNo": page, "jobAge": age_days, "sort": "f"}
    if internship:
        params |= {"qproductJobSource": "2", "qinternshipFlag": "true"}
    else:
        params["experience"] = 1
    r = s.get(SEARCH, params=params, headers={"appid": "109", "systemid": "Naukri", "nkparam": _token("srp")})
    if r.status_code == 406:
        raise Blocked("Naukri asked for a captcha (406)")
    if r.status_code == 400 and page > 1:
        return [], 0
    if r.status_code != 200:
        raise RuntimeError(f"Naukri search {r.status_code}")
    js = r.json()
    return js.get("jobDetails") or [], int(js.get("noOfJobs") or 0)


def _detail(s, job: Job) -> None:
    r = s.get(DETAIL.format(id=job.platform_id),
              headers={"appid": "121", "systemid": "Naukri", "nkparam": _token(job.platform_id)})
    if r.status_code == 406:
        raise Blocked("rate limited on job pages")
    if r.status_code != 200:
        return
    d = (r.json() or {}).get("jobDetails") or {}
    job.description = html_to_text(d.get("description") or "") or job.description
    created = d.get("createdDate")
    if created:
        try:
            job.posted_at = datetime.strptime(created, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST).astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    if d.get("jobType") == "internship":
        job.is_internship = True
    if d.get("employmentType") and not job.work_type:
        job.work_type = d["employmentType"]
    co = d.get("companyDetail") or {}
    if isinstance(co, dict):
        job.address = (co.get("address") or "").strip() or job.address
        job.company_url = co.get("websiteUrl") or job.company_url
    if d.get("consultant"):
        job.flags = ["Via consultancy"]
    skills = [k.get("label") for k in (d.get("keySkills") or {}).get("other", []) + (d.get("keySkills") or {}).get("preferred", [])
              if isinstance(k, dict) and k.get("label")] if isinstance(d.get("keySkills"), dict) else []
    if skills:
        job.skills = skills


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    known = known or {}
    s = _session()
    age = 1 if mode == "quick" else config.DAYS_BACK
    pages = 2 if mode == "quick" else 5
    found: dict[str, Job] = {}
    blocked = ""
    searches = [(kw, False) for kw in config.SEARCH_KEYWORDS] + [(kw, True) for kw in config.INTERNSHIP_KEYWORDS]
    done = 0
    for kw, internship in searches:
        try:
            for page in range(1, pages + 1):
                rows, total = _search(s, kw, page, age, internship)
                batch = [j for j in (_parse(r, internship) for r in rows) if j]
                for j in batch:
                    found.setdefault(j.platform_id, j)
                if len(rows) < 20 or page * 20 >= total or all(j.platform_id in known for j in batch):
                    break
                time.sleep(random.uniform(1.5, 3.0))
            done += 1
        except Blocked as e:
            blocked = str(e)
            break
        except Exception as e:
            log(f"  Naukri '{kw}' failed: {e}")
        time.sleep(random.uniform(1.0, 2.0))
    if not found and blocked:
        raise RuntimeError(blocked)
    if done == 0:
        raise RuntimeError("every Naukri search failed")

    jobs = list(found.values())
    need = [j for j in jobs if not prefilter_reason(j) and not (known.get(j.platform_id) or {}).get("has_description")]
    log(f"  Naukri: {len(jobs)} postings, {len(need)} new & worth opening{' (stopped early: ' + blocked + ')' if blocked else ''}")
    for j in need[:MAX_DETAILS]:
        try:
            _detail(s, j)
        except Blocked:
            log("  Naukri: rate-limited while opening jobs; the rest will be opened next run")
            break
        except Exception:
            pass
        time.sleep(random.uniform(0.8, 1.6))
    return jobs
