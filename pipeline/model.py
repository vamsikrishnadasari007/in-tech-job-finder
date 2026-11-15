"""The one job format every collector produces."""
from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field


@dataclass
class Job:
    platform: str                 # "Naukri", "LinkedIn", "Company site", ...
    platform_id: str              # id on that platform
    title: str
    company: str
    url: str
    location: str = ""
    posted_at: str = ""           # ISO-8601 UTC
    posted_precision: str = "exact"   # "exact" | "hour" (from "5 hours ago") | "date" | "seen" (no date: first seen)
    salary: str = ""              # already formatted, e.g. "₹4–6 LPA"
    work_type: str = ""           # Full time / Internship / Contract ...
    work_mode: str = ""           # Office / Hybrid / Remote / ""
    description: str = ""         # plain text
    address: str = ""
    company_url: str = ""
    skills: list[str] = field(default_factory=list)
    exp_min: float | None = None  # structured experience from the site (years), when it gives one
    exp_max: float | None = None
    is_internship: bool = False
    # filled in by the pipeline
    roles: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)   # Bengaluru / Hyderabad / Remote / ...
    experience: str = ""          # "Freshers welcome" / "1 year asked" / "Internship" / "Needs 3+ years" ...
    exp_range: str = ""           # "0–2 yrs" when known
    flags: list[str] = field(default_factory=list)   # "Bond: 2 years", "Via consultancy"
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    hidden_reason: str = ""       # "" = shown; otherwise why it is hidden
    first_seen: str = ""

    def to_dict(self):
        return asdict(self)


_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(p|div|br|li|ul|ol|h\d|tr)[^>]*>", re.I)


def html_to_text(s: str) -> str:
    """Rough HTML → readable plain text (keeps line breaks between blocks/bullets)."""
    if not s:
        return ""
    s = _BLOCK.sub("\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def lpa(lo: float | None, hi: float | None, per: str = "year") -> str:
    """Rupee amounts → '₹4–6 LPA' (yearly) or '₹15,000–20,000 / month'."""
    lo = lo or None
    hi = hi or None
    if not lo and not hi:
        return ""
    per = (per or "year").lower()
    if per.startswith("month"):
        a, b = lo or hi, hi or lo
        rng = f"₹{a:,.0f}" if a == b else f"₹{a:,.0f}–{b:,.0f}"
        return f"{rng} / month"
    if per.startswith("hour"):
        return ""
    def l(x):
        v = round(x / 100000, 1)
        return f"{v:g}"
    a, b = lo or hi, hi or lo
    if a < 10000:          # already in lakhs ("4.5")
        a, b = a * 100000, b * 100000
    return f"₹{l(a)} LPA" if l(a) == l(b) else f"₹{l(a)}–{l(b)} LPA"
