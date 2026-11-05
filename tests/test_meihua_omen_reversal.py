"""Two source examples with actual bodies; no real outcomes or safety judgement."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.meihua_omen_reversal import _reading
from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parent / "fixtures/meihua_omen_reversal_v1"
REF = json.loads((FIXTURE / "expected-cases.json").read_bytes())
GEOMETRY = json.loads((FIXTURE / "geometry384-reused.json").read_bytes())
TOPICS = [
    "general",
    "planning",
    "reputation",
    "wealth",
    "transaction",
    "travel",
    "meeting",
]
KINDS = ["gold_silver_treasure", "weapon"]


def at(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def cast(body):
    g = next(row for row in GEOMETRY if row["body"] == body)
    return {"method": "existing", "hexagram_code": g["code"], "moving_line": g["line"]}


def observation(kind):
    return {"manifestation": kind, "label": "虚构明确已报原文类别工程例"}


def test_independent_literal_body_cases_and_draft_source_precede_implementation():
    m = json.loads((FIXTURE / "manifest.json").read_bytes())
    assert not m["implementation_present_at_reference_freeze"]
    assert not m["new_expected_values_from_production"]
    for name, digest in m["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert REF["new_body_category_contexts"] == 16


@pytest.mark.parametrize("body", list(REF["body_elements"]))
@pytest.mark.parametrize("kind", KINDS)
def test_two_explicit_symbols_on_all_eight_actual_original_bodies(body, kind):
    out = calculate_meihua_cast(
        casting=cast(body), external_observations=[observation(kind)]
    )
    assert "error" not in out
    external = out["interpretation"]["external_omens"]
    layer = external["body_relative_symbols"]
    row = layer["records"][0]
    expected = REF[kind]
    matched = body in expected["qualified_bodies"]
    assert row["original_body"]["trigram"] == body
    assert (
        row["raw_relation_to_body"]
        == REF["relation_to_metal"][REF["body_elements"][body]]
    )
    assert row["common_source_symbol"] == expected["common_symbol"]
    assert row["selected_body_condition"]["matches_actual_body"] is matched
    assert row["qualified_source_symbol"] == (
        expected["qualified_symbol"] if matched else None
    )
    assert at(out, row["reported_fact_path"]) == kind
    assert at(out, row["relation_fact_path"]) == row["raw_relation_to_body"]
    assert at(out, row["original_body"]["fact_path"])["name"] == body
    assert (
        at(out, row["material_qualification_fact_path"])
        == "not_addressed_in_selected_pairs"
    )
    assert external["observations"][0]["mapping_ruleset_id"] == layer["ruleset_id"]
    assert not external["observations"][0]["unique_external_trigram_assigned"]
    assert not layer["not_inauspicious_promoted_to_auspicious"]
    assert not layer["material_qualification_overridden"]
    assert (
        layer["full_internal_external_synthesis"]
        is layer["real_outcome"]
        is layer["event_time"]
        is layer["success_probability"]
        is None
    )
    assert layer["independent_verified_observations"] == 0


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize(
    "case",
    json.loads((FIXTURE / "candidate-arithmetic-supplement.json").read_bytes())[
        "cases"
    ],
)
def test_every_human_branch_keeps_both_symbols_and_each_candidate_own_body(topic, case):
    out = calculate_meihua_cast(
        casting={
            "method": "object_count",
            "count": case["count"],
            "hour_branch": case["hour_branch"],
        },
        interpretation_topic=topic,
        external_observations=[observation(k) for k in KINDS],
    )
    candidates = out["interpretation"]["casting_readings"]
    assert len(candidates) == 2 and len({r["body"] for r in candidates}) == 2
    statuses = []
    for index, candidate in enumerate(candidates):
        layer = candidate["external_omens"]["body_relative_symbols"]
        assert [r["manifestation"] for r in layer["records"]] == KINDS
        for row in layer["records"]:
            assert row["original_body"]["trigram"] == candidate["body"]
            assert (
                row["original_body"]["fact_path"]
                == f"meihua.counting_variants.{index}.body_trigram"
            )
            assert (
                at(out, row["original_body"]["fact_path"])["name"] == candidate["body"]
            )
            assert at(out, row["reported_fact_path"]) == row["manifestation"]
        statuses.append(
            layer["records"][1]["selected_body_condition"]["matches_actual_body"]
        )
    assert [r["body"] for r in candidates] == case["expected_bodies"]
    assert statuses == case["expected_weapon_body_matches"]


def test_common_valued_and_bad_symbols_never_become_unqualified_current_outcomes():
    for kind, body, value in [
        ("gold_silver_treasure", "震", "not_auspicious_symbol"),
        ("weapon", "坎", "not_inauspicious_symbol"),
    ]:
        out = calculate_meihua_cast(
            casting=cast(body), external_observations=[observation(kind)]
        )
        row = out["interpretation"]["external_omens"]["body_relative_symbols"][
            "records"
        ][0]
        assert row["qualified_source_symbol"] == value
        assert row["real_outcome"] is None
    assert "不替换实物资格" in out["summary"]


def test_old_material_exceptions_remain_and_generic_categories_do_not_infer_new_class():
    records = [
        observation(k)
        for k in [
            "metal_ornament_or_utensil",
            "sharp_metal_tool",
            "gold_silver_treasure",
            "weapon",
        ]
    ]
    records[0]["label"] = "金银宝与兵器字样不解析成新类别"
    out = calculate_meihua_cast(casting=cast("震"), external_observations=records)
    layer = out["interpretation"]["external_omens"]
    assert layer["observations"][0]["qualification"] == "no_substantive_control"
    assert layer["observations"][1]["qualification"] == "substantive_control"
    assert [r["record_index"] for r in layer["body_relative_symbols"]["records"]] == [
        2,
        3,
    ]
    old = calculate_meihua_cast(casting=cast("震"), external_observations=records[:2])
    assert "body_relative_symbols" not in old["interpretation"]["external_omens"]


def test_time_entry_uses_actual_body_and_source_paths():
    out = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=26,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        external_observations=[observation("weapon")],
    )
    row = out["interpretation"]["external_omens"]["body_relative_symbols"]["records"][0]
    assert (
        at(out, row["original_body"]["fact_path"])["name"]
        == row["original_body"]["trigram"]
    )
    assert at(out, row["relation_fact_path"]) == row["raw_relation_to_body"]


@pytest.mark.parametrize(
    "change", ["body", "relation", "kind", "body_path", "record_index", "element"]
)
def test_wrong_body_relation_or_record_binding_is_rejected(change):
    out = calculate_meihua_cast(
        casting=cast("坎"), external_observations=[observation("weapon")]
    )
    external = copy.deepcopy(out["interpretation"]["external_omens"])
    row = external["observations"][0]
    key, value = {
        "body": ("body", "震"),
        "relation": ("raw_relation_to_body", "用克体"),
        "kind": ("manifestation", "gold_silver_treasure"),
        "body_path": ("body_fact_path", "meihua.counting_variants.0.body_trigram"),
        "record_index": ("record_index", 1),
        "element": ("body_element", "火"),
    }[change]
    row[key] = value
    with pytest.raises(ValueError):
        _reading(
            out["meihua"]["body_trigram"],
            external,
            external_path="interpretation.external_omens",
            body_path="meihua.body_trigram",
        )


@pytest.mark.parametrize("kind", KINDS)
def test_weather_and_full_quiet_context_cannot_accept_reported_external_items(kind):
    base = {"casting": cast("坎"), "external_observations": [observation(kind)]}
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate({**base, "interpretation_topic": "weather"})
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate(
            {
                **base,
                "observation_context": {
                    "label": "same cast",
                    "quiet_room": True,
                    "nothing_heard": True,
                    "nothing_seen": True,
                },
            }
        )


def test_cached_profile_and_original_input_are_not_mutated():
    values = [observation("weapon")]
    before = copy.deepcopy(values)
    out = calculate_meihua_cast(casting=cast("坎"), external_observations=values)
    out["interpretation"]["external_omens"]["body_relative_symbols"]["ruleset"][
        "cases"
    ]["weapon"]["qualified_bodies"].clear()
    assert values == before
    assert (
        calculate_meihua_cast(casting=cast("坎"), external_observations=values)[
            "interpretation"
        ]["external_omens"]["body_relative_symbols"]["records"][0][
            "qualified_source_symbol"
        ]
        == "not_inauspicious_symbol"
    )
