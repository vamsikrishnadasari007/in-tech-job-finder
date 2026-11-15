"""Pull recruiter emails, phone numbers and an office address out of a job description."""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Indian mobiles: +91 98765 43210 / 098765-43210 / 9876543210
_PHONE = re.compile(r"(?<![\d])(?:\+91[\s-]?|91[\s-]|0)?[6-9]\d{4}[\s-]?\d{5}(?![\d])")
_ADDRESS_LINE = re.compile(
    r"(?:office\s*address|company\s*address|work\s*(?:location|address)|address|venue|"
    r"location\s*of\s*work|located\s*at|walk[\s-]*in\s*(?:venue|address))\s*[:\-–]\s*(.{8,160})",
    re.I,
)
_NOT_RECRUITER = ("noreply", "no-reply", "example.com", "sentry", "wixpress")


def emails(text: str) -> list[str]:
    seen = []
    for e in _EMAIL.findall(text or ""):
        e = e.strip(".").lower()
        if e not in seen and not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) and not any(x in e for x in _NOT_RECRUITER):
            seen.append(e)
    return seen


def phones(text: str) -> list[str]:
    seen = []
    for p in _PHONE.findall(text or ""):
        p = re.sub(r"\s+", " ", p.strip())
        if p not in seen:
            seen.append(p)
    return seen


def address(text: str) -> str:
    m = _ADDRESS_LINE.search(text or "")
    if not m:
        return ""
    return m.group(1).split("\n")[0].strip(" .;")
