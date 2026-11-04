"""What employers ask for: benefits, years, degrees, interview style, office days, stack groups.

Unit cases come from real "Who is hiring?" wording. The accuracy floors run on hand-labeled
fixtures that keep only the lines the rules read, never whole posts.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from sejr.features import post_answers
from sejr.features.benefits import CATEGORIES, offered_benefits
from sejr.features.experience import degree, years_bucket, years_required
from sejr.features.traits import interview_styles, office_days
from sejr.features.vocab import GROUP_TERMS, stack_terms

FIXTURES = Path(__file__).parent / "fixtures" / "post_trends"


@pytest.mark.parametrize(
    ("text", "present", "absent"),
    [
        ("Perks: unmetered vacation, health, dental, vision, life, 401k.",
         {"unlimited_pto", "health_insurance", "dental_vision", "retirement"}, set()),
        ("Competitive salary + equity + bonus", {"equity", "bonus"}, set()),
        ("$150k, no equity, fully remote", set(), {"equity"}),
        ("Salary only (no equity at this stage).", set(), {"equity"}),
        ("We champion diversity, equity and inclusion.", set(), {"equity"}),
        ("We help 20k private companies with equity management", set(), {"equity"}),
        ("Equity: ~10%", {"equity"}, set()),
        ("Asyncy | Front End Engineer | Amsterdam | €60k | <1% | angel.co", {"equity"}, set()),
        ("Bonus points for Go experience. Elixir is a bonus.", set(), {"bonus"}),
        ("Base, discretionary year-end bonus and a $20K signing bonus",
         {"bonus", "sign_on_bonus"}, set()),
        ("25 days paid vacation, 5 paid sick days", {"pto_days"}, set()),
        ("28-days holiday, plus bank holidays", {"pto_days"}, set()),
        ("Generous PTO and great benefits", set(), {"pto_days", "unlimited_pto", "health_insurance"}),
        ("12 weeks of fully paid maternity leave", {"parental_leave"}, {"pto_days"}),
        ("Employees file parental leave requests in our app", set(), {"parental_leave"}),
        ("We work a 4-day work week at full pay", {"four_day_week"}, set()),
        ("$5k/year to spend on continuing education", {"learning_budget"}, set()),
        ("home office setup stipend; coworking budget", {"remote_stipend"}, set()),
        ("Remote support engineer for our help desk", set(), {"remote_stipend"}),
        ("Relocation assistance available", {"relocation"}, set()),
        ("We are not able to offer relocation.", set(), {"relocation"}),
        ("Must be willing to relocate to Austin", set(), {"relocation"}),
        ("Visa & Relo supported", {"relocation", "visa"}, set()),
        ("We help people get health insurance through healthcare.gov", set(), {"health_insurance"}),
        ("100% of health insurance premiums paid for by the company", {"health_insurance"}, set()),
        ("We build software for pension funds", set(), {"retirement"}),
        ("Unfortunately we cannot sponsor visas.", set(), {"visa"}),
        ("Toronto, ON (Local, Remote, Visa, Relocation)", {"relocation", "visa"}, set()),
        ("Relocation could be possible if you are the right person!", {"relocation"}, set()),
        ("we do provide a relocation incentive", {"relocation"}, set()),
        ("Relocation not provided.", set(), {"relocation"}),
        ("Both roles require relocation to Japan.", set(), {"relocation"}),
        ("We're open to relocating people", {"relocation"}, set()),
        ("401k, unlimited time-off, full healthcare", {"unlimited_pto", "health_insurance"}, set()),
        ("med/dental/vision", {"health_insurance", "dental_vision"}, set()),
        ("75 paid vacations days", {"pto_days"}, set()),
        ("co-working/gear budget; Internet stipend", {"remote_stipend"}, set()),
        ("We help employees pick the right health insurance", set(), {"health_insurance"}),
        ("a new approach to health benefits", set(), {"health_insurance"}),
        ("We back founders with equity-free grants", set(), {"equity"}),
        ("Bonuses:\n - AJAX, jQuery", set(), {"bonus"}),
        ("$180-250K + Bonus/Carry (hedge fund equity equivalent)", {"bonus"}, {"equity"}),
        ("meaningful, non-trivial equity", {"equity"}, set()),
        ("Benefits: health care, 401k", {"health_insurance", "retirement"}, set()),
        ("We are a health care company", set(), {"health_insurance"}),
        ("Insurance (medical, dental, retirement)", {"retirement"}, set()),
        ("home office expenses; an education expense account",
         {"remote_stipend", "learning_budget"}, set()),
        ("we consider relocation for strong candidates", {"relocation"}, set()),
        ("assistance in relocating", {"relocation"}, set()),
        ("we are open to providing relocation assistance", {"relocation"}, set()),
        ("Both roles require (eventual) relocation to Japan", set(), {"relocation"}),
        ("Relocation to London preferred", set(), {"relocation"}),
        ("relocation to the bay area", set(), {"relocation"}),
    ],
)  # fmt: skip
def test_benefits(text, present, absent):
    found = set(offered_benefits(text))
    assert present <= found
    assert not (absent & found)


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("3+ years of professional experience with Python", 3),
        ("Senior (5+ YOE), Mid (3+ yrs)", 3),
        ("minimum of 3-5+ years experience developing websites", 3),
        ("You should have at least four years of experience", 4),
        ("more than 5 years of experience in backend development", 5),
        ("-5+ years of experience building large scale applications", 5),
        ("Exp: 6–12+ yrs", 6),
        ("Magoosh has been around for two years and is growing fast", None),
        ("Founded 10 years ago, profitable for 4+ years", None),
        ("We have 3+ years of runway", None),
        ("Our team has 50+ years of combined experience", None),
        ("most of us have 10-25 years' experience", None),
        ("The junior roles suit people with <= 2 years of experience", None),
        ("We scaled to $20m ARR in 3 years with 600 customers", None),
        ("a 4 year degree", None),
        ("the CTO has been working with Rails for five years", None),
        ("named a fastest growing company for nine years in a row", None),
        ("We have 3+ years cash runway", None),
        ("A family business (20+ years) in Ohio", None),
        ("Senior (5+ years)", 5),
        ("founded by a portfolio manager with 15+ years of experience", None),
        ("product minded (3y+ experience, 32-40h)", 3),
        ("Python (5+ years)", 5),
        ("an experienced (4+ years) developer", 4),
        ("Acme, established (20+ years), is hiring", None),
        ("Our CTO, with 15+ years at Google, leads the team", None),
        ("Product manager with 5+ years of experience", 5),
        ("Two (2) years of experience required", 2),
    ],
)
def test_years_required(text, years):
    assert years_required(text) == years


def test_years_buckets():
    assert [years_bucket(y) for y in (0, 2, 3, 4, 5, 7, 8, 15)] == [
        "0_2", "0_2", "3_4", "3_4", "5_7", "5_7", "8_plus", "8_plus"
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("BS in Computer Science", "required"),
        ("Computer Science degree preferred", "required"),
        (
            "BS/MS/PhD in Computer Science, Statistics, Math or related fields",
            "required",
        ),
        ("Bachelor's degree in CS or equivalent experience", "optional"),
        ("Degrees are not required for several of these positions.", "optional"),
        ("We hire from no-degree to PhD.", "optional"),
        ("founding team of two PhDs and a professor from Berkeley CS", "none"),
        ("Open to students working towards their degree in CS", "none"),
        ("Our CEO has a PhD in physics", "none"),
        ("We'll teach you growth to an advanced degree", "none"),
        ("We have diverse backgrounds (Stanford, Bain, Google)", "none"),
        ("No BS, just shipping. MS SQL Server experience a plus", "none"),
    ],
)
def test_degree(text, label):
    assert degree(text) == label


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("Hybrid (3 days/week in SF office)", 3),
        ("in-person at least 3 days per week", 3),
        ("NYC (In-Office 3-4 days)", 3),
        ("HYBRID (4 days/week)", 4),
        ("Findigs | NYC | 3x/week in office", 3),
        ("Strictly on-site (Mon-Fri, 9-5:30pm)", 5),
        ("in the office in Cambridge Tue-Thu", 3),
        ("onsite (option to WFH 3 days a week)", None),
        ("We work a 4 day work week", None),
        ("support 24 hours a day, 7 days a week", None),
        ("Hybrid, flexible days in office", None),
        ("V7 | London (UK) | ONSITE (2/3 Days P/W)", 2),
        ("Hybrid (2/3 days in the office)", 2),
        ("hybrid: on-campus at least two or three days per week", 2),
    ],
)
def test_office_days(text, days):
    assert office_days(text) == days


@pytest.mark.parametrize(
    ("text", "styles"),
    [
        ("Interview process: Take-home coding assignment, Pair programming interview",
         {"take_home", "pair_programming"}),
        ("No leetcode. No whiteboard.", {"no_leetcode"}),
        ("We don't do whiteboard interviews", {"no_leetcode"}),
        ("Interviews include LeetCode-style questions", set()),
        ("Never-ending supply of short coding puzzles", set()),
        ("We pair program daily and practice TDD", set()),
        ("Everything is done via Zoom and there are no takehomes", set()),
        ("a quick sample project (fully paid)", {"paid_trial"}),
        ("We pay $300 for take-home exercises", {"paid_trial", "take_home"}),
        ("Your take-home pay is competitive", set()),
    ],
)  # fmt: skip
def test_interview_styles(text, styles):
    assert set(interview_styles(text)) == styles


def test_new_answers_shape():
    text = (
        "Acme | Senior Engineer | NYC (Hybrid, 3 days/week)\n\n5+ years of Python. "
        "BS in CS or equivalent experience. Equity, 401(k) match. Take-home, no LeetCode."
    )
    rows = {q: (method, value, label, probs) for _, q, method, _, value, label, probs, _ in
            post_answers(1, text)}  # fmt: skip
    assert rows["years_required"] == ("regex", 5.0, "5_7", None)
    assert rows["degree"][2] == "optional"
    assert rows["office_days"][1] == 3.0
    assert rows["post_length"][:2] == ("count", float(len(text)))
    assert json.loads(rows["benefits"][3]) == {"equity": 1.0, "retirement": 1.0}
    assert set(json.loads(rows["interview_style"][3])) == {"take_home", "no_leetcode"}
    # A post that states nothing still gets rows, so shares have every post as denominator.
    empty = {
        q: (value, label) for _, q, _, _, value, label, _, _ in post_answers(2, "Acme")
    }
    assert empty["years_required"] == (None, None)
    assert empty["office_days"] == (None, None)
    assert empty["degree"] == (None, "none")


def _load(name: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / name).read_text().splitlines()]


# Hand labels, written before the rules ran on these posts. "random" is a seeded draw of 120
# live hiring posts (30 per era: 2011–14, 2015–19, 2020–22, 2023–26); "keyword" is 80 posts
# with a benefits, experience or interview word (20 per era; one seeker post that landed in a
# hiring thread was dropped, leaving 79); "sentences" is 120 posts' keyword sentences (30 per era),
# labeled for years, degree, office days and interview style. "review_random" (150 posts)
# and "review_keyword" (100 keyword-dense posts) were drawn and labeled by an independent
# reviewer. Rules were tuned on a separate 240-post dev draw; general misses found in each
# set's first scoring were then fixed, so every set is partly in-sample now. First scores
# are in docs/architecture.md. Personal emails in the fixtures are replaced by [email].
POSTS = _load("post_labels.jsonl")
SIZES = {"random": 120, "keyword": 79, "sentences": 120, "review_random": 150,
         "review_keyword": 100, "heldout": 60}  # fmt: skip
# The reviewer's seed-31337 draw (30 random, 30 keyword-dense) was labeled for benefits and
# years only and scored before the rules saw it: benefits 0.99/0.90, years 9 of 9 stated.
# The next round fixed the misses it showed, so it is partly in-sample too.
TRAITS = [r for r in POSTS if r["set"] != "heldout"]


def _text(row: dict) -> str:
    return "\n".join(row["lines"])


def _pr(tp: int, fp: int, fn: int) -> tuple[float, float]:
    return tp / (tp + fp), tp / (tp + fn)


def _scores(pairs) -> tuple[float, float]:
    """Precision and recall over (gold set, found set) pairs: positives only, not every row."""
    tp = fp = fn = 0
    for gold, found in pairs:
        tp, fp, fn = (
            tp + len(found & gold),
            fp + len(found - gold),
            fn + len(gold - found),
        )
    return _pr(tp, fp, fn)


def test_fixture_sizes():
    assert Counter(r["set"] for r in POSTS) == SIZES
    assert not any("@" in ln and "." in ln.split("@")[-1][:30] for r in POSTS
                   for ln in r["lines"] if "[email]" not in ln and "@ " not in ln)  # fmt: skip


@pytest.mark.parametrize(
    "sample", ["random", "keyword", "review_random", "review_keyword", "heldout"]
)
def test_benefits_accuracy(sample):
    rows = [r for r in POSTS if r["set"] == sample]
    for row in rows:
        assert set(offered_benefits(_text(row))) <= set(CATEGORIES)
    precision, recall = _scores(
        (set(r["benefits"]), set(offered_benefits(_text(r)))) for r in rows
    )
    assert precision >= 0.95
    assert recall >= 0.85


def _stated(rows, rule, field):
    """A scalar answer as a set, so "stated" is scored on positives: {value} or {}."""
    return (
        ({r[field]} if r[field] is not None else set(),
         {v} if (v := rule(_text(r))) is not None else set())
        for r in rows
    )  # fmt: skip


def test_years_required_accuracy():
    pairs = list(_stated(POSTS, years_required, "years"))
    stated = [({1} if g else set(), {1} if f else set()) for g, f in pairs]
    precision, recall = _scores(stated)
    assert precision >= 0.9 and recall >= 0.9
    both = [(g, f) for g, f in pairs if g and f]
    assert sum(g == f for g, f in both) / len(both) >= 0.9


def test_degree_accuracy():
    pairs = [({r["degree"]} - {"none"}, {degree(_text(r))} - {"none"}) for r in TRAITS]
    for label in ("required", "optional"):
        precision, recall = _scores(
            ({label} & gold, {label} & found) for gold, found in pairs
        )
        assert precision >= 0.85 and recall >= 0.8, label


def test_office_days_accuracy():
    pairs = list(_stated(TRAITS, office_days, "office_days"))
    precision, recall = _scores(pairs)  # the stated number must match exactly
    assert precision >= 0.9 and recall >= 0.85


def test_interview_style_accuracy():
    precision, recall = _scores(
        (set(r["interview"]), set(interview_styles(_text(r)))) for r in TRAITS
    )
    assert precision >= 0.85 and recall >= 0.6


# A seeded sample of matches, 30 per group drawn across all terms (so it weighs terms by how
# often they match) and 20 per group from the terms added in features-4, each judged by hand:
# does the match name the technology (not a person, season, company or investor)? The
# fixture keeps the matched snippet and, for added terms, the header line their
# company-field rule reads.
STACK = _load("stack_precision.jsonl")


@pytest.mark.parametrize("sample", ["all_terms", "added_terms"])
@pytest.mark.parametrize("group", list(GROUP_TERMS))
def test_stack_group_precision(sample, group):
    rows = [r for r in STACK if r["sample"] == sample and r["group"] == group]
    assert len(rows) == (30 if sample == "all_terms" else 20)
    detected = [
        r
        for r in rows
        if r["term"] in stack_terms(f"{r['header']}\n{r['snippet']}".lstrip("\n"))
    ]
    assert sum(r["correct"] for r in detected) / len(detected) >= 0.9
    correct = [r for r in rows if r["correct"]]
    assert sum(r in detected for r in correct) / len(correct) >= 0.95
