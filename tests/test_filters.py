"""Filter tests on real-world Indian job-ad wording.   python -m pytest -q tests"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.filters import (  # noqa: E402
    areas_of, asks_for_money, bond_flag, classify, is_consultancy, match_roles, work_mode_of,
)
from pipeline.model import Job, lpa  # noqa: E402


def job(title, desc="", location="Bengaluru", **kw):
    return classify(Job(platform="Naukri", platform_id="1", title=title, company=kw.pop("company", "Acme"),
                        url="u", location=location, description=desc, **kw))


# ---------------- roles ----------------
@pytest.mark.parametrize("title, role", [
    ("Software Engineer", "Software Engineer / SDE"),
    ("SDE 1", "Software Engineer / SDE"),
    ("Associate Software Engineer", "Software Engineer / SDE"),
    ("Member of Technical Staff", "Software Engineer / SDE"),
    ("Graduate Engineer Trainee - Software", "Software Engineer / SDE"),
    ("Java Developer", "Backend"),
    ("Python Django Developer", "Backend"),
    ("Node.js Developer", "Backend"),
    ("React JS Developer", "Frontend"),
    ("MERN Stack Developer", "Full Stack"),
    ("Flutter Developer", "Mobile"),
    ("React Native Developer", "Mobile"),
    ("GenAI Engineer", "AI / ML"),
    ("Machine Learning Engineer", "AI / ML"),
    ("Data Scientist - Fresher", "AI / ML"),
    ("Data Engineer", "Data"),
    ("DevOps Engineer", "DevOps / Cloud"),
    ("SDET", "QA / SDET"),
    ("QA Automation Engineer", "QA / SDET"),
    ("Salesforce Developer", "Other developer"),
])
def test_roles(title, role):
    assert role in match_roles(title)


def test_react_native_is_not_frontend():
    assert "Frontend" not in match_roles("React Native Developer")


def test_javascript_is_not_java():
    assert "Backend" not in match_roles("JavaScript Developer")


@pytest.mark.parametrize("title", [
    "Inside Sales Executive - AI Products", "Python Trainer", "IT Recruiter", "Technical Support Engineer",
    "Business Development Executive (Software)", "Data Entry Operator", "Content Writer - AI",
    "Mechanical Design Engineer", "UI/UX Designer", "Customer Success Engineer", "Data Analyst (Kannada Speaker)",
    "Quality Engineer",
])
def test_non_developer_titles_hidden(title):
    assert job(title).hidden_reason == "not a developer role"


# ---------------- seniority / experience ----------------
@pytest.mark.parametrize("title", [
    "Senior Software Engineer", "Sr. Java Developer", "Tech Lead - Backend", "Staff Engineer", "Principal Engineer",
    "SDE 2", "SDE-III", "Software Engineer II", "Engineering Manager", "Solution Architect", "Intermediate Backend Engineer",
    ".Net Fullstack Developer-AVP",
])
def test_senior_titles_hidden(title):
    assert job(title).hidden_reason == "senior / too much experience required"


def test_member_of_technical_staff_is_not_senior():
    assert job("Member of Technical Staff").hidden_reason == ""


@pytest.mark.parametrize("lo, hi, label, hidden", [
    (0, 1, "Freshers welcome", False),
    (0, 2, "Freshers welcome", False),
    (0, 5, "Freshers welcome", False),
    (1, 3, "1 year asked", False),
    (2, 4, "Needs 2+ years", True),
    (3, 7, "Needs 3+ years", True),
])
def test_structured_experience(lo, hi, label, hidden):
    j = job("Software Engineer", exp_min=lo, exp_max=hi)
    assert j.experience == label
    assert bool(j.hidden_reason) == hidden


@pytest.mark.parametrize("desc, label, hidden", [
    ("Experience: 0-2 Years", "Freshers welcome", False),
    ("Freshers can apply. B.Tech CSE 2025 batch.", "Freshers welcome", False),
    ("Open for 2025 / 2026 pass-outs", "Freshers welcome", False),
    ("Minimum 1 year of experience in Python", "1 year asked", False),
    ("6 months of experience with React", "Less than 1 year", False),
    ("Requires 2+ years of experience in Java", "Needs 2+ years", True),
    ("Minimum two (2) years experience in backend development", "Needs 2+ years", True),
    ("3-5 yrs exp in Spring Boot", "Needs 3+ years", True),
    ("Experience: 4 to 6 years", "Needs 4+ years", True),
    ("Our company has 20 years of experience in fintech. Strong Python skills.", "Experience not mentioned", False),
    ("Proven experience building REST APIs", "Some experience preferred", False),
    ("Great opportunity to grow.", "Experience not mentioned", False),
    ("Service bond of 2 years. Freshers welcome", "Freshers welcome", False),
])
def test_experience_from_text(desc, label, hidden):
    j = job("Software Developer", desc)
    assert j.experience == label
    assert bool(j.hidden_reason) == hidden


def test_experience_in_title():
    assert job("Java Developer (3-6 years)").hidden_reason == "senior / too much experience required"


def test_no_freshers_wins_over_fresher_word():
    j = job("Backend Developer", "Not for freshers. Need 3 years of experience in Node.js")
    assert j.hidden_reason == "senior / too much experience required"


# ---------------- internships ----------------
def test_internship_kept_and_tagged():
    j = job("Software Development Intern", "Duration: 6 months. Stipend 20,000/month")
    assert j.is_internship and j.experience == "Internship" and j.hidden_reason == ""


def test_non_dev_internship_hidden():
    assert job("Marketing Intern").hidden_reason == "not a developer role"


# ---------------- places ----------------
@pytest.mark.parametrize("loc, areas", [
    ("Bangalore", ["Bengaluru"]),
    ("Bengaluru(HSR Layout)", ["Bengaluru"]),
    ("Gurgaon", ["Delhi NCR"]),
    ("Noida, Delhi / NCR", ["Delhi NCR"]),
    ("Hyderabad, Bengaluru, Delhi / NCR", ["Bengaluru", "Hyderabad", "Delhi NCR"]),
    ("Hybrid - Pune, Mumbai (All Areas)", ["Pune", "Mumbai"]),
    ("Visakhapatnam", ["Andhra Pradesh"]),
    ("Jaipur, India", ["Other India"]),
    ("India", ["Other India"]),
    ("Remote", ["Remote"]),
])
def test_areas(loc, areas):
    assert areas_of(loc) == areas


@pytest.mark.parametrize("loc", ["London, UK", "Australia, Canada, Other International", "San Francisco, CA", "Singapore"])
def test_foreign_hidden(loc):
    assert job("Software Engineer", location=loc).hidden_reason == "outside India"


def test_remote_job_gets_remote_area():
    j = job("Python Developer (Remote)", location="India")
    assert j.work_mode == "Remote" and "Remote" in j.areas


def test_work_mode_from_description():
    assert work_mode_of(Job("x", "1", "Dev", "c", "u", description="This is a hybrid role, 3 days in office")) == "Hybrid"


# ---------------- traps ----------------
@pytest.mark.parametrize("desc", [
    "Registration fee of Rs 2000 is required before joining.",
    "100% placement guarantee after our training program.",
    "Pay Rs. 15000 for the course and get a job.",
    "Refundable security deposit of 25,000 at joining.",
    "Internship live training on web development",
])
def test_scams_hidden(desc):
    assert asks_for_money(desc)
    assert job("Web Developer", desc).hidden_reason == "asks for money / paid training"


@pytest.mark.parametrize("desc", [
    "We never ask you to pay fees or send money for applications.",
    "No registration fee. Freshers welcome.",
    "Beware of fraudsters asking for a registration fee in our name.",
    "Paid training for 3 months, then full-time role.",
])
def test_fee_denials_are_fine(desc):
    assert not asks_for_money(desc)


@pytest.mark.parametrize("desc, flag", [
    ("Candidates must sign a 2 year service bond.", "Bond: 2 years"),
    ("Bond: 18 months", "Bond: 18 months"),
    ("Service bond applicable.", "Service bond"),
    ("There is no bond.", ""),
])
def test_bond(desc, flag):
    assert bond_flag(desc) == flag


def test_bond_does_not_count_as_experience():
    assert job("Software Engineer", "Freshers. 2 years service bond.").hidden_reason == ""


@pytest.mark.parametrize("company, yes", [
    ("ABC HR Solutions", True), ("Talent Hub Placements", True), ("XYZ Consultants", True),
    ("Tata Consultancy Services", False), ("Razorpay", False),
])
def test_consultancy(company, yes):
    assert is_consultancy(company) == yes


# ---------------- salary ----------------
@pytest.mark.parametrize("lo, hi, per, out", [
    (400000, 600000, "year", "₹4–6 LPA"),
    (450000, 450000, "year", "₹4.5 LPA"),
    (15000, 20000, "month", "₹15,000–20,000 / month"),
    (None, None, "year", ""),
])
def test_lpa(lo, hi, per, out):
    assert lpa(lo, hi, per) == out


def test_months_range_text():
    assert job("Software Developer", "Experience: 1 month of experience in React").exp_range == "1 month+"


def test_senior_internship_type_still_hidden():
    j = job("Senior Specialist - Software Engineering", work_type="Internship")
    assert j.hidden_reason == "senior / too much experience required"


def test_cnc_programmer_not_dev():
    assert job("VMC CAM Programmer").hidden_reason == "not a developer role"


def test_neither_charge_fee_is_fine():
    assert not asks_for_money("Neither LTM nor any of its partners charge any candidate registration fee.")


def test_training_and_internship_certificate_is_fine():
    assert not asks_for_money("Training and internship certificates are provided on completion")
