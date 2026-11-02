"""Actual local REST, native MCP and CLI preserve complete/partial facts."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

import fatebridge.core.astrology_election as engine
from fatebridge.application.examples import evidence_views
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_election import CANDIDATE


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("unavailable", [False, True])
def test_native_election_fact_and_unknown_states_agree_across_transports(
    project, zodiac, unavailable, rest, monkeypatch, tmp_path, capsys
):
    if unavailable:
        monkeypatch.setattr(
            engine,
            "native_lunar_contacts",
            lambda subject: {
                "status": "unavailable",
                "method_id": "native_tt_lunar_contacts_before_ingress_v1",
                "constant_velocity_projection": False,
                "void_of_course": None,
                "contacts": [],
                "unavailable_reason": "Synthetic native search failure",
            },
        )
    spec = SPECS["astro_election"]
    payload = {
        **CANDIDATE,
        "topic_id": "contract",
        "house_system": "W",
        "zodiac_type": zodiac,
    }
    card = evidence_views(spec)["calculation_conditions"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        params += [("fields", f) for f in card["fields"]] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *card["fields"],
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        kwargs = {
            "fields": card["fields"],
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    response = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **kwargs))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        e = result["election"]
        raw = 60 + sum(f["weight"] for f in e["factors"])
        assert e["axes"]["ascendant_longitude"] != e["axes"]["first_house_cusp"]
        assert e["scoring_policy"]["weights_and_band_boundaries_changed"] is False
        assert e["scoring_policy"]["full_original_text_acceptance"] is False
        if unavailable:
            assert e["score"] is None and e["score_evidence"]["status"] == "partial"
            assert e["moon"]["void_of_course"] is None
            assert e["score_bounds"] == [
                max(0, min(100, raw - 25)),
                max(0, min(100, raw)),
            ]
            assert e["unresolved_factors"][0]["code"] == "moon_void_of_course"
        else:
            assert e["score"] == max(0, min(100, raw)) and e["unresolved_factors"] == []
            assert (
                e["moon"]["motion_basis"]["start_julian_day_tt"]
                == e["calculation_basis"]["julian_day_tt"]
            )
            assert e["moon"]["motion_basis"]["constant_velocity_projection"] is False
        if project:
            assert "snapshot_text" not in result
        elif unavailable:
            assert (
                "未完成" in result["summary"]
                and '"score": null' in result["snapshot_text"]
            )


def test_source_consistency_failure_is_error_not_partial_favourable_score(
    rest, monkeypatch, tmp_path, capsys
):
    def changed(subject):
        raise EphemerisSourceError("physical_configuration_changed")

    monkeypatch.setattr(engine, "native_lunar_contacts", changed)
    spec = SPECS["astro_election"]
    payload = {**CANDIDATE, "topic_id": "general"}
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 503 and code != 0 and protocol.is_error
    for result in [response.json(), cli, protocol.structured_content]:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert "election" not in result
