"""Primary clause witnesses, actual phase facts and unresolved whole verdicts."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import heluo_months
from fatebridge.core.heluo import MONTH_GUA, hexagram_najia, judge
from fatebridge.core.heluo_months import MONTH_BRANCHES, month_affinity
from fatebridge.core.output_numerology import HeluoNatalNajiaClause
from fatebridge.utils.errors import NumerologySourceError
from tests.test_heluo_month_depth import chart_for
from tests.test_heluo_najia_depth import PILLARS

ROOT = Path(__file__).parent / "fixtures/heluo_najia_qualifiers_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
POSITIVE_YEARS = {
    "乾為天": "壬子",
    "坤為地": "癸未",
    "水雷屯": "戊申",
    "水地比": "癸卯",
    "風天小畜": "壬辰",
    "離為火": "己酉",
    "雷水解": "戊寅",
    "水風井": "辛丑",
    "風水渙": "戊寅",
}


def test_clause_witnesses_reuse_the_same_primary_edition_without_new_counts():
    assert REFERENCE["source_pdf_sha256"] == heluo_months.SOURCE_SHA256
    assert len(REFERENCE["literal_clauses"]) == 9
    assert len(REFERENCE["images"]) == 9
    assert REFERENCE["new_direct_assignments_collated"] == 18
    for key in (
        "new_borrowed_assignments_collated",
        "new_independent_calendar_instants",
        "new_classical_birth_examples",
        "new_real_world_outcomes",
        "new_independent_reviews",
        "new_source_images",
    ):
        assert REFERENCE[key] == 0
    assert REFERENCE["review_status"].endswith("independent_second_review_pending")
    for image in REFERENCE["images"]:
        assert image["reused_prior_image"] is True
        assert (
            hashlib.sha256((ROOT / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )


@pytest.mark.parametrize("case", REFERENCE["najia_cases"], ids=lambda c: c["gua"])
def test_three_new_six_line_tables_agree_with_primary_readings(case):
    rows = hexagram_najia(case["lines"])
    assert [r["direct"] for r in rows] == case["direct"]
    assert [r["borrowed"] for r in rows] == case["borrowed"]


@pytest.mark.parametrize("case", REFERENCE["literal_clauses"], ids=lambda c: c["gua"])
def test_literal_binding_and_actual_najia_do_not_settle_an_unmatched_month(case):
    outside = next(m for m in range(1, 13) if m not in case["month_numbers"])
    chart = chart_for(case["gua"])
    before = deepcopy(chart)
    result = judge(
        chart,
        {**PILLARS, "year": POSITIVE_YEARS[case["gua"]]},
        MONTH_BRANCHES[outside - 1],
    )
    assert chart == before
    assert result["deSheng"] is True
    for i, row in enumerate(result["month_affinity"]["phases"]):
        clause = row["natal_najia_clause"]
        assert (
            clause["rule_id"],
            clause["source_pdf_page"],
            clause["literal"],
            clause["month_numbers"],
        ) == (case["id"], case["page"], case["literal"], case["month_numbers"])
        assert clause["month_label_match"] is False
        assert clause["najia"] == {
            k: result["najia"][i][k]
            for k in ("phase", "gua", "year_ganzhi", "matches", "present")
        }
        assert clause["najia"]["present"] is True
        assert clause["qualifier_status"] == "current_phase_facts_available"
        assert clause["match"] is None
        assert clause["connector_status"] == "source_ji_scope_unresolved"
    result["month_affinity"]["phases"][0]["natal_najia_clause"]["najia"][
        "matches"
    ].clear()
    assert result["najia"][0]["matches"]
    assert result["month_affinity"]["phases"][1]["natal_najia_clause"]["najia"][
        "matches"
    ]


@pytest.mark.parametrize("case", REFERENCE["literal_clauses"], ids=lambda c: c["gua"])
def test_true_month_and_false_najia_stay_separate(case):
    year = "丁卯" if case["gua"] in {"乾為天", "風天小畜"} else "甲子"
    result = judge(
        chart_for(case["gua"]),
        {**PILLARS, "year": year},
        MONTH_BRANCHES[case["month_numbers"][0] - 1],
    )
    clause = result["month_affinity"]["phases"][0]["natal_najia_clause"]
    assert clause["month_label_match"] is True
    assert clause["najia"]["present"] is False
    assert clause["najia"]["matches"] == []
    assert clause["match"] is None


def test_najia_uses_its_own_phase_even_when_other_phase_makes_desheng_true():
    chart = chart_for("水風井")
    chart["hou"] = chart_for("離為火")["hou"]
    result = judge(chart, {**PILLARS, "year": "己酉"}, "辰")
    assert result["deSheng"] is True
    xian, hou = [r["natal_najia_clause"] for r in result["month_affinity"]["phases"]]
    assert xian["najia"]["present"] is False and xian["najia"]["matches"] == []
    assert hou["najia"]["present"] is True
    assert hou["najia"]["matches"] == [{"pos": 4, "kind": "direct"}]
    assert xian["match"] is hou["match"] is None


@pytest.mark.parametrize(
    "gua,month", [("離為火", 9), ("水風井", 6), ("風水渙", 1), ("雷水解", 4)]
)
def test_false_month_label_does_not_resolve_a_qualified_clause(gua, month):
    row = month_affinity(chart_for(gua), MONTH_BRANCHES[month - 1], MONTH_GUA)[
        "phases"
    ][0]
    qualified = [w for w in row["additional_windows"] if w["qualifiers"]]
    assert qualified and all(w["month_label_match"] is False for w in qualified)
    assert all(
        w["match"] is None and w["status"] == "additional_condition_unresolved"
        for w in qualified
    )
    assert row["natal_najia_clause"]["najia"] is None
    assert (
        row["natal_najia_clause"]["qualifier_status"] == "not_evaluated_missing_najia"
    )


def test_unregistered_hexagram_does_not_receive_an_invented_clause():
    result = judge(chart_for("天風姤"), PILLARS, "卯")
    assert all(
        row["natal_najia_clause"] is None for row in result["month_affinity"]["phases"]
    )


@pytest.mark.parametrize(
    "corruption",
    [
        "duplicate_phase",
        "wrong_gua",
        "inconsistent_year",
        "invalid_year",
        "missing_line",
        "boolean_pos",
        "invented_match",
        "copied_present",
        "missing_borrowed",
    ],
)
def test_misaligned_phase_najia_cannot_be_used_as_clause_evidence(corruption):
    chart = chart_for("水風井")
    rows = judge(chart, {**PILLARS, "year": "辛丑"}, "未")["najia"]
    if corruption == "duplicate_phase":
        rows[1]["phase"] = "xian"
    elif corruption == "wrong_gua":
        rows[0]["gua"] = "離為火"
    elif corruption == "inconsistent_year":
        rows[0].update(year_ganzhi="甲子", matches=[], present=False)
    elif corruption == "invalid_year":
        rows[0]["year_ganzhi"] = "甲丑"
    elif corruption == "missing_line":
        rows[0]["lines"].pop()
    elif corruption == "boolean_pos":
        rows[0]["lines"][0]["pos"] = True
    elif corruption == "invented_match":
        rows[0]["matches"] = [{"pos": 2, "kind": "direct"}]
    elif corruption == "copied_present":
        rows[0]["present"] = False
    else:
        rows[0]["lines"][0].pop("borrowed")
    with pytest.raises(ValueError):
        month_affinity(chart, "未", MONTH_GUA, najia_assessments=rows)


@pytest.mark.parametrize(
    "key,value",
    [
        ("gua", "離為火"),
        ("page", 189),
        ("literal", "別句"),
        ("month_numbers", [6]),
        ("id", "li_natal_najia"),
    ],
)
def test_clause_pointer_must_match_the_same_literal_witness(
    key, value, monkeypatch, tmp_path
):
    data = json.loads(heluo_months.COLLATION_PATH.read_text())
    clause = next(
        c for c in data["natal_najia_clauses"] if c["id"] == "jing_natal_najia"
    )
    clause[key] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    heluo_months._collation.cache_clear()
    try:
        monkeypatch.setattr(heluo_months, "COLLATION_PATH", path)
        with pytest.raises(NumerologySourceError):
            heluo_months._collation()
    finally:
        heluo_months._collation.cache_clear()


@pytest.mark.parametrize("value", [True, False, "true", 1])
def test_output_contract_rejects_a_decided_whole_clause(value):
    with pytest.raises(ValidationError):
        HeluoNatalNajiaClause.model_validate({"match": value})


def test_partial_clause_leaf_remains_a_valid_output():
    HeluoNatalNajiaClause.model_validate(
        {"month_label_match": False, "najia": {"present": True}, "match": None}
    )


def test_jie_prose_order_disagreement_is_retained_without_claiming_positional_collation():
    issue = REFERENCE["unresolved_source_order"][0]
    assert issue["page"] == 214 and issue["gua"] == "雷水解"
    actual = [r["direct"] for r in hexagram_najia(chart_for("雷水解")["xian"]["lines"])]
    assert actual == issue["engine_positional_list"]
    assert actual != issue["literal_najia_list"]
    assert set(actual) == set(issue["literal_najia_list"])
    assert issue["algorithm_changed"] is False
    assert issue["assignments_added_to_directly_collated_count"] == 0
    assert issue["gua"] not in {c["gua"] for c in REFERENCE["najia_cases"]}
