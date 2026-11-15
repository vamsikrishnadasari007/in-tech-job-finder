"""The key that says two postings are the same job (same company + same title), whatever the site."""
from __future__ import annotations

import re

from pipeline.model import Job

# Order of preference for which copy becomes the main card (official / richest data first).
PLATFORM_RANK = {"Company site": 0, "Naukri": 1, "foundit": 2, "Instahyre": 3, "Internshala": 4,
                 "Indeed": 5, "Glassdoor": 6, "LinkedIn": 7}

_CO_NOISE = re.compile(
    r"\b(pvt|private|ltd|limited|llp|inc|incorporated|corp|corporation|co|company|india|technologies|technology|"
    r"tech|solutions|services|software|systems|labs|global|infotech|it|and|the|group)\b|[^a-z0-9 ]",
    re.I,
)
_TITLE_NOISE = re.compile(
    r"\(.*?\)|\[.*?\]|[^a-z0-9+# ]|\b(urgent|urgently|hiring|hire|needed|wanted|immediate|immediately|joiners?|"
    r"opening|openings|vacancy|vacancies|job|for|freshers?|fresher|wfh|remote|hybrid|onsite|on site)\b",
    re.I,
)


def _norm(s: str, noise: re.Pattern) -> str:
    return " ".join(noise.sub(" ", (s or "").lower()).split())


def dedupe_key(j: Job) -> str:
    return f"{_norm(j.company, _CO_NOISE)}|{_norm(j.title, _TITLE_NOISE)}"
