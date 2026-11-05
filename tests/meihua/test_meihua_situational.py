"""Literal source lookups and candidate fidelity, never empirical weather cases."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.meihua_situational import _reading
from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.core.requests.meihua_situational import MeihuaResponseContext
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_situational_v1"
REF = json.loads((FIXTURE / "expected-lookup.json").read_bytes())
CAST = {"method": "existing", "hexagram_code": "111101", "moving_line": 1}
BASE = {"label": "虚构同次现场工程示例", "same_casting_episode_confirmed": True}
CASES = [
    (body, family, category)
    for body in REF["elements"]
    for family in ("directions", "weather", "setting", "human")
    for category in REF[family]
]


def context(family, category):
    if family == "directions":
        return {
            **BASE,
            "querent_position": {
                "direction": category,
                "reference_label": "虚构占者所在点",
            },
        }
    return {**BASE, family: [category]}


def normalized(value):
    return MeihuaResponseContext.model_validate(value).model_dump(mode="json")


def at_path(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def test_frozen_literals_and_precode_correction_are_not_production_expectations():
    manifest = json.loads((FIXTURE / "source-files.json").read_bytes())
    assert not manifest["implementation_present_at_reference_freeze"]
    assert not manifest["new_lookup_values_from_production"]
    assert manifest["new_category_contexts"] == len(CASES) == 184
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    source = json.loads((FIXTURE / "source-reading.json").read_bytes())
    assert "所坐立之方卦" in source["quotes"]["direction"]
    assert source["comparison"]["transcription_direction"] == "所坐立之方位"
    assert source["quotes"]["intro_list"].count("應") == 10


@pytest.mark.parametrize("body,family,category", CASES)
def test_all_eight_bodies_and_twenty_three_source_categories(body, family, category):
    result = _reading(
        {"name": body, "element": REF["elements"][body]},
        normalized(context(family, category)),
        body_path="fixture.body",
        context_path="fixture.context",
    )
    assert len(result["observations"]) == 1
    row = result["observations"][0]
    expected = (
        [REF[family][category][0]] if family == "directions" else REF[family][category]
    )
    assert [r["trigram"] for r in row["trigram_candidates"]] == expected
    for candidate in row["trigram_candidates"]:
        element = REF["elements"][candidate["trigram"]]
        relation = REF["relation_matrix"][REF["elements"][body]][element]
        assert candidate["element"] == element
        assert candidate["raw_relation_to_original_body"] == relation
        assert candidate["direction_clause_preference"] == (
            REF["direction_preferences"][relation] if family == "directions" else None
        )
    if family == "weather":
        assert row["exact_weather_pair"]["matches_actual_body"] == (
            body == REF["weather_exact_preferred"][category]
        )
    if family == "human":
        assert row["source_symbolic_valence"] == REF["human_symbolic_valence"].get(
            category
        )
    if family == "weather" and category == "thunder":
        clause = row["unresolved_source_relation_clause"]
        assert clause["selected_quote"] == "體見雷爲比和"
        assert clause["comparison_quote"] == "火見雷為比和"
        assert clause["selected_subject"] == "unresolved"
        assert not clause["used_to_override_five_element_relation"]
    assert (
        result["ten_response_synthesis"]
        is result["event_time"]
        is result["real_outcome"]
        is result["success_probability"]
        is None
    )
    assert result["independent_verified_observations"] == 0
    assert not result["changes_casting_or_registered_study_eligibility"]


def test_fire_and_thunder_keep_generation_with_unresolved_source_subject():
    out = calculate_meihua_cast(
        casting=CAST, response_context=context("weather", "thunder")
    )
    row = out["interpretation"]["situational_responses"]["observations"][0]
    assert row["body"]["trigram"] == "离"
    assert row["trigram_candidates"][0]["raw_relation_to_original_body"] == "用生体"
    assert not row["exact_weather_pair"]["matches_actual_body"]
    assert row["unresolved_source_relation_clause"]["selected_subject"] == "unresolved"
    assert "主语接续未裁定" in out["summary"]


def test_unknown_context_is_distinct_from_no_context_and_absent_omens():
    omitted = calculate_meihua_cast(casting=CAST, question="晴明，老人北来，竹林")
    assert "situational_responses" not in omitted["interpretation"]
    provided = calculate_meihua_cast(casting=CAST, response_context=BASE)
    layer = provided["interpretation"]["situational_responses"]
    assert layer["status"] == "pending_reported_categories"
    assert len(layer["uncollected_families"]) == 4
    assert not layer["observations"]
    assert "缺项" in layer["summary"]


def test_multiple_observations_neither_vote_nor_silently_choose_one_trigram():
    value = {
        **BASE,
        "weather": ["clear", "rain_or_snow"],
        "setting": ["bamboo_woodland", "metal_place", "earth_or_tiles"],
        "human": ["heard_laughter", "weeping_encountered"],
    }
    out = calculate_meihua_cast(casting=CAST, response_context=value)
    rows = out["interpretation"]["situational_responses"]["observations"]
    assert len(rows) == 7
    assert [[r["trigram"] for r in row["trigram_candidates"]] for row in rows[2:5]] == [
        ["震", "巽"],
        ["乾", "兑"],
        ["坤", "艮"],
    ]
    assert [r["source_symbolic_valence"] for r in rows[-2:]] == [
        "source_joy_symbol",
        "source_sorrow_symbol",
    ]
    assert all(row["combined_effect"] is None for row in rows)
    assert (
        out["interpretation"]["situational_responses"]["ten_response_synthesis"] is None
    )


def test_each_ambiguous_count_candidate_uses_own_actual_body_and_real_paths():
    out = calculate_meihua_cast(
        casting={"method": "object_count", "count": 11, "hour_branch": "丑"},
        response_context={
            **context("directions", "west"),
            "weather": ["thunder"],
            "human": ["young_girl"],
        },
    )
    assert len(out["interpretation"]["casting_readings"]) == 2
    assert len({r["body"] for r in out["interpretation"]["casting_readings"]}) == 2
    for index, reading in enumerate(out["interpretation"]["casting_readings"]):
        for row in reading["situational_responses"]["observations"]:
            assert row["body"]["trigram"] == reading["body"]
            assert at_path(out, row["body"]["fact_path"])["name"] == reading["body"]
            assert (
                row["body"]["fact_path"]
                == f"meihua.counting_variants.{index}.body_trigram"
            )
            assert at_path(out, row["reported_fact_path"]) == row["category"]


@pytest.mark.parametrize(
    "topic",
    ["general", "planning", "reputation", "wealth", "transaction", "travel", "meeting"],
)
def test_all_human_topics_accept_reported_context_without_recasting(topic):
    baseline = calculate_meihua_cast(casting=CAST, interpretation_topic=topic)
    changed = calculate_meihua_cast(
        casting=CAST,
        interpretation_topic=topic,
        response_context=context("setting", "metal_place"),
    )
    assert changed["meihua"] == baseline["meihua"]
    assert (
        changed["interpretation"]["situational_responses"]["status"]
        == "reported_categories_mapped"
    )


def test_time_input_retains_context_and_uses_its_actual_body():
    inputs = dict(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=26,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
    )
    baseline = calculate_meihua_analysis(**inputs)
    out = calculate_meihua_analysis(
        **inputs, response_context=context("weather", "rain_or_snow")
    )
    assert out["meihua"] == baseline["meihua"]
    row = out["interpretation"]["situational_responses"]["observations"][0]
    assert at_path(out, row["reported_fact_path"]) == "rain_or_snow"
    assert at_path(out, row["body"]["fact_path"])["name"] == row["body"]["trigram"]


@pytest.mark.parametrize(
    "change",
    [
        {"label": " "},
        {"same_casting_episode_confirmed": False},
        {"same_casting_episode_confirmed": "true"},
        {"same_casting_episode_confirmed": 1},
        {"weather": []},
        {"weather": ["thunder", "thunder"]},
        {"weather": ["dry_day"]},
        {"setting": ["living_tree"]},
        {"human": ["young_person"]},
        {"querent_position": {"direction": "N", "reference_label": "origin"}},
        {"querent_position": {"direction": "north", "reference_label": " "}},
        {"future_date": "2027-01-01"},
    ],
)
def test_unknown_categories_fake_confirmations_and_duplicate_votes_fail(change):
    with pytest.raises(ValidationError):
        MeihuaResponseContext.model_validate({**BASE, **change})


@pytest.mark.parametrize(
    "model,extra",
    [
        (MeihuaCastRequest, {"casting": CAST}),
        (
            MeihuaAnalysisRequest,
            {
                "analysis_year": 2026,
                "analysis_month": 10,
                "analysis_day": 26,
                "analysis_hour": 12,
            },
        ),
    ],
)
def test_weather_topic_and_contradictory_quiet_facts_rejected(model, extra):
    value = context("human", "heard_laughter")
    with pytest.raises(ValidationError):
        model.model_validate(
            {**extra, "interpretation_topic": "weather", "response_context": value}
        )
    with pytest.raises(ValidationError):
        model.model_validate(
            {
                **extra,
                "observation_context": {"label": "same fixture", "nothing_heard": True},
                "response_context": value,
            }
        )
    with pytest.raises(ValidationError):
        model.model_validate(
            {
                **extra,
                "observation_context": {
                    "label": "same fixture",
                    "quiet_room": True,
                    "nothing_heard": True,
                    "nothing_seen": True,
                },
                "response_context": context("weather", "wind"),
            }
        )


def test_uncollected_categories_and_single_unknown_modality_do_not_invent_contradictions():
    quiet = {
        "label": "fixture",
        "quiet_room": True,
        "nothing_heard": True,
        "nothing_seen": True,
    }
    out = calculate_meihua_cast(
        casting=CAST, observation_context=quiet, response_context=BASE
    )
    assert "error" not in out
    out = calculate_meihua_cast(
        casting=CAST,
        observation_context={"label": "fixture", "nothing_heard": True},
        response_context=context("human", "weeping_encountered"),
    )
    assert "error" not in out


def test_source_and_input_mutations_do_not_poison_cached_profile():
    value = context("setting", "bamboo_woodland")
    original = copy.deepcopy(value)
    out = calculate_meihua_cast(casting=CAST, response_context=value)
    out["interpretation"]["situational_responses"]["ruleset"]["tables"]["setting"][
        "bamboo_woodland"
    ].clear()
    assert value == original
    assert calculate_meihua_cast(casting=CAST, response_context=value)[
        "interpretation"
    ]["situational_responses"]["observations"][0]["trigram_candidates"]


def test_weather_negative_result_and_registered_denominator_unchanged():
    out = calculate_meihua_cast(casting=CAST, interpretation_topic="weather")
    assert "situational_responses" not in out["interpretation"]
    primary = out["interpretation"]["weather"]["research_validation"][
        "current_profile_study"
    ]["primary"]
    assert (
        primary["cohort_days"],
        primary["correct"],
        primary["all_dates_always_dry_correct"],
        primary["primary_full_cohort_gate_met"],
    ) == (273, 29, 158, False)


@pytest.mark.parametrize("body", list(REF["elements"]))
@pytest.mark.parametrize("kind", ["rain", "snow"])
def test_precipitation_supplement_separates_mapping_and_exact_rain_preference(
    body, kind
):
    supplement = json.loads(
        (FIXTURE / "precipitation-distinction-supplement.json").read_bytes()
    )
    freeze = json.loads((FIXTURE / "precipitation-supplement-freeze.json").read_bytes())
    assert (
        hashlib.sha256(
            (FIXTURE / "precipitation-distinction-supplement.json").read_bytes()
        ).hexdigest()
        == freeze["sha256"]
    )
    assert not freeze["fix_present"]
    layer = _reading(
        {"name": body, "element": REF["elements"][body]},
        normalized(context("weather", kind)),
        body_path="fixture.body",
        context_path="fixture.context",
    )
    row = layer["observations"][0]
    assert (
        [r["trigram"] for r in row["trigram_candidates"]]
        == supplement["mapping"][kind]
        == ["坎"]
    )
    assert (
        row["trigram_candidates"][0]["raw_relation_to_original_body"]
        == REF["relation_matrix"][REF["elements"][body]]["水"]
    )
    if kind == "snow":
        assert row["exact_weather_pair"] is None
    else:
        assert row["exact_weather_pair"]["clause_applies_to_reported_conditions"] is (
            body == "坎"
        )
    assert layer["ten_response_synthesis"] is None


@pytest.mark.parametrize("body", list(REF["elements"]))
def test_umbrella_precipitation_never_claims_the_exact_rain_predicate_true(body):
    layer = _reading(
        {"name": body, "element": REF["elements"][body]},
        normalized(context("weather", "rain_or_snow")),
        body_path="fixture.body",
        context_path="fixture.context",
    )
    pair = layer["observations"][0]["exact_weather_pair"]
    assert pair["matches_actual_body"] is (body == "坎")
    assert pair["source_weather_condition_status"] == "pending_rain_vs_snow"
    assert pair["clause_applies_to_reported_conditions"] is (
        None if body == "坎" else False
    )
