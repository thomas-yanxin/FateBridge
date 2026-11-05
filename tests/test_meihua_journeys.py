"""Two selected-edition chapters; no actual travel, meeting or hazard oracle."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.meihua_journeys import journey_ruleset
from fatebridge.core.meihua_topics import topic_ruleset
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parent / "fixtures/meihua_journeys_v1"
READING = json.loads((FIXTURE / "source-reading.json").read_text())
GEOMETRY = json.loads((FIXTURE / "geometry384.json").read_text())
STRENGTH = json.loads((FIXTURE / "strength-contexts.json").read_text())
ANCHORS = [next(c for c in GEOMETRY if c["body_element"] == e) for e in "木火土金水"]
CLAUSES = [
    (topic, relation, quote, next(c for c in GEOMETRY if c["relation"] == relation))
    for topic, chapter in READING["chapters"].items()
    for relation, quote in chapter["clauses"].items()
]


def calculate(case, topic="travel", month=None, **extra):
    return calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic=topic,
        **({"season_month_branch": month} if month else {}),
        **extra,
    )


def test_source_and_manual_geometry_commitment_precede_new_implementation():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert not manifest["implementation_present"]
    assert not manifest["expected_values_from_production"]
    assert manifest["geometry_cases"] == 384
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("topic,relation,quote,case", CLAUSES)
def test_selected_literal_clause_and_original_body_paths(topic, relation, quote, case):
    result = calculate(case, topic)
    assert "error" not in result
    row = result["interpretation"]["topic_reading"]
    assert (row["body"], row["use"], row["relation"], row["quote"]) == (
        case["body"],
        case["use"],
        relation,
        quote,
    )
    assert row["body_fact_path"] == "meihua.body_trigram"
    assert row["use_fact_path"] == "meihua.use_trigram"
    assert (
        row["source_witness"]["original_pdf_indices"]
        == READING["chapters"][topic]["quote_indices"][relation]
    )
    assert (
        row["event_time"]
        is row["success_probability"]
        is row["real_outcome_verdict"]
        is None
    )
    assert not row["comparison_reading"]["used_to_override_selected_edition"]


@pytest.mark.parametrize("case", ANCHORS)
@pytest.mark.parametrize("month", [None, *STRENGTH])
def test_every_body_element_uses_its_own_known_or_unknown_strength(case, month):
    result = calculate(case, month=month)
    layer = result["interpretation"]["topic_reading"]["chapter_qualifications"]
    expected = (
        None
        if month is None
        else (
            "旺"
            if case["body_element"] == STRENGTH[month][0]
            else "衰" if case["body_element"] == STRENGTH[month][1] else "原文未定"
        )
    )
    pref = layer["body_strength_preference"]
    assert pref["actual_strength"] == expected
    assert pref["status"] == (
        "preference_met"
        if expected == "旺"
        else "preference_not_met" if expected == "衰" else "pending_known_strength"
    )
    assert not pref["is_travel_permission_or_safety_gate"]
    assert [
        (r["role"], r["trigram"], r["relation"]) for r in layer["auxiliary_preferences"]
    ] == [(r["role"], r["trigram"], r["relation"]) for r in case["roles"]]
    assert [
        r["symbolic_generation_present"] for r in layer["auxiliary_preferences"]
    ] == [r["relation"] == "用生体" for r in case["roles"]]


def test_complete_unclear_source_sentences_remain_pending_without_restored_dui():
    layer = calculate(ANCHORS[0])["interpretation"]["topic_reading"][
        "chapter_qualifications"
    ]
    assert (
        layer["selected_facsimile_complete_supplement"]
        == READING["chapters"]["travel"]["complete_selected_supplement"]
    )
    assert len(layer["unadjudicated_source_clauses"]) == 6
    assert all(
        r["status"] == "pending_source_scope"
        and not r["automatic_outcome_or_travel_mode_selected"]
        for r in layer["unadjudicated_source_clauses"]
    )
    last = layer["unadjudicated_source_clauses"][-1]
    assert last["quote"] == "主紛爭之應也" and last["actual_matching_roles"] is None
    assert all(
        layer[k] is None
        for k in [
            "event_time",
            "geographic_direction",
            "travel_mode_instruction",
            "hazard_verdict",
            "real_outcome",
        ]
    )
    assert (
        sum(
            layer["frequency_diagnostics"][
                "five_roles_original_static_body_once"
            ].values()
        )
        == 5
    )
    assert (
        sum(
            layer["frequency_diagnostics"]["six_base_mutual_changed_positions"].values()
        )
        == 6
    )


@pytest.mark.parametrize("topic", ["travel", "meeting"])
def test_count_candidates_use_their_own_geometry_and_evidence_paths(topic):
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
            "line_sum_basis": "raw_counts",
        },
        interpretation_topic=topic,
        season_month_branch="申",
    )
    assert "error" not in result
    rows = result["interpretation"]["casting_readings"]
    assert len(rows) == 2
    for i, row in enumerate(rows):
        expected = next(
            c
            for c in GEOMETRY
            if c["code"] == row["base_code"] and c["line"] == row["moving_line"]
        )
        clause = row["topic_clause"]
        assert (clause["body"], clause["use"], clause["relation"]) == (
            expected["body"],
            expected["use"],
            expected["relation"],
        )
        assert clause["body_fact_path"] == f"meihua.counting_variants.{i}.body_trigram"
        if topic == "travel":
            layer = clause["chapter_qualifications"]
            assert (
                layer["actual_role_occurrences"][0]["fact_path"]
                == f"meihua.counting_variants.{i}.body_trigram"
            )
            assert (
                layer["body_strength_preference"]["strength_fact_path"]
                == f"interpretation.casting_readings.{i}.seasonal_strength.trigrams.0.strength"
            )


@pytest.mark.parametrize("topic", ["travel", "meeting"])
def test_weather_context_cannot_supply_human_chapter_conditions(topic):
    assert "error" in calculate(ANCHORS[0], topic, weather_context={"season": "autumn"})


def test_new_profiles_cannot_mutate_old_twenty_clause_profile_or_cached_quotes():
    original = topic_ruleset()
    assert len(original["rules"]) == 20
    new = journey_ruleset()
    new["rules"][0]["quote"] = "伪造文本"
    assert journey_ruleset()["rules"][0]["quote"] != "伪造文本"
    assert topic_ruleset() == original


def test_question_keywords_do_not_select_new_classical_chapters():
    result = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "100111", "moving_line": 1},
        question="虚构工程示例：出行和谒见",
    )
    assert result["interpretation"]["interpretation_topic"] == "general"
    assert result["interpretation"].get("topic_reading") is None


@pytest.mark.parametrize("topic", ["travel", "meeting"])
def test_new_human_branches_keep_reported_motion_and_external_roles_separate(topic):
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
        },
        interpretation_topic=topic,
        observer_activity="walking",
        matter_scenario="favorable_matter",
        external_observations=[
            {
                "manifestation": "actual_water",
                "label": "虚构工程示例的水",
                "motion": "moving",
            }
        ],
    )
    assert "error" not in result
    layer = result["interpretation"]["external_omens"]
    assert layer["combined_outcome"] is None
    assert layer["observations"][0]["body"] == result["meihua"]["body_trigram"]["name"]
    for i, row in enumerate(result["interpretation"]["casting_readings"]):
        assert row["external_omens"]["observations"][0]["body"] == row["body"]
        assert (
            row["external_omens"]["observations"][0]["body_fact_path"]
            == f"meihua.counting_variants.{i}.body_trigram"
        )
