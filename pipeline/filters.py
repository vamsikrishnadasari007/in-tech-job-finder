"""Decide which role groups a job fits, which cities it is in, and whether it must be hidden
(senior, not a developer job, outside India, asks for money)."""
from __future__ import annotations

import re

import config
from pipeline.model import Job

_ROLE_RE = {name: [re.compile(p, re.I) for p in pats] for name, pats in config.ROLES.items()}
_INTERN = re.compile(r"\b(intern|interns|internship|summer\s*trainee)\b", re.I)


def match_roles(title: str) -> list[str]:
    roles = [name for name, pats in _ROLE_RE.items() if any(p.search(title) for p in pats)]
    # "Other developer" only when nothing more specific matched.
    if len(roles) > 1 and "Other developer" in roles:
        roles.remove("Other developer")
    return roles


# ---------------------------------------------------------------------------------------
# Experience. Kept: freshers / 0–2 years (minimum asked below 2 years) / not mentioned.
# Hidden: "2+ years", "3-5 yrs", "minimum two (2) years", ...
# ---------------------------------------------------------------------------------------
_NUM_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen".split())}
_NUM_WORD_RE = re.compile(r"\b(" + "|".join(_NUM_WORDS) + r")\b", re.I)
_DASHES = re.compile(r"[‐‑‒–—―−~�]")
_EXP_WORD = re.compile(r"\b(exp[ei]r\w{0,3}n[cs]e[sd]?|experienced|exp\.?|worked|working\s+in|track\s+record|yoe)\b", re.I)
_NOT_EXP = re.compile(r"\b(years?\s*old|of\s*age|age\s*\d|warranty|in\s*business|in\s*the\s*industry\s*for|"
                      r"established|founded|serving|company\s*with|since\s*\d{4}|"
                      r"(we|our\s*(company|firm|team|group)|the\s*company|company)\s*(has|have|brings?)|"
                      r"backed\s*by|over\s*the\s*(past|last)|bond|service\s*agreement|duration|stipend)\b", re.I)
_UNIT = r"(years?|yrs?\.?|y\.?o\.?e|months?|mos?\.?)"
_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*\+?\s*['’]?\s*" + _UNIT, re.I)
_SINGLE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*-?\s*['’]?\s*" + _UNIT, re.I)
# Strong: the ad itself invites freshers.
FRESH_OK = re.compile(
    r"\b(fresh(ers?)?\s*(graduates?|grads?)|freshers?|new\s*(graduates?|grads?)|recent\s*graduates?|entry[\s-]*level|"
    r"early[\s-]*career|campus\s*(hire|hiring|drive|recruitment)|university\s*(graduates?|grads?|hire)|"
    r"20(2[4-7])\s*(batch|pass[\s-]*outs?|graduates?|grads?)|(batch|passing\s*out|pass[\s-]*out)\s*(of\s*)?20(2[4-7])|"
    r"graduate\s*engineer\s*trainee|no\s*(work\s*|prior\s*)?experience\s*(is\s*)?(required|needed|necessary)|"
    r"without\s*(work\s*)?experience|with\s*or\s*without\s*(work\s*)?experience|experience\s*is\s*not\s*(required|necessary)|"
    r"open\s*to\s*(fresh|new)|trainee)\b",
    re.I,
)
NO_FRESHERS = re.compile(r"\b((not|no)\s*(for\s*|open\s*to\s*)?freshers?|freshers?\s*(need\s*not|cannot|can'?t|please\s*don'?t|not))\b", re.I)
EXP_OPTIONAL = re.compile(
    r"\bexperience\s*(is|would\s*be)\s*(optional|a\s*plus|an\s*advantage|advantageous|preferred\s*but\s*not\s*required)\b",
    re.I,
)
SOME_EXP = re.compile(
    r"(\b(proven|solid|extensive|progressive|substantial|strong|relevant|related|must\s*have|should\s*have|"
    r"preferably\s*with|minimum|at\s*least|hands[\s-]*on\s*professional)\b[^\n.]{0,30}\bexp[ei]r\w*n[cs]e\b"
    r"|^\W*experienced?\s+(in|with|as)\b)",
    re.I | re.M,
)


def _normalize(text: str) -> str:
    t = _DASHES.sub("-", (text or "").replace("**", "").replace("__", ""))
    t = _NUM_WORD_RE.sub(lambda m: _NUM_WORDS[m.group(1).lower()], t)
    t = re.sub(r"(\d+)\s*\(\s*\1\s*\)", r"\1", t)          # "two (2) years" → "2 years"
    return t


def required_years(text: str) -> list[tuple[float, float | None]]:
    """(min, max) years asked in each experience statement of the ad."""
    out = []
    for line in re.split(r"[\n;•|]|\.(?=\s|$)", _normalize(text)):
        if not _EXP_WORD.search(line) or _NOT_EXP.search(line):
            continue
        found = []
        for m in _RANGE.finditer(line):
            div = 12 if m.group(3).lower().startswith("m") else 1
            found.append((float(m.group(1)) / div, float(m.group(2)) / div))
        if not found:
            for m in _SINGLE.finditer(line):
                div = 12 if m.group(2).lower().startswith("m") else 1
                found.append((float(m.group(1)) / div, None))
        found = [f for f in found if 0 <= f[0] <= 15]
        if found:
            out.append(min(found, key=lambda f: f[0]))
    return out


def _range_text(lo: float, hi: float | None) -> str:
    def y(v):
        m = round(v * 12)
        return (f"{m} month" + ("s" if m != 1 else "")) if 0 < v < 1 else f"{v:g} yrs"
    if hi is not None and hi > lo:
        return f"{lo:g}–{y(hi)}" if lo >= 1 or lo == 0 and hi >= 1 else f"{y(lo)}–{y(hi)}"
    return f"{y(lo)}+" if lo else ""


def _label(need: float) -> tuple[str, bool]:
    if need <= 0:
        return "Freshers welcome", False
    if need < 1:
        return "Less than 1 year", False
    if need < config.MAX_EXPERIENCE_YEARS:
        return "1 year asked", False
    return f"Needs {need:g}+ years", True


def experience_info(job: Job) -> tuple[str, str, bool]:
    """→ (label shown on the card, range text, too_much). too_much=True means hide the job."""
    if job.is_internship:
        return "Internship", "", False
    if job.exp_min is not None:                       # the site says it (Naukri, foundit, Internshala)
        label, too_much = _label(job.exp_min)
        return label, _range_text(job.exp_min, job.exp_max), too_much
    # "Java Developer (3-6 years)": years in the title always mean experience.
    title_years = [(float(m.group(1)), float(m.group(2))) for m in _RANGE.finditer(_normalize(job.title))
                   if not m.group(3).lower().startswith("m")]
    if title_years:
        lo, hi = title_years[0]
        label, too_much = _label(lo)
        return label, _range_text(lo, hi), too_much
    text = f"{job.title}\n{job.description}"
    if FRESH_OK.search(text) and not NO_FRESHERS.search(text):
        return "Freshers welcome", "", False
    years = required_years(text)
    if not years:
        if EXP_OPTIONAL.search(job.description or ""):
            return "Freshers welcome", "", False
        if SOME_EXP.search(job.description or ""):
            return "Some experience preferred", "", False
        return "Experience not mentioned", "", False
    lo, hi = min(years, key=lambda y: y[0])            # several positions in one ad → the easiest counts
    label, too_much = _label(lo)
    return label, _range_text(lo, hi), too_much


# ---------------------------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------------------------
_AREA_RE = {a: re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)
            for a, words in config.AREAS.items()}


def areas_of(text: str) -> list[str]:
    found = [a for a, rx in _AREA_RE.items() if rx.search(text or "")]
    if len(found) > 1 and "Other India" in found:
        found.remove("Other India")        # "Bengaluru, India" → just Bengaluru
    return found


def is_foreign(location: str) -> bool:
    return not areas_of(location) and bool(config.FOREIGN.search(location or ""))


_REMOTE = re.compile(r"\b(remote|work\s*from\s*home|wfh|work\s*from\s*anywhere)\b", re.I)
_REMOTE_DESC = re.compile(r"\b(fully\s*remote|100\s*%\s*remote|remote[\s-]*first|work\s*from\s*home|wfh|remote\s*(role|position|job|opportunity))\b", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)


def work_mode_of(job: Job) -> str:
    if job.work_mode:
        return job.work_mode
    head = f"{job.title} {job.location}"
    if _HYBRID.search(head):
        return "Hybrid"
    if _REMOTE.search(head):
        return "Remote"
    if _REMOTE_DESC.search(job.description or ""):
        return "Remote"
    if _HYBRID.search(job.description or ""):
        return "Hybrid"
    return ""


# ---------------------------------------------------------------------------------------
# Traps: fees, bonds, consultancies
# ---------------------------------------------------------------------------------------
_NEGATION = re.compile(r"\b(never|not|no|neither|nor|don'?t|won'?t|doesn'?t|zero|nil|free\s*of|beware|fraud|scam|fake)\b", re.I)


def asks_for_money(text: str) -> bool:
    """True when the ad itself asks the candidate to pay. Sentences that deny or warn about fees
    ("we never ask you to pay fees", "beware of fake offers asking for money") don't count."""
    for sentence in re.split(r"[\n!?;]|\.(?=\s+[A-Z])", config.NO_FEE.sub(" ", text or "")):
        if config.SCAM.search(sentence) and not _NEGATION.search(sentence):
            return True
    return False


def bond_flag(text: str) -> str:
    t = config.NO_BOND.sub(" ", _normalize(text or ""))
    m = config.BOND_YEARS.search(t)
    if m:
        n, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        unit = "months" if unit.lower().startswith("m") else ("year" if float(n) == 1 else "years")
        return f"Bond: {float(n):g} {unit}"
    return "Service bond" if config.BOND_ANY.search(t) else ""


def is_consultancy(company: str) -> bool:
    return bool(config.CONSULTANCY.search(company or "")) and not config.CONSULTANCY_OK.search(company or "")


_SKILL_RE = [(s, re.compile(r"(?<![\w.+#])" + re.escape(s) + r"(?![\w+#])", re.I)) for s in config.SKILL_WORDS]


def skills_of(job: Job) -> list[str]:
    out, seen = [], set()
    for s in list(job.skills) + [s for s, rx in _SKILL_RE if rx.search(f"{job.title}\n{job.description}")]:
        s = (s or "").strip()
        if s and s.lower() not in seen and len(s) <= 30:
            seen.add(s.lower())
            out.append(s)
    return out[:12]


# ---------------------------------------------------------------------------------------
def prefilter_reason(job: Job) -> str:
    """Cheap checks on what a search result already gives (title, location, structured experience).
    Runs BEFORE any slow detail request. '' means: worth fetching the full description."""
    if config.NOT_DEV.search(job.title):
        return "not a developer role"
    if config.SENIOR_TITLE.search(job.title) and not _INTERN.search(job.title):
        return "senior / too much experience required"
    if not match_roles(job.title):
        return "not a developer role"
    if job.exp_min is not None and job.exp_min >= config.MAX_EXPERIENCE_YEARS and not job.is_internship:
        return "senior / too much experience required"
    if is_foreign(job.location):
        return "outside India"
    return ""


def classify(job: Job) -> Job:
    """Fill roles / areas / experience / flags and set hidden_reason ('' means the job is shown)."""
    if _INTERN.search(job.title) or job.work_type.lower() == "internship":
        job.is_internship = True
        job.work_type = "Internship"
    job.roles = match_roles(job.title)
    job.work_mode = work_mode_of(job)
    job.areas = areas_of(f"{job.location} {job.address}")
    if not job.areas and not is_foreign(job.location):
        job.areas = [a for a in areas_of(job.description[:1500]) if a != "Other India"]
    if job.work_mode == "Remote" and "Remote" not in job.areas:
        job.areas.append("Remote")
    job.skills = skills_of(job)
    job.experience, job.exp_range, too_much = experience_info(job)

    flags = []
    bond = bond_flag(job.description)
    if bond:
        flags.append(bond)
    if is_consultancy(job.company) or "Via consultancy" in job.flags:   # Naukri marks consultants itself
        flags.append("Via consultancy")
    job.flags = flags

    pre = prefilter_reason(job)
    if pre:
        job.hidden_reason = pre
    elif asks_for_money(f"{job.title}\n{job.description}"):
        job.hidden_reason = "asks for money / paid training"
    elif too_much:
        job.hidden_reason = "senior / too much experience required"
    else:
        job.hidden_reason = ""
    return job
