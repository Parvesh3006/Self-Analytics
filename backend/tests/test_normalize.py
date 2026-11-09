import pytest

from app.crawl.extract import jobpostings_from_html, rawjob_from_jsonld
from app.normalize.salary import parse_salary_text, to_annual_usd
from app.normalize.skills import extract_skills
from app.normalize.text import html_to_text, norm_key
from app.normalize.titles import role_family, seniority
from app.services.discovery import boards_in
from app.services.ingest import fingerprint


def test_skills_match_real_mentions():
    found = extract_skills("We use Python, React.js, Node.js, PostgreSQL and k8s with CI/CD on AWS.")
    assert {"Python", "React", "Node.js", "PostgreSQL", "Kubernetes", "CI/CD", "AWS"} <= set(found)


@pytest.mark.parametrize("sentence,skill", [
    ("You will go to client sites and help the team go further", "Go"),
    ("We rust-proof bridges in spring", "Spring"),
    ("r and d department, express delivery", "R"),
    ("express delivery", "Express"),
])
def test_everyday_words_are_not_skills(sentence, skill):
    assert skill not in extract_skills(sentence)


def test_capitalised_short_skills_count():
    found = extract_skills("Backend in Go and Rust, statistics in R.")
    assert {"Go", "Rust", "R"} <= set(found)


def test_cplusplus_is_not_c_sharp_or_java_from_javascript():
    found = extract_skills("Strong C++ and JavaScript")
    assert "C++" in found and "JavaScript" in found and "Java" not in found and "C#" not in found


@pytest.mark.parametrize("text,low,high,currency,period", [
    ("Salary: $120,000 - $150,000 per year", 120000, 150000, "USD", "year"),
    ("£45k-£55k", 45000, 55000, "GBP", "year"),
    ("A$140k to A$160k", 140000, 160000, "AUD", "year"),
    ("€65.000 - €80.000", 65000, 80000, "EUR", "year"),
    ("$45/hour", 45, None, "USD", "hour"),
    ("₹18L - ₹25L", 1800000, 2500000, "INR", "year"),
])
def test_salary_parsing(text, low, high, currency, period):
    s = parse_salary_text(text)
    assert (s.min, s.max, s.currency, s.period) == (low, high, currency, period)


@pytest.mark.parametrize("text", ["We raised $40 million in Series B", "Our revenue is $200,000,000", "5 years experience, 401k match"])
def test_non_salary_money_ignored(text):
    assert parse_salary_text(text) is None


def test_bare_dollar_is_local_currency():
    assert parse_salary_text("$120,000 - $140,000", "AU").currency == "AUD"
    assert parse_salary_text("$120,000 - $140,000", "US").currency == "USD"
    assert parse_salary_text("US$120,000", "AU").currency == "USD"


def test_annual_conversion_and_plausibility():
    rates = {"AUD": 1.5}
    assert to_annual_usd(150000, "AUD", "year", rates) == 100000
    assert to_annual_usd(50, "USD", "hour", rates) == 104000
    assert to_annual_usd(50, "USD", "year", rates) is None  # implausible annual pay
    assert to_annual_usd(100000, "XXX", "year", rates) is None  # unknown currency


@pytest.mark.parametrize("title,family", [
    ("Senior Machine Learning Engineer", "Machine Learning / AI"), ("Data Engineer II", "Data Engineering"), ("DevOps Engineer", "DevOps / SRE / Cloud"),
    ("Front-End Developer", "Frontend"), ("Software Engineer, Backend", "Backend"), ("Engineering Manager", "Engineering Management"),
    ("Registered Nurse", "Healthcare"), ("Account Executive", "Sales"),
])
def test_role_family(title, family):
    assert role_family(title) == family


def test_seniority():
    assert seniority("Senior Data Engineer") == "Senior"
    assert seniority("Graduate Software Engineer") == "Intern / Graduate"
    assert seniority("Staff Engineer") == "Principal / Staff"
    assert seniority("Software Engineer") == "Mid / Unspecified"


def test_fingerprint_ignores_case_and_punctuation():
    a = fingerprint("Senior Engineer", "Acme, Inc.", "AU", "Sydney", None)
    assert a == fingerprint("senior  engineer", "ACME Inc", "AU", "sydney", None)
    assert a != fingerprint("Senior Engineer", "Acme, Inc.", "AU", "Melbourne", None)


def test_text_helpers():
    assert norm_key("Zürich-Nord") == "zurich nord"
    assert html_to_text("<p>One</p><ul><li>Two</li></ul><script>x()</script>") == "One\nTwo"


def test_jsonld_extraction():
    html = """<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"JobPosting","title":"Data Engineer",
    "hiringOrganization":{"name":"Acme"},"datePosted":"2026-10-01","description":"<p>Build pipelines</p>",
    "jobLocation":{"address":{"addressLocality":"Sydney","addressRegion":"NSW","addressCountry":"AU"}},
    "baseSalary":{"currency":"AUD","value":{"minValue":120000,"maxValue":140000,"unitText":"YEAR"}}}]}</script>"""
    posting = jobpostings_from_html(html)[0]
    job = rawjob_from_jsonld(posting, "https://x.test/j/1")
    assert (job.title, job.company, job.country_code, job.salary_min, job.salary_currency) == ("Data Engineer", "Acme", "AU", 120000, "AUD")
    assert job.location == "Sydney, NSW, AU" and job.description == "Build pipelines"


def test_board_discovery():
    found = boards_in(["https://boards.greenhouse.io/acme/jobs/1", "https://jobs.lever.co/widgets", "https://example.com/", "https://boards.greenhouse.io/embed/job_board"])
    assert found == {("greenhouse", "acme"), ("lever", "widgets")}
