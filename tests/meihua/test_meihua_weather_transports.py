"""The dedicated weather branch and its source evidence survive all surfaces."""

import asyncio
import hashlib
import json

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator

from fatebridge.application.examples import suggested_fields
from fatebridge.mcp_server import create_mcp_app
from tests.meihua.test_meihua_transports import INPUT
from tests.meihua.test_meihua_weather_cast_variants import CASES as VARIANT_CASES
from tests.meihua.test_meihua_weather_cast_variants import resolve
from tests.support.result_delivery import store
from tests.support.transports import SPECS, business, rest, surface_calls

FIELDS = [
    "interpretation.interpretation_topic",
    "interpretation.weather",
    "interpretation.evidence_scope",
    "summary",
]


@pytest.mark.parametrize("key", ["meihua_analysis", "meihua_cast"])
@pytest.mark.parametrize("projected", [False, True])
def test_weather_rules_agree_on_rest_mcp_cli(key, projected, surface_calls):
    spec = SPECS[key]
    payload = (
        dict(INPUT)
        if key == "meihua_analysis"
        else {
            "casting": {
                "method": "existing",
                "hexagram_code": "001010",
                "moving_line": 4,
            }
        }
    )
    context = {"season": "winter", "prior_condition": "prolonged_rain"}
    payload.update(interpretation_topic="weather", weather_context=context)
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0", "--weather-context", json.dumps(context)]
    options = {}
    if projected:
        params += [("fields", f) for f in FIELDS] + [("strict_fields", "true")]
        flags += ["--fields", *FIELDS, "--strict-fields", "true"]
        options = {"fields": FIELDS, "strict_fields": True}
    response, protocol, code, local = surface_calls(
        spec, payload, params=params, options=options, flags=flags
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert output["interpretation"]["evidence_scope"]["body_use_applied"] is False
        assert (
            "meihua_weather_v1@1.7.0" in output["run_metadata"]["provenance"]["ruleset"]
        )
        assert (
            "meihua_weather_controls_v1@1.0.0"
            in output["run_metadata"]["provenance"]["ruleset"]
        )
        assert output["interpretation"]["weather"]["single_forecast"] is None


@pytest.mark.parametrize("key", ["meihua_analysis", "meihua_cast"])
def test_weather_context_cannot_silently_use_general_reading(key, surface_calls):
    spec = SPECS[key]
    payload = (
        dict(INPUT)
        if key == "meihua_analysis"
        else {
            "casting": {
                "method": "existing",
                "hexagram_code": "101101",
                "moving_line": 1,
            }
        }
    )
    payload["weather_context"] = {"season": "summer"}
    response, protocol, code, local = surface_calls(spec, payload)
    assert response.status_code == 422 and code != 0 and protocol.is_error


@pytest.mark.parametrize("key", ["meihua_analysis", "meihua_cast"])
def test_published_weather_reading_card_retains_control_qualification(
    key, surface_calls
):
    spec = SPECS[key]
    payload = (
        dict(INPUT)
        if key == "meihua_analysis"
        else {
            "casting": {
                "method": "existing",
                "hexagram_code": "011111",
                "moving_line": 4,
            }
        }
    )
    payload.update(
        interpretation_topic="weather", weather_context={"many_min_count": 2}
    )
    fields = suggested_fields(spec, view="weather")
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
    weather = local["interpretation"]["weather"]
    assert weather["selected_readings"] and "rule_trace" not in weather
    assert weather["control_profile"]["sources"]
    assert weather["research_validation"]["correct"] == 128
    if key == "meihua_cast":
        row = next(
            r for r in weather["selected_readings"] if r["rule_id"] == "symbol_xun"
        )
        assert row["controlled_tags"] == ["wind"]
        assert row["effective_status"] == "qualified_by_source_control"


@pytest.mark.parametrize(
    "code,line,season,rule_id",
    [
        ("101101", 1, "summer", "summer_li_without_kan"),
        ("101101", 4, "summer", "many_li"),
        ("010010", 1, "winter", "winter_kan_without_li"),
    ],
)
def test_weather_card_keeps_disputed_many_premise_on_all_surfaces(
    code, line, season, rule_id, surface_calls
):
    spec = SPECS["meihua_cast"]
    payload = {
        "casting": {"method": "existing", "hexagram_code": code, "moving_line": line},
        "interpretation_topic": "weather",
        "weather_context": {"season": season, "many_min_count": 3},
    }
    fields = suggested_fields(spec, view="weather")
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
        options={"fields": fields, "strict_fields": True},
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--weather-context",
            json.dumps(payload["weather_context"]),
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    for output in [response.json(), local, protocol.structured_content]:
        row = next(
            r
            for r in output["interpretation"]["weather"]["selected_readings"]
            if r["rule_id"] == rule_id
        )
        assert row["effective_status"] == "conditional_on_unresolved_frequency"
        assert [
            v["count"] for v in row["frequency_assessment"]["counting_variants"]
        ] == [3, 2]
        assert row["qualification_reasons"] == ["unresolved_frequency_scope"]
        assert "频数范围未裁定" in row["reading"]
        assert "频数范围未裁定" in output["summary"]


@pytest.mark.parametrize("case", VARIANT_CASES[:5], ids=lambda c: c["id"])
def test_weather_card_preserves_actual_candidate_readings_on_all_surfaces(
    case, surface_calls
):
    spec = SPECS["meihua_cast"]
    payload = {
        "casting": case["casting"],
        "interpretation_topic": "weather",
        "weather_context": case["context"],
    }
    fields = suggested_fields(spec, view="weather")
    response, protocol, exit_code, local = surface_calls(
        spec,
        payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
        options={"fields": fields, "strict_fields": True},
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--weather-context",
            json.dumps(case["context"]),
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and exit_code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    for output in [response.json(), local, protocol.structured_content]:
        weather = output["interpretation"]["weather"]
        assert (
            weather["casting_comparison"]["status"]
            == case["expected"]["comparison_status"]
        )
        assert len(weather["casting_variants"]) == 2
        assert "casting_variant_traces" not in weather
        assert all(row["selected_readings"] for row in weather["casting_variants"])
        for index, row in enumerate(weather["casting_variants"]):
            assert row["fact_prefix"] == f"meihua.counting_variants.{index}"
            assert (
                row["moving_line"]
                == output["meihua"]["counting_variants"][index]["moving_line"]
            )
        assert weather["ruleset"]["sources"] and weather["control_profile"]["sources"]
        assert "各候选分列" in output["summary"]


def test_large_candidate_card_remains_readable_from_same_run_without_recalculation(
    store,
):
    async def replay():
        spec = SPECS["meihua_cast"]
        case = VARIANT_CASES[0]
        async with Client(create_mcp_app()) as client:
            reply = await client.call_tool(
                "meihua_cast",
                {
                    "casting": case["casting"],
                    "interpretation_topic": "weather",
                    "weather_context": case["context"],
                    "fields": suggested_fields(spec, view="weather"),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            assert not reply.is_error
            data = reply.structured_content
            ref = data["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            assert manifest["run_metadata"]["run_id"] == data["run_metadata"]["run_id"]
            uri = f"fatebridge://results/{ref['result_id']}/fields/interpretation.weather.casting_variants/0"
            parts = []
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                assert page["result_id"] == ref["result_id"]
                assert page["path"] == "interpretation.weather.casting_variants"
                parts.append(page["text"])
                uri = page["next_uri"]
            full_text = "".join(parts)
            assert hashlib.sha256(full_text.encode()).hexdigest() == page["sha256"]
            variants = json.loads(full_text)
            assert len(variants) == 2
            rows = {v["line_sum_basis"]: v for v in variants}
            assert "summer_li_without_kan" not in rows["raw_counts"]["matched_rule_ids"]
            assert (
                "summer_li_without_kan" in rows["trigram_numbers"]["matched_rule_ids"]
            )

    asyncio.run(replay())


def test_complete_weather_audit_card_retains_the_actual_geometry_for_its_paths():
    async def replay():
        spec = SPECS["meihua_cast"]
        case = VARIANT_CASES[0]
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "meihua_cast",
                {
                    "casting": case["casting"],
                    "interpretation_topic": "weather",
                    "weather_context": case["context"],
                    "fields": suggested_fields(spec, view="weather_audit"),
                    "strict_fields": True,
                    "response_char_limit": 0,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            assert not result.is_error
            output = result.structured_content
            for row in output["interpretation"]["weather"]["casting_variant_traces"]:
                for slot in row["trigram_slots"]:
                    assert resolve(output, slot["path"])["name"] == slot["trigram"]
            assert output["input_normalized"]["casting"]["count"] == 9

    asyncio.run(replay())
