"""Text-count witnesses and declared arithmetic never choose a winning cast."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.meihua_casting import cast_explicit_meihua
from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.transports import SPECS, business, rest, surface_calls

REFERENCE = Path(__file__).parents[1] / "fixtures/meihua_text_count_v1"
CASES = json.loads((REFERENCE / "cases.json").read_text())["cases"]


def parameters(case, basis="raw_counts"):
    return {
        "method": "text_count",
        "character_count": case["count"],
        "text_basis": case["text_basis"],
        "line_sum_basis": basis,
    }


def test_six_hand_probes_and_selected_source_bytes_are_preserved():
    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    assert manifest["precedes_implementation"]
    for group in ["files", "references"]:
        for name, digest in manifest[group].items():
            path = (REFERENCE / name).resolve()
            assert path.is_relative_to(REFERENCE.parent.resolve())
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert len(CASES) == 6


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_declared_count_basis_keeps_hand_derived_geometry_and_body(case, basis):
    output = calculate_meihua_cast(casting=parameters(case, basis))
    cast = output["meihua"]
    expected = case["raw" if basis == "raw_counts" else "reduced"]
    assert cast["base_hexagram"]["binary_code"] == case["base"]
    assert cast["seed"]["upper_number"] == case["upper"]
    assert cast["seed"]["lower_number"] == case["lower"]
    assert cast["seed"]["moving_line"] == expected["line"]
    assert cast["changed_hexagram"]["binary_code"] == expected["changed"]
    assert cast["mutual_hexagram"]["binary_code"] == expected["mutual"]
    assert cast["body_trigram"]["name"] == expected["body"]
    assert cast["use_trigram"]["name"] == expected["use"]
    assert cast["seed"]["line_sum_basis"] == basis
    assert "hour_branch" not in cast["seed"]
    diverges = case["raw"]["line"] != case["reduced"]["line"]
    assert len(cast["counting_variants"]) == (2 if diverges else 0)
    assert cast["seed"]["text_count_basis"]["text_basis"] == case["text_basis"]
    assert (
        cast["seed"]["text_count_basis"]["exact_facsimile_upper_bound_adjudicated"]
        is False
    )
    if diverges:
        assert (
            output["interpretation"]["status"] == "conditional_on_declared_convention"
        )
        assert "原字数" in output["summary"] and "原声数" not in output["summary"]


def test_hundred_plus_requires_an_explicit_textual_basis_and_remains_conditional():
    with pytest.raises(ValidationError):
        MeihuaCastRequest(casting={"method": "text_count", "character_count": 101})
    output = calculate_meihua_cast(casting=parameters(CASES[4]))
    assert output["interpretation"]["status"] == "conditional_on_textual_extent"
    assert (
        output["meihua"]["evidence_scope"]["calculation_status"]
        == "conditional_on_textual_extent"
    )
    assert "软件扩展" in output["summary"]
    scope = output["meihua"]["seed"]["text_count_basis"]
    assert (
        scope["range_status"] == "software_extension_exact_textual_extent_unadjudicated"
    )
    assert scope["selected_wording"] == "百餘字"


@pytest.mark.parametrize("value", [10, 0, True, 17.0, "17", 1_000_001])
def test_invalid_or_oversized_software_counts_do_not_become_ancient_rules(value):
    with pytest.raises(ValidationError):
        MeihuaCastRequest(
            casting={
                "method": "text_count",
                "character_count": value,
                "text_basis": "nlc1925_selected_span",
            }
        )


def test_large_software_extension_is_not_a_source_range_certification():
    output = calculate_meihua_cast(
        casting={
            "method": "text_count",
            "character_count": 1_000_000,
            "text_basis": "nlc1925_selected_span",
        }
    )
    assert output["meihua"]["seed"]["moving_line"] == 4
    scope = output["meihua"]["seed"]["text_count_basis"]
    assert scope["software_count_guard"] == 1_000_000
    assert (
        scope["range_status"] == "software_extension_exact_textual_extent_unadjudicated"
    )
    assert output["interpretation"]["status"] == "conditional_on_textual_extent"


def test_all_working_counts11through199_keep_both_formulae_without_an_hour():
    changed = 0
    for n in range(11, 200):
        upper, lower = n // 2, n - n // 2
        raw_line = n % 6 or 6
        reduced_line = ((upper % 8 or 8) + (lower % 8 or 8)) % 6 or 6
        for basis, line in [
            ("raw_counts", raw_line),
            ("trigram_numbers", reduced_line),
        ]:
            cast, trace = cast_explicit_meihua(
                {
                    "method": "text_count",
                    "character_count": n,
                    "text_basis": (
                        "fixed_transcription_2690596"
                        if n <= 100
                        else "nlc1925_selected_span"
                    ),
                    "line_sum_basis": basis,
                }
            )
            assert cast["seed"]["moving_line"] == line
            assert cast["seed"]["raw_upper_number"] == upper
            assert cast["seed"]["raw_lower_number"] == lower
            assert trace[0]["result"]["hour_number_used"] is None
            assert bool(cast["counting_variants"]) == (raw_line != reduced_line)
        changed += raw_line != reduced_line
    assert changed > 0


def test_other_methods_and_unknown_basis_cannot_silently_choose_this_policy():
    for extra in [
        {"text_basis": "best_outcome"},
        {"line_sum_basis": "best_outcome"},
        {"hour_branch": "子"},
    ]:
        with pytest.raises(ValidationError):
            MeihuaCastRequest(
                casting={"method": "text_count", "character_count": 17, **extra}
            )
    with pytest.raises(ValidationError):
        MeihuaCastRequest(
            casting={
                "method": "existing",
                "hexagram_code": "111000",
                "moving_line": 5,
                "text_basis": "nlc1925_selected_span",
            }
        )


@pytest.mark.parametrize(
    "topic", ["general", "planning", "reputation", "wealth", "transaction"]
)
def test_each_human_candidate_keeps_its_own_body_relation_and_clause(topic):
    output = calculate_meihua_cast(
        casting=parameters(CASES[1]), interpretation_topic=topic
    )
    readings = {
        r["line_sum_basis"]: r for r in output["interpretation"]["casting_readings"]
    }
    assert readings["raw_counts"]["body"] == "乾"
    assert readings["trigram_numbers"]["body"] == "坤"
    assert readings["raw_counts"]["body_use_relation"] == "用生体"
    assert readings["trigram_numbers"]["body_use_relation"] == "体生用"
    for index, row in enumerate(output["interpretation"]["casting_readings"]):
        assert row["fact_prefix"] == f"meihua.counting_variants.{index}"
        if topic == "general":
            assert (
                row["classical_text_reference"]["moving_yaoci"]["position"]
                == row["moving_line"]
            )
        else:
            assert row["topic_clause"]["relation"] == row["body_use_relation"]


def test_weather_variants_do_not_borrow_the_other_changed_hexagram_rain_symbol():
    output = calculate_meihua_cast(
        casting=parameters(CASES[1]), interpretation_topic="weather"
    )
    weather = output["interpretation"]["weather"]
    rows = {r["line_sum_basis"]: r for r in weather["casting_variant_traces"]}
    statuses = {
        basis: {r["rule_id"]: r["status"] for r in row["rule_trace"]}
        for basis, row in rows.items()
    }
    assert statuses["raw_counts"]["symbol_kan"] == "matched"
    assert statuses["trigram_numbers"]["symbol_kan"] == "not_met"
    assert weather["single_forecast"] is None
    assert (
        weather["research_validation"]["current_profile_study"]["primary"]["correct"]
        == 29
    )


@pytest.mark.parametrize(
    "case,basis,topic",
    [
        (CASES[1], "raw_counts", "general"),
        (CASES[1], "trigram_numbers", "transaction"),
        (CASES[2], "raw_counts", "weather"),
        (CASES[4], "raw_counts", "general"),
    ],
)
def test_textual_and_arithmetic_conditions_survive_rest_mcp_cli(
    case, basis, topic, surface_calls
):
    spec = SPECS["meihua_cast"]
    payload = {"casting": parameters(case, basis), "interpretation_topic": topic}
    fields = [
        "meihua.seed",
        "meihua.counting_variants",
        "meihua.ruleset",
        "interpretation",
        "summary",
    ]
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    for output in [response.json(), local, protocol.structured_content]:
        assert (
            output["meihua"]["seed"]["text_count_basis"]["text_basis"]
            == case["text_basis"]
        )
        assert output["meihua"]["ruleset"]["version"] == "1.5.0"
