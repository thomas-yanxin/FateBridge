"""Marriage source variants, family roles, unknown strength and own candidates."""

import hashlib
import json
from copy import deepcopy

import pytest

from fatebridge.core.meihua_marriage import marriage_qualifications, marriage_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.meihua_marriage_reference import CASES, FOLDER, validate


def test_source_and_cases_were_frozen_before_new_production():
    manifest = json.loads((FOLDER / "manifest.json").read_bytes())
    assert not manifest["new_production_implemented_before_freeze"]
    assert (
        manifest["reused_geometry_count"] == 384 and manifest["rule_contexts"] == 4992
    )
    assert manifest["unique_real_world_observations"] == 0
    assert (
        len(CASES) == len({(r["code"], r["line"], r["month"]) for r in CASES}) == 4992
    )
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize(
    "case", CASES, ids=lambda r: f"{r['code']}-{r['line']}-{r['month']}"
)
def test_all_4992_reused_geometry_and_month_contexts_preserve_own_clauses_unknowns_and_source_variants(
    case,
):
    result = calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic="marriage",
        season_month_branch=case["month"],
    )
    validate(result, case["month"])


@pytest.mark.parametrize("month", [None, *"子丑寅卯辰巳午未申酉戌亥"])
@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_candidate_body_and_use_swap_preserves_each_family_strength_and_own_clause(
    month, basis
):
    manual = json.loads((FOLDER / "manual-candidate-probe.json").read_bytes())
    result = calculate_meihua_cast(
        casting={**manual["casting"], "line_sum_basis": basis},
        interpretation_topic="marriage",
        season_month_branch=month,
    )
    validate(result, month)
    expected_by_basis = {row["basis"]: row for row in manual["candidates"]}
    rows = result["interpretation"]["casting_readings"]
    assert {row["line_sum_basis"] for row in rows} == set(expected_by_basis)
    assert rows[0]["line_sum_basis"] == basis and rows[0]["selected"] is True
    for row in rows:
        expected = expected_by_basis[row["line_sum_basis"]]
        assert (
            row["body"],
            row["use"],
            row["moving_line"],
            row["body_use_relation"],
        ) == (expected["body"], expected["use"], expected["line"], expected["relation"])
        assert row["topic_clause"]["quote"] in row["traditional_judgement"]


def test_initial_bihe_is_independent_of_later_unadjudicated_bili():
    result = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "000000", "moving_line": 1},
        interpretation_topic="marriage",
    )
    clause = result["interpretation"]["topic_reading"]
    assert clause["quote"] == "體用比和婚姻吉利"
    assert (
        clause["chapter_qualifications"]["bili_supplement"]["source_relation_condition"]
        is None
    )
    validate(result)


@pytest.mark.parametrize("month", ["申", "巳", None])
def test_changing_chapter_never_recasts_geometry_or_uses_question_words_as_context(
    month,
):
    args = {
        "casting": {"method": "existing", "hexagram_code": "100111", "moving_line": 1},
        "season_month_branch": month,
        "question": "结婚，求婚，婚姻",
    }
    baseline = calculate_meihua_cast(**args)
    result = calculate_meihua_cast(**args, interpretation_topic="marriage")
    assert baseline["interpretation"]["interpretation_topic"] == "general"
    for key in [
        "seed",
        "base_hexagram",
        "changed_hexagram",
        "mutual_hexagram",
        "body_trigram",
        "use_trigram",
        "stage_relations",
        "seasonal_strength",
        "calendar_policy",
        "rule_trace",
    ]:
        assert baseline["meihua"][key] == result["meihua"][key]
    validate(result, month)


@pytest.mark.parametrize("hour", [0, 23])
def test_calendar_entry_preserves_the_actual_clock_and_original_cast(hour):
    args = {
        "analysis_year": 2026,
        "analysis_month": 2,
        "analysis_day": 16,
        "analysis_hour": hour,
        "analysis_timezone": "Asia/Shanghai",
    }
    baseline = calculate_meihua_analysis(**args)
    result = calculate_meihua_analysis(**args, interpretation_topic="marriage")
    for key in [
        "seed",
        "base_hexagram",
        "changed_hexagram",
        "mutual_hexagram",
        "body_trigram",
        "use_trigram",
        "stage_relations",
        "seasonal_strength",
        "calendar_policy",
        "rule_trace",
    ]:
        assert result["meihua"][key] == baseline["meihua"][key]
    validate(result, result["meihua"]["seasonal_strength"]["month_branch"])


@pytest.mark.parametrize(
    "mutation",
    [
        "bili_emended",
        "bili_auto",
        "unknown_false",
        "borrowed_strength",
        "family_swap",
        "or_to_and",
        "borrowed_summary",
        "actual_traits",
    ],
)
def test_independent_reference_rejects_wrong_source_scope_or_borrowed_candidate(
    mutation,
):
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 10,
            "second_count": 3,
            "hour_branch": "子",
        },
        interpretation_topic="marriage",
        season_month_branch="辰",
    )
    q = result["interpretation"]["casting_readings"][0]["topic_clause"][
        "chapter_qualifications"
    ]
    if mutation == "bili_emended":
        q["bili_supplement"]["quote"] = "若體用比和則彼此相就良配無疑"
    elif mutation == "bili_auto":
        q["bili_supplement"]["source_relation_condition"] = True
    elif mutation == "unknown_false":
        q["strength_clauses"][0]["wang_condition"] = False
    elif mutation == "borrowed_strength":
        q["strength_clauses"][0][
            "trigram_fact_path"
        ] = "meihua.counting_variants.1.body_trigram"
    elif mutation == "family_swap":
        q["family_frame"]["actual_roles"].reverse()
    elif mutation == "or_to_and":
        q["generation_relation_atoms"][0]["alternatives_combined_as_conjunction"] = True
    elif mutation == "actual_traits":
        q["actual_partner_traits"] = {"face": "predicted"}
    else:
        result["interpretation"]["casting_readings"][0]["traditional_judgement"] = (
            result["interpretation"]["casting_readings"][1]["traditional_judgement"]
        )
    with pytest.raises(AssertionError):
        validate(result, "辰")


def test_cached_profile_is_returned_as_an_isolated_copy():
    profile = marriage_ruleset()
    profile["rules"][0]["quote"] = "forged"
    assert marriage_ruleset()["rules"][0]["quote"] == "體尅用可成但成之遲"


def test_strength_rows_from_another_candidate_are_rejected_at_domain_boundary():
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 10,
            "second_count": 3,
            "hour_branch": "子",
        },
        interpretation_topic="marriage",
        season_month_branch="申",
    )
    row = result["interpretation"]["casting_readings"][0]
    other = result["interpretation"]["casting_readings"][1]
    with pytest.raises(ValueError, match="this candidate"):
        marriage_qualifications(
            result["meihua"]["counting_variants"][0],
            row["stage_relations"],
            other["seasonal_strength"],
            fact_prefix="meihua.counting_variants.0",
            strength_prefix="interpretation.casting_readings.0.seasonal_strength",
        )
