"""Independent assigned-month readings and distinct literal window evidence."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.heluo import MONTH_GUA, gua_lines, judge
from fatebridge.core.heluo_hexagrams import _gua_tables
from fatebridge.core.heluo_months import MONTH_BRANCHES, month_affinity
from fatebridge.core.output_numerology import HeluoMonthAffinity
from fatebridge.utils.errors import NumerologySourceError
from tests.numerology.test_heluo_najia_depth import PILLARS, example_chart

ROOT = Path(__file__).parents[1] / "fixtures/numerology_nlc_v1"
REFERENCE = json.loads((ROOT / "month-reference.json").read_text())
# The historical fixture stays unchanged: only these four probes previously
# promoted a false month label into a false whole qualified clause.
UNRESOLVED_QUALIFIER_MIGRATIONS = {
    ("離為火", 3, 0),
    ("雷水解", 5, 0),
    ("水風井", 2, 0),
    ("風水渙", 3, 0),
}


def chart_for(gua):
    chart = example_chart()
    pair = _gua_tables()[0][gua]
    for phase in ("xian", "hou"):
        chart[phase].update(name=gua, **pair, lines=gua_lines(pair["up"], pair["low"]))
    return chart


def test_month_source_witnesses_keep_the_declared_identity():
    manifest = json.loads((ROOT / "month-manifest.json").read_text())
    assert manifest["pdf_sha256"] == REFERENCE["source_pdf_sha256"]
    for page in manifest["images"]:
        assert (
            hashlib.sha256((ROOT / page["file"]).read_bytes()).hexdigest()
            == page["sha256"]
        )


@pytest.mark.parametrize("case", REFERENCE["assigned_months"], ids=lambda c: c["gua"])
def test_original_month_readings(case):
    chart = chart_for(case["gua"])
    actual = judge(chart, PILLARS, case["branch"])
    assert actual["deTime"] is True
    for row in actual["month_affinity"]["phases"]:
        assert row["assigned_month_number"] == case["month"]
        assert row["assigned_month_match"] is True
        assert row["source_pdf_page"] == case["page"]
    other = MONTH_BRANCHES[case["month"] % 12]
    assert judge(chart, PILLARS, other)["deTime"] is False


@pytest.mark.parametrize(
    "gua,old_branch,new_branch",
    [
        ("火澤睽", "辰", "卯"),
        ("震為雷", "丑", "亥"),
        ("水澤節", "申", "子"),
        ("水風井", "辰", "卯"),
    ],
)
def test_default_intro_profile_preserves_its_source_month_readings(
    gua, old_branch, new_branch
):
    chart = chart_for(gua)
    assert judge(chart, PILLARS, old_branch)["deTime"] is False
    assert judge(chart, PILLARS, new_branch)["deTime"] is True


@pytest.mark.parametrize("case", REFERENCE["window_cases"])
def test_extra_windows_are_not_collapsed_into_assigned_month(case):
    actual = month_affinity(
        chart_for(case["gua"]), MONTH_BRANCHES[case["month"] - 1], MONTH_GUA
    )
    assert actual["complete_assessment"] is False
    for phase in actual["phases"]:
        index = case.get("window_index", 0)
        window = phase["additional_windows"][index]
        if (case["gua"], case["month"], index) in UNRESOLVED_QUALIFIER_MIGRATIONS:
            assert case["match"] is False
            assert window["month_label_match"] is False
            assert window["match"] is None
            assert window["status"] == "additional_condition_unresolved"
        else:
            assert window["match"] is case["match"]
    if case["gua"] == "天雷無妄":
        assert actual["phases"][0]["source_pdf_page"] == 18
        assert actual["phases"][0]["source_status"] == "volume_one_table_explicit_month"
        assert actual["phases"][0]["source_readings"][0]["month_number"] is None
        assert (
            actual["phases"][0]["source_readings"][0]["status"] == "month_not_explicit"
        )


def test_discrete_months_are_not_expanded_and_opposed_clauses_are_retained():
    def row(gua, month):
        return month_affinity(chart_for(gua), MONTH_BRANCHES[month - 1], MONTH_GUA)[
            "phases"
        ][0]

    yu = row("雷地豫", 5)
    assert yu["assigned_month_match"] is True
    window = yu["additional_windows"][0]
    assert window["kind"] == "discrete_months"
    assert window["month_numbers"] == [2, 8]
    assert window["match"] is False
    assert "first_month_number" not in window
    sui = row("澤雷隨", 1)
    assert [w["match"] for w in sui["additional_windows"]] == [True, True]
    assert sui["opposed_month_conditions"] is True
    assert sui["conflict_rule_ids"] == [w["rule_id"] for w in sui["additional_windows"]]
    assert row("澤雷隨", 2)["opposed_month_conditions"] is False


@pytest.mark.parametrize(
    "gua,month", [("離為火", 5), ("雷水解", 12), ("水風井", 3), ("風水渙", 5)]
)
def test_month_label_does_not_discharge_unevaluated_qualifiers(gua, month):
    actual = month_affinity(chart_for(gua), MONTH_BRANCHES[month - 1], MONTH_GUA)
    matched = [
        w for w in actual["phases"][0]["additional_windows"] if w["month_label_match"]
    ]
    assert matched
    assert all(
        w["match"] is None and w["qualifier_status"] == "not_evaluated" for w in matched
    )
    assert actual["complete_assessment"] is False


def test_full_intro_review_does_not_become_complete_book_or_full_assessment():
    actual = month_affinity(chart_for("天雷無妄"), "酉", MONTH_GUA)
    assert actual["reviewed_hexagram_introductions"] == 64
    assert actual["explicit_assigned_months"] == 63
    assert actual["additional_month_clauses"] == 21
    assert actual["review_status"].endswith("independent_second_review_pending")
    assert actual["complete_assessment"] is False


def test_table_stays_complete_and_conflicting_source_anchor_fails_visibly():
    from copy import deepcopy

    assert len([n for names in MONTH_GUA.values() for n in names]) == 64
    assert len({n for names in MONTH_GUA.values() for n in names}) == 64
    bad = deepcopy(MONTH_GUA)
    bad["卯"].remove("睽")
    bad["辰"].append("睽")
    with pytest.raises(NumerologySourceError, match="冲突"):
        month_affinity(chart_for("火澤睽"), "卯", bad)


@pytest.mark.parametrize("branch", [None, "", "未知", "寅卯"])
def test_unknown_month_cannot_become_a_negative_assessment(branch):
    with pytest.raises(ValueError):
        month_affinity(chart_for("火澤睽"), branch, MONTH_GUA)


@pytest.mark.parametrize(
    "payload",
    [
        {"birth_month_number": True},
        {"complete_assessment": True},
        {"phases": [{"assigned_month_match": "false"}]},
        {"phases": [{"additional_windows": [{"match": "true"}]}]},
        {"phases": [{"additional_windows": [{"month_numbers": [True]}]}]},
        {"phases": [{"additional_windows": [{"uncertain_month_numbers": [13]}]}]},
        {"phases": [{"opposed_month_conditions": "false"}]},
    ],
)
def test_corrupt_month_facts_are_rejected(payload):
    with pytest.raises(ValidationError):
        HeluoMonthAffinity.model_validate(payload)


@pytest.mark.parametrize(
    "date,expected,unexpected",
    [
        ("2000-02-10", "此月同时进入原文及时与失时两段，保留冲突", None),
        ("2000-04-19", "月号匹配，附加条件待核", "边界月待核"),
        ("2002-10-19", "边界月待核", "附加条件待核"),
    ],
)
def test_snapshot_distinguishes_qualifier_uncertainty_endpoint_and_conflict(
    date, expected, unexpected
):
    from fatebridge.core.local_techniques.heluo import build_heluo_result

    result = build_heluo_result(
        date=date,
        time="09:33:00",
        zone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    text = result["snapshot_text"]
    assert expected in text
    if unexpected:
        assert unexpected not in text
