"""Actual P contract, computation notes, and source errors on three adapters."""

import asyncio
import json
from datetime import datetime

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.astro import house_axes
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.western.test_western_placidus_semiarc import CRITICAL, HORIZON, separation


def payload(zodiacal=0):
    case = CRITICAL[0]
    moment = datetime.fromisoformat(case["utc"])
    return dict(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_timezone="UTC",
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        hsys=3,
        zodiacal=zodiacal,
    )


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_placidus_checked_endpoints_and_limits_survive_public_surfaces(
    zodiacal, rest, tmp_path, capsys
):
    spec = SPECS["astro_chart"]
    p = payload(zodiacal)
    fields = [
        "chart_profile.house_axis_convention",
        "chart_profile.angle_definition",
        "angles",
        "houses",
        "summary",
        "interpretation_evidence.social_style.source_paths",
    ]
    response = rest.post(
        spec.rest_path,
        json=p,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, cli = call_cli(
        spec,
        p,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(spec, p, fields=fields, strict_fields=True, include_snapshot_text=False)
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        convention = result["chart_profile"]["house_axis_convention"]
        assert convention["house_code"] == "P"
        precision = convention["eastern_direction_precision"]
        assert "placidus_horizon_endpoints1_7" in precision["house_cusp_scope"]
        assert precision["maximum_physical_error_arcseconds"] is None
        assert set(precision["corrected_cusps"]) <= {1, 7}
        assert (
            precision["delivered_ascendant"]
            == result["angles"]["ascendant"]["longitude"]
        )
        assert precision["delivered_cusps"] == [
            h["cusp_longitude"] for h in result["houses"]
        ]
        assert convention["note_zh"] in result["summary"]
        assert (
            "chart_profile.house_axis_convention"
            in result["interpretation_evidence"]["social_style"]["source_paths"]
        )
        assert (
            result["chart_profile"]["angle_definition"]["status"]
            == "ecliptic_horizon_ill_conditioned"
        )
        if not zodiacal:
            assert (
                separation(
                    precision["delivered_ascendant"],
                    float(HORIZON[CRITICAL[0]["id"]]["ascendant"]),
                )
                <= 1
            )
        assert not result.get("projection_warnings")


def test_newly_checked_small_normal_cannot_silently_fall_back(
    monkeypatch, rest, tmp_path, capsys
):
    def fail(*args):
        raise ArithmeticError("injected small-normal precision failure")

    monkeypatch.setattr(house_axes, "horizon_geometry", fail)
    spec = SPECS["astro_chart"]
    p = payload()
    response = rest.post(
        spec.rest_path,
        json=p,
        params=[("fields", "person_info.name"), ("strict_fields", "true")],
    )
    code, cli = call_cli(
        spec,
        p,
        tmp_path,
        capsys,
        flags=["--fields", "person_info.name", "--strict-fields"],
    )
    protocol = asyncio.run(
        native(spec, p, fields=["person_info.name"], strict_fields=True)
    )
    assert response.status_code == 503 and code == 1 and protocol.is_error
    for result in (response.json(), cli, json.loads(protocol.content[0].text)):
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["issues"] == [
            {
                "path": "runtime.ephemeris_data",
                "code": "horizon_direction_precision_unavailable",
            }
        ]
        assert result["retryable"] is False and "person_info" not in result
