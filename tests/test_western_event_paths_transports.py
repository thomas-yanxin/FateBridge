"""Actual local protocols retain native histories, nullable source gates and failures."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_horary import QUESTION


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_event_histories_and_conditions_match_rest_native_mcp_cli(
    project, zodiac, rest, tmp_path, capsys, monkeypatch
):
    # This is the explicit native fallback contract. Strict complete-position
    # derivatives and their unavailable coverage are tested separately.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career", "zodiac_type": zodiac}
    fields = evidence_views(spec)["event_paths"]["fields"]
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
        kwargs = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    response = rest.post(spec.rest_path, json=inputs, params=params)
    code, cli = call_cli(spec, inputs, tmp_path, capsys, flags=flags)
    mcp = asyncio.run(native(spec, inputs, **kwargs))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        assert not out.get("projection_warnings")
        h = out["horary"]
        assert h["calculation_basis"]["ephemeris_model"] == "moshier"
        p = h["perfection"]
        events = p["event_history"]
        assert events["status"] == "computed" and len(events["events"]) > 100
        assert (
            events["question_julian_day_tt"] == h["calculation_basis"]["julian_day_tt"]
        )
        assert events["window_tt"] == [
            events["question_julian_day_tt"] - 30,
            events["question_julian_day_tt"] + 30,
        ]
        facts = p["lilly_conditions"]["event_paths"]
        same_body = (
            h["significators"]["querent"]["planet"]
            == h["significators"]["quesited"]["planet"]
        )
        assert facts["status"] == (
            "same_body_insufficient" if same_body else "computed_conditions"
        )
        assert bool(facts["paths"]) is not same_body
        assert h["verdict"] == "uncertain" and p["perfects"] is None
        assert events["full_original_text_acceptance"] is False
        for path in facts["paths"]:
            assert path["full_path_accepted"] is False
            for receipt in path["event_receptions"]:
                assert receipt["chart_sect"] == "day"
                assert len(receipt["endpoint_receptions"]) == 2
                assert isinstance(receipt["boundary_uncertainty"], bool)
        if project:
            assert "snapshot_text" not in out
        else:
            assert "主星历史分离与传光星历史分离分别核对" in out["snapshot_text"]


def test_failed_event_history_remains_unknown_and_source_failure_is_not_a_result(
    rest, monkeypatch, tmp_path, capsys
):
    import fatebridge.core.astrology_horary as engine
    import fatebridge.core.horary_events as events

    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career"}
    original = engine.native_planetary_events
    monkeypatch.setattr(
        engine,
        "native_planetary_events",
        lambda subject: dict(
            status="unavailable",
            constant_velocity_projection=False,
            events=[],
            unavailable_reason="Controlled unavailable history",
            full_original_text_acceptance=False,
        ),
    )
    response = rest.post(spec.rest_path, json=inputs, params={"response_char_limit": 0})
    assert response.status_code == 200
    p = response.json()["horary"]["perfection"]
    assert (
        p["event_history"]["status"] == "unavailable"
        and p["lilly_conditions"]["event_paths"]["status"] == "unavailable"
    )
    assert p["perfects"] is None
    monkeypatch.setattr(engine, "native_planetary_events", original)

    def changed(*args, **kwargs):
        raise EphemerisSourceError("model_changed")

    monkeypatch.setattr(events, "_swisseph_planet_state", changed)
    response = rest.post(spec.rest_path, json=inputs)
    code, cli = call_cli(spec, inputs, tmp_path, capsys)
    mcp = asyncio.run(native(spec, inputs))
    assert response.status_code == 503 and code != 0 and mcp.is_error
    assert cli.get("error") and response.json().get("error")
