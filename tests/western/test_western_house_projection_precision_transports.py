"""Actual precision records and source rejections on local public adapters."""

import json

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.astro import house_positions
from fatebridge.core.astro.house_projection_precision import RC_PLANE_PROJECTION_METHOD
from tests.support.transports import SPECS, business, rest, surface_calls
from tests.western.test_western_horizon_precision import PUBLIC


def payload(hsys, zodiacal=0):
    case = PUBLIC[0]
    return dict(
        birth_year=case["year"],
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        hsys=hsys,
        zodiacal=zodiacal,
    )


@pytest.mark.parametrize("hsys", [2])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_plane_records_and_explanation_survive_public_surfaces(
    hsys, zodiacal, surface_calls
):
    spec = SPECS["astro_chart"]
    p = payload(hsys, zodiacal)
    fields = [
        "chart_profile.house_position_projection",
        "planets",
        "summary",
        "interpretation_evidence.social_style.source_paths",
    ]
    http, protocol, code, cli = surface_calls(
        spec,
        p,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        projection = result["chart_profile"]["house_position_projection"]
        assert projection["method"] == RC_PLANE_PROJECTION_METHOD
        assert projection["note_zh"] in result["summary"]
        assert (
            "chart_profile.house_position_projection"
            in result["interpretation_evidence"]["social_style"]["source_paths"]
        )
        assert projection["precision"]["checks"]
        assert projection["precision"]["maximum_physical_error_arcseconds"] is None
        assert not result.get("projection_warnings")


def test_plane_precision_failure_cannot_be_hidden_by_projection(
    monkeypatch, surface_calls
):
    def fail(**kwargs):
        raise ArithmeticError("injected plane failure")

    monkeypatch.setattr(house_positions, "checked_house_plane_position", fail)
    spec = SPECS["astro_chart"]
    p = payload(2)
    http, protocol, code, cli = surface_calls(
        spec,
        p,
        params=[("fields", "person_info.name"), ("strict_fields", "true")],
        options={"fields": ["person_info.name"], "strict_fields": True},
        flags=["--fields", "person_info.name", "--strict-fields"],
    )
    assert http.status_code == 503 and code == 1 and protocol.is_error
    for result in [http.json(), cli, json.loads(protocol.content[0].text)]:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["issues"] == [
            {
                "path": "runtime.ephemeris_data",
                "code": "house_projection_precision_unavailable",
            }
        ]
        assert result["retryable"] is False and "person_info" not in result


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_actual_campanus_predictive_contract_on_all_surfaces(zodiac, surface_calls):
    case = PUBLIC[0]
    spec = SPECS["transit"]
    p = payload(2)
    del p["hsys"], p["zodiacal"]
    p.update(
        house_system="C",
        zodiac_type=zodiac,
        analysis_year=case["year"],
        analysis_month=1,
        analysis_day=1,
        analysis_hour=0,
        analysis_minute=30,
        return_timezone="UTC",
        return_longitude=case["longitude"],
        return_latitude=case["latitude"],
    )
    fields = [
        f"{layer}.calculation_basis.house_position_projection"
        for layer in ["natal_reference", "transit"]
    ]
    http, protocol, code, cli = surface_calls(
        spec,
        p,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        for layer in ["natal_reference", "transit"]:
            projection = result[layer]["calculation_basis"]["house_position_projection"]
            assert (
                projection["house_code"] == "C"
                and projection["method"] == RC_PLANE_PROJECTION_METHOD
            )
            assert projection["precision"]["checks"]
        assert not result.get("projection_warnings")
