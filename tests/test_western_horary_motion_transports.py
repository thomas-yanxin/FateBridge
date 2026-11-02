"""Actual REST/native MCP/CLI preserve events, candidate status and source gaps."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_accuracy import BIRTH
from tests.test_western_horary import QUESTION


@pytest.mark.parametrize(
    "key",
    ["astro_chart", "astro_chart13", "astro_hellen", "astro_india", "astro_germany"],
)
def test_named_solar_policy_view_keeps_definition_and_textual_conflict_together(
    key, rest
):
    spec = SPECS[key]
    card = evidence_views(spec)["solar_conditions"]
    response = rest.post(
        spec.rest_path,
        json=BIRTH,
        params=[("fields", p) for p in card["fields"]]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    assert response.status_code == 200
    result = response.json()
    assert not result.get("projection_warnings")
    node = result["base_chart"] if key == "astro_germany" else result
    policy = node["classical"]["solar_condition_policy"]
    assert policy["under_beams_limit_degrees"] == 17
    assert policy["combust_requires_same_sign"] is True
    assert policy["full_page_acceptance"] is False
    assert "Sun 18 Aries, planet 28 Aries" in policy["printed_example_discrepancy"]


@pytest.mark.parametrize("project", [False, True])
def test_native_lunar_events_and_unverified_conditions_match_three_transports(
    project, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    payload = {**QUESTION, "category": "general"}
    fields = evidence_views(spec)["motion_conditions"]["fields"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        params += [("fields", p) for p in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        kwargs = {
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    response = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **kwargs))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        horary = result["horary"]
        assert horary["perfection"]["perfects"] is None
        assert horary["perfection"]["candidate"] is False
        assert horary["perfection"]["status"] == "same_ruler_insufficient"
        assert horary["verdict"] == "uncertain"
        assert horary["rule_profile"]["full_original_text_acceptance"] is False
        basis = horary["moon"]["motion_basis"]
        assert basis["status"] == "computed" and basis["time_scale"] == "TT"
        assert basis["constant_velocity_projection"] is False
        assert basis["physical_ephemeris_source"]["accuracy_certified"] is False
        assert (
            horary["calculation_basis"]["julian_day_tt"] == basis["start_julian_day_tt"]
        )
        if project:
            assert "heuristic_verdict" not in horary and "snapshot_text" not in result
        else:
            assert "尚未完成Lilly" in result["snapshot_text"]


def test_failed_native_event_search_remains_unknown_in_public_schema(rest, monkeypatch):
    import fatebridge.core.astrology_horary as horary

    monkeypatch.setattr(
        horary,
        "native_lunar_contacts",
        lambda subject: {
            "status": "unavailable",
            "method_id": "native_tt_lunar_contacts_before_ingress_v1",
            "constant_velocity_projection": False,
            "void_of_course": None,
            "contacts": [],
            "unavailable_reason": "Synthetic source unavailable",
        },
    )
    result = rest.post(
        SPECS["astro_horary"].rest_path,
        json={**QUESTION, "category": "career"},
        params={"response_char_limit": 0},
    )
    assert result.status_code == 200
    output = result.json()["horary"]
    assert output["moon"]["void_of_course"] is None
    assert output["moon"]["motion_basis"]["status"] == "unavailable"
    assert not any(
        row["code"] == "moon_void_of_course"
        for row in output["radicality"]["strictures"]
    )
    assert output["verdict"] == "uncertain"


def test_published_horary_description_matches_actual_cast_and_verification_scope():
    summary = SPECS["astro_horary"].summary
    assert "按明确提问时刻起盘" in summary and "原典条件缺项" in summary
    assert "求解天文时刻后起盘" not in summary
