"""Frozen selected source and reused geometry controls, never outcome observations."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.meihua import meihua_stage_relations
from fatebridge.core.meihua_lost_property import (
    lost_property_qualifications,
    lost_property_ruleset,
)
from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_lost_property_v1"
PROFILE = json.loads((FIXTURE / "profile.json").read_text())
GEOMETRY = json.loads((FIXTURE / "geometry384.json").read_text())


def calculate(code="111111", line=1, **kwargs):
    return calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": code, "moving_line": line},
        interpretation_topic="lost_property",
        **kwargs,
    )


def resolve(result, path):
    for key in path.split("."):
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def test_source_freeze_precedes_implementation_and_retains_all_raw_witnesses():
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_text())
    assert not freeze["new_production_module_present"]
    assert not freeze["new_profile_present"]
    assert freeze["semantic_scope_not_uniquely_adjudicated"]
    assert freeze["reused_384_geometry_not_new_source_facts_or_observations"]
    for name, sha in freeze["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    assert lost_property_ruleset() == PROFILE
    copy = lost_property_ruleset()
    copy["rules"][0]["quote"] = "mutated"
    assert lost_property_ruleset() == PROFILE


@pytest.mark.parametrize("case", GEOMETRY, ids=lambda c: f"{c['code']}:{c['line']}")
def test_all_384_reused_geometries_bind_initial_and_changed_roles_separately(case):
    result = calculate(case["code"], case["line"])
    clause = result["interpretation"]["topic_reading"]
    initial, changed = case["rows"][0], case["rows"][3]
    expected = next(r for r in PROFILE["rules"] if r["relation"] == initial["relation"])
    assert (clause["body"], clause["use"], clause["relation"], clause["quote"]) == (
        case["body"],
        initial["trigram"],
        initial["relation"],
        expected["quote"],
    )
    location = clause["chapter_qualifications"]
    expected_location = next(
        r for r in PROFILE["location_rules"] if r["trigram"] == changed["trigram"]
    )
    assert location["selected_role"] == "changed_use"
    assert location["selected_trigram"] == changed["trigram"]
    assert resolve(result, location["trigram_fact_path"]) == changed["trigram"]
    assert resolve(result, location["moving_line_fact_path"]) == case["line"]
    assert location["quote"] == expected_location["quote"]
    assert location["direction_symbol"] == expected_location["direction_symbol"]
    assert location["place_symbols"] == expected_location["place_symbols"]
    assert (
        location["physical_reference_origin"]
        is location["numeric_bearing"]
        is location["geographic_coordinates"]
        is location["real_location"]
        is location["search_permission"]
        is location["loss_or_recovery_verified"]
        is location["event_time"]
        is None
    )
    assert (
        clause["event_time"]
        is clause["success_probability"]
        is clause["real_outcome_verdict"]
        is None
    )
    assert not location["selection_policy"]["unique_classical_scope_adjudicated"]
    assert location["selected_trigram"] in result["summary"]
    assert location["direction_symbol"] in result["summary"]


@pytest.mark.parametrize(
    "code,line,trigram,direction,position",
    [
        ("111111", 1, "巽", "东南", "lower"),
        ("111111", 4, "巽", "东南", "upper"),
        ("000000", 1, "震", "东方", "lower"),
        ("000000", 4, "震", "东方", "upper"),
    ],
)
def test_literal_anchors_do_not_choose_the_unchanged_half(
    code, line, trigram, direction, position
):
    result = calculate(code, line)
    loc = result["interpretation"]["topic_reading"]["chapter_qualifications"]
    assert (
        loc["selected_trigram"],
        loc["direction_symbol"],
        loc["trigram_fact_path"],
    ) == (trigram, direction, f"meihua.changed_hexagram.{position}.name")


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_count_candidates_keep_opposed_initial_clauses_and_distinct_location_paths(
    basis,
):
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
            "line_sum_basis": basis,
        },
        interpretation_topic="lost_property",
    )
    readings = result["interpretation"]["casting_readings"]
    expected = {
        "raw_counts": (1, "体克用", "體尅用可尋遲得", "巽", "东南"),
        "trigram_numbers": (5, "用克体", "用尅體不可尋", "乾", "西北"),
    }
    for i, row in enumerate(readings):
        clause = row["topic_clause"]
        loc = clause["chapter_qualifications"]
        assert (
            row["moving_line"],
            clause["relation"],
            clause["quote"],
            loc["selected_trigram"],
            loc["direction_symbol"],
        ) == expected[row["line_sum_basis"]]
        assert loc["trigram_fact_path"].startswith(f"meihua.counting_variants.{i}.")
        assert resolve(result, loc["trigram_fact_path"]) == loc["selected_trigram"]
        assert resolve(result, loc["moving_line_fact_path"]) == row["moving_line"]
        assert loc["summary"] in result["summary"]
    assert result["interpretation"]["casting_comparison"][
        "changed_lost_location_trigrams"
    ] == ["乾", "巽"]
    assert (
        result["interpretation"]["casting_comparison"]["single_real_location"] is None
    )
    selected = next(row for row in readings if row["selected"])
    assert (
        result["interpretation"]["topic_reading"]["clause_id"]
        == selected["topic_clause"]["clause_id"]
    )


def test_source_variants_and_reported_loss_are_not_silently_rewritten():
    result = calculate(question="已经确认丢失了钥匙")
    clause = result["interpretation"]["topic_reading"]
    assert clause["quote"] == "體用比和物不失矣"
    assert "不能否认已报遗失" in result["summary"]
    loc = clause["chapter_qualifications"]
    assert "舟車" in loc["quote"] and "舟居" in loc["comparison_reading"]["quote"]
    assert not loc["comparison_reading"]["used_to_override_selected_edition"]
    kun = next(r for r in PROFILE["location_rules"] if r["trigram"] == "坤")
    assert "倉廩" in kun["quote"] and "倉稟" in kun["comparison_reading"]["quote"]


def test_questions_do_not_select_the_chapter_and_weather_context_stays_exclusive():
    result = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "111111", "moving_line": 1},
        question="失物在西北吗",
    )
    assert result["interpretation"]["interpretation_topic"] == "general"
    with pytest.raises(ValueError, match="weather_context"):
        MeihuaInterpretationOptions(
            interpretation_topic="lost_property", weather_context={}
        )


def test_mismatched_stage_path_fails_instead_of_silently_copying_another_candidate():
    cast = calculate()["meihua"]
    stages = meihua_stage_relations(cast)
    stages[-1]["fact_path"] = "meihua.changed_hexagram.upper"
    with pytest.raises(ValueError, match="changed use"):
        lost_property_qualifications(cast, stages, fact_prefix="meihua")
