"""Source consistency and refusal tests; synthetic cases are not predictions."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-source-calendar-caption-constraints-v1"
CENSUS = ROOT / "docs/validation/bazi-ditian-wholebook-census-v1"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


CHECK = module("caption_checker", "scripts/audit_bazi_source_calendar_captions.py")
CENSUS_AUDIT = module("caption_census", "scripts/audit_bazi_wholebook_census.py")


def read(path):
    return json.loads(path.read_text())


@pytest.fixture
def profile():
    return CHECK.read_bound(STUDY / "reference-profile-first.json")


def test_all_source_objects_and_original_failure_denominators_preserved():
    before = CHECK.read_bound(STUDY / "census-before-first.json")
    after = CENSUS_AUDIT.audit(CENSUS, ROOT)
    fixture = (
        ROOT
        / "tests/fixtures/bazi_source_calendar_caption_constraints_v1/reader-correction-first.json"
    )
    assert (
        CHECK.sha(fixture)
        == "e07062816486139ddb64dc124895f4d2c731b4f952671e16c5f6d87babf88109"
    )
    fix = read(fixture)
    expected = copy.deepcopy(before["resolved_source_claims"])
    assert expected[fix["claim_id"]][fix["field"]] == fix["first_value_retained"]
    expected[fix["claim_id"]][fix["field"]] = fix["corrected_value"]
    rescan_fixture = (
        ROOT
        / "tests/fixtures/bazi_source_rescan_collation_v1/planned-deltas-first.json"
    )
    assert (
        CHECK.sha(rescan_fixture)
        == "d6cb37fecde03817ef4478cd39bde9e3d3eaaa14ee2c7e4ec8a4aff32291cbd0"
    )
    rescan = read(rescan_fixture)
    expected_cases = copy.deepcopy(before["resolved_source_cases"])
    for case in expected_cases:
        case.update(rescan["case_patches"].get(case["case_id"], {}))
    for identity, patch in rescan["claim_patches"].items():
        expected[identity].update(patch)
    formula_path = (
        ROOT
        / "tests/fixtures/bazi_grouped_formula_positions_v1/expected-fields-first.json"
    )
    assert (
        CHECK.sha(formula_path)
        == "e9bdfad8fdbfc0a01dba1d2277103a446b167b6106b2ba5f5f8913d89b2e16aa"
    )
    formulas = read(formula_path)
    for case in expected_cases:
        case.update(formulas["case_patches"].get(case["case_id"], {}))
    for identity, patch in formulas["claim_patches"].items():
        expected[identity].update(patch)
    assert after["resolved_source_claims"] == expected
    assert after["resolved_source_cases"] == expected_cases
    assert after["resolved_source_cases_sha256"] == CENSUS_AUDIT.digest_value(
        expected_cases
    )
    assert fix["corrected_value"] == fix["first_value_retained"].replace(
        "土官令", "土当令"
    )
    for field in [
        "batches_sha256",
        "remaining_transcription_warnings",
        "transcription_warnings_retained",
    ]:
        assert after[field] == before[field]
    assert (
        after["source_case_input_corrections"][:8]
        == before["source_case_input_corrections"]
    )
    assert (
        after["source_case_claim_alignment_reviews"][:8]
        == before["source_case_claim_alignment_reviews"]
    )
    assert (
        after["source_case_input_questions_retained"]
        == before["remaining_case_input_questions"]
    )
    assert len(after["source_case_input_question_resolutions"]) == 1
    assert after["remaining_case_input_questions"] == [
        q
        for q in before["remaining_case_input_questions"]
        if q != rescan["resolved_original_question"]
    ]
    assert after["exact_body_labels"] == 26
    assert after["unknown_body_labels_retained"] == 532
    assert len(after["remaining_transcription_warnings"]) == 22
    assert len(after["remaining_case_input_questions"]) == 3
    assert not after["candidate_evaluation_allowed"]
    assert not after["whole_book_collection_frozen"]
    assert (
        after["resolved_source_claims"]["CENSUS-R836"]["expected_daymaster_strength"]
        == "强"
    )


def test_full_selection_keeps_both_failures_and_ambiguous_rules():
    result = CHECK.audit()
    assert result["all_source_claims_scanned"] == 1380
    assert result["all_literal_cases_scanned"] == 558
    rows = {r["claim_id"]: r for r in result["relative_term_rows"]}
    assert set(rows) == {
        "CENSUS-R522",
        "CENSUS-R523",
        "CENSUS-R526",
        "CENSUS-R759",
        "CENSUS-R836",
        "CENSUS-R1088",
    }
    assert all(
        rows[k]["parse"]["status"] == "unparsed" for k in ["CENSUS-R522", "CENSUS-R523"]
    )
    bad = rows["CENSUS-R836"]["case_constraints"][0]
    assert bad["case_id"] == "MAIN-C269"
    assert bad["status"] == "direct_order_contradiction"
    assert bad["literal_month_retained"] == "辛巳"
    assert bad["corrected_month"] is None
    for key in ["CENSUS-R526", "CENSUS-R759", "CENSUS-R1088"]:
        row = rows[key]["case_constraints"][0]
        assert row["status"] == "no_direct_endpoint_contradiction"
        assert not row["full_month_membership_proved"]
        assert row["modern_birth_instant"] is None
    era = result["era_caption_rows"]
    assert len(era) == 1 and era[0]["case_id"] == "MAIN-C159"
    assert era[0]["status"] == "year_caption_contradiction_even_with_adjacent_years"
    assert era[0]["nominal_era_year_ganzhi"] == "癸未"
    assert era[0]["literal_year_pillar_retained"] == "癸巳"
    assert era[0]["conservative_previous_nominal_next_year_candidates"] == [
        "壬午",
        "癸未",
        "甲申",
    ]
    assert era[0]["corrected_year_pillar"] is None
    assert not result["full_goal_complete"] and result["overall_score"] is None
    assert (
        result["source_questions_closed"]
        == result["original26_disagreements_closed"]
        == 0
    )


@pytest.mark.parametrize(
    "branch,start,end",
    [
        ("寅", "立春", "驚蟄"),
        ("卯", "驚蟄", "清明"),
        ("辰", "清明", "立夏"),
        ("巳", "立夏", "芒種"),
        ("午", "芒種", "小暑"),
        ("未", "小暑", "立秋"),
        ("申", "立秋", "白露"),
        ("酉", "白露", "寒露"),
        ("戌", "寒露", "立冬"),
        ("亥", "立冬", "大雪"),
        ("子", "大雪", "小寒"),
        ("丑", "小寒", "立春"),
    ],
)
def test_strict_endpoint_order_for_every_declared_month(profile, branch, start, end):
    for term, side, expected in [
        (start, "前", "direct_order_contradiction"),
        (start, "後", "no_direct_endpoint_contradiction"),
        (end, "前", "no_direct_endpoint_contradiction"),
        (end, "後", "direct_order_contradiction"),
    ]:
        parsed = CHECK.parse_relative(term + side + "一日", profile["start_terms"])
        result = CHECK.month_constraint("甲" + branch, parsed, profile)
        assert result["status"] == expected
        assert result["corrected_month"] is result["modern_birth_instant"] is None
        assert not result["full_month_membership_proved"]


@pytest.mark.parametrize(
    "text",
    [
        "立春後七日前者值戊土",
        "立春後八日十日內",
        "立夏後十天半",
        "立夏前五日左右",
        "立夏前五日至七日",
        "立夏前五日或十日",
        "立夏前五日內",
        "立夏前0日",
        "立夏後零日",
        "立夏前5.5日",
        "立夏後1/2日",
        "立夏後半日",
        "立夏前五日，立夏後十天",
        "立夏後十天以下",
        "立夏前二〇日",
        "年月未记",
    ],
)
def test_ambiguous_fractional_and_nonpositive_offsets_are_not_forced(profile, text):
    result = CHECK.parse_relative(text, profile["start_terms"])
    assert result["status"] == "unparsed"
    assert CHECK.month_constraint("辛巳", result, profile)["status"] == "unparsed"


def test_no_interval_duration_birth_instant_or_other_endpoint_inferred(profile):
    parsed = CHECK.parse_relative("立夏後九十九日", profile["start_terms"])
    result = CHECK.month_constraint("辛巳", parsed, profile)
    assert result["status"] == "no_direct_endpoint_contradiction"
    assert not result["full_month_membership_proved"]
    parsed = CHECK.parse_relative("立秋前一日", profile["start_terms"])
    assert CHECK.month_constraint("辛巳", parsed, profile)["status"] == "unadjudicated"
    assert CHECK.month_constraint(None, parsed, profile)["status"] == "unadjudicated"


def test_four_catalog_anchors_agree_but_do_not_determine_birth_date(profile):
    receipts = CHECK.read_bound(STUDY / "reference-receipts-first.json")
    cycle = CHECK.reference_cycle(STUDY, receipts, profile, ROOT)
    assert len(cycle) == len(set(cycle)) == 60
    assert cycle[:3] == ["甲子", "乙丑", "丙寅"] and cycle[-1] == "癸亥"
    for pillar in ["壬午", "癸未", "甲申"]:
        row = CHECK.era_constraint("乾隆二十八年四月十八日辰時", pillar, cycle, profile)
        assert row["status"] == "not_disproved_by_conservative_year_set"
        assert not row["birth_calendar_conversion_performed"]
        assert row["modern_birth_instant"] is None
    assert (
        CHECK.era_constraint("康熙二十八年", "癸巳", cycle, profile)["status"]
        == "unparsed"
    )
    bad = copy.deepcopy(profile)
    bad["museum_year_anchors"][0]["ganzhi"] = "癸巳"
    with pytest.raises(ValueError, match="collection title"):
        CHECK.reference_cycle(STUDY, receipts, bad, ROOT)


def test_reference_and_selection_tampering_cannot_turn_conflicts_green(tmp_path):
    profile = CHECK.read_bound(STUDY / "reference-profile-first.json")
    receipts = CHECK.read_bound(STUDY / "reference-receipts-first.json")
    changed = copy.deepcopy(receipts)
    changed[0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="byte binding"):
        CHECK.reference_cycle(STUDY, changed, profile, ROOT)
    path = tmp_path / "changed.json"
    path.write_text('{"full_scope": {"source_claims": 1}}')
    path.with_suffix(".sha256").write_text("0" * 64)
    with pytest.raises(ValueError, match="Frozen input changed"):
        CHECK.read_bound(path)
