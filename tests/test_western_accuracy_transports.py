"""Real REST, native MCP and CLI agree on corrected western facts."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_accuracy import BIRTH


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen"])
def test_civil_time_horizon_and_primary_text_facts_across_transports(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**BIRTH, "hsys": 0}
    response = rest.post(
        spec.rest_path, json=payload, params={"response_char_limit": 0}
    )
    code, local = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert result["classical"]["sect"] == "day"
        assert result["chart_profile"]["calendar"] == "proleptic_gregorian"
        assert result["classical"]["ptolemy"]["status"] == "computed_subset"
        assert result["interpretation_evidence"]["core_identity"]["source_paths"] == [
            "planets.0"
        ]


def test_new_evidence_supports_strict_projection_on_all_transports(
    rest, tmp_path, capsys
):
    spec = SPECS["astro_hellen"]
    fields = [
        "classical.ptolemy.planets.Sun.triplicity_primary",
        "classical.sect",
        "interpretation_evidence.core_identity.source_paths",
        "chart_profile.time_scale",
        "classical.syzygy.solver.strictly_before_birth",
        "classical.syzygy.zodiac",
        "planetary_hours.hour_start_utc",
        "planetary_hours.hour_end_utc",
    ]
    flags = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response = rest.post(
        spec.rest_path,
        json=BIRTH,
        params=[("fields", field) for field in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, local = call_cli(
        spec,
        BIRTH,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, BIRTH, **flags))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for result in [response.json(), local, protocol.structured_content]:
        assert result["classical"]["sect"] == "day"
        assert "snapshot_text" not in result
        assert not result.get("projection_warnings")
        assert result["classical"]["syzygy"]["solver"]["strictly_before_birth"] is True
        assert result["classical"]["syzygy"]["zodiac"] == "tropical"
        assert (
            result["planetary_hours"]["hour_start_utc"]
            < result["planetary_hours"]["hour_end_utc"]
        )


def test_explanation_references_can_be_checked_against_the_original_receipt(rest):
    from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

    result = rest.post(
        "/api/astro/chart", json=BIRTH, params={"response_char_limit": 0}
    ).json()
    metadata = result["run_metadata"]
    claims = []
    for evidence in result["interpretation_evidence"].values():
        for path in evidence["source_paths"]:
            value = result
            for key in path.split("."):
                value = value[int(key)] if isinstance(value, list) else value[key]
            claims.append(
                CalculationClaim(
                    path=path,
                    value=value,
                    run_id=metadata["run_id"],
                    business_output_sha256=metadata["business_output_sha256"],
                )
            )
    assert (
        verify_calculation_claims(result, claims)["status"]
        == "verified_structured_facts"
    )
    # An uncomputed probability cannot be laundered through an evidence path.
    claims.append(
        CalculationClaim(
            path="predicted_success_probability",
            value=1.0,
            run_id=metadata["run_id"],
            business_output_sha256=metadata["business_output_sha256"],
        )
    )
    assert verify_calculation_claims(result, claims)["status"] == "rejected"


def test_dst_gap_fails_consistently_instead_of_returning_a_chart(
    rest, tmp_path, capsys
):
    spec = SPECS["astro_chart"]
    payload = {
        **BIRTH,
        "birth_month": 3,
        "birth_day": 10,
        "birth_hour": 2,
        "birth_timezone": "America/New_York",
    }
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 400 and code != 0 and protocol.is_error
    assert local["error_code"] == "validation_error"


@pytest.mark.parametrize("key", ["solarreturn", "lunarreturn", "transit"])
def test_native_timing_time_scales_and_full_precision_agree_across_surfaces(
    key, rest, tmp_path, capsys
):
    from tests.test_agentic_nested_outputs import AS_OF

    spec = SPECS[key]
    payload = {
        **BIRTH,
        "birth_year": 1990,
        "birth_month": 4,
        "birth_day": 6,
        "birth_hour": 1,
        "birth_minute": 33,
        "analysis_year": 2099,
        "analysis_month": 12,
        "analysis_day": 31,
        "analysis_hour": 23,
        "analysis_minute": 59,
        "return_timezone": "+05:45",
        "return_longitude": 85.32,
        "return_latitude": 27.72,
    }
    fields = [
        "natal_reference.calculation_basis",
        f"{key}.calculation_basis",
        f"{key}.sun.longitude",
        f"{key}.moon.longitude",
    ]
    if key != "transit":
        fields += [
            f"{key}.solver",
            f"{key}.return_datetime_utc",
            f"{key}.return_datetime",
        ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", field) for field in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("as_of", AS_OF),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
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
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error, (
        response.json(),
        local,
    )
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        assert (
            result[key]["calculation_basis"]["future_leap_seconds_assumed_unchanged"]
            is True
        )
        assert (
            result[key]["calculation_basis"]["engine_backend"]
            == "fatebridge_swisseph_native"
        )
        assert result[key]["sun"]["longitude"] > 0
        if key != "transit":
            assert result[key]["solver"]["residual_arcseconds"] < 0.002
            assert result[key]["solver"]["event_not_after_analysis"] is True
            assert result[key]["return_datetime"].endswith("+05:45")


def test_robbins_fortune_formula_and_value_are_projectable_on_all_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["astro_chart"]
    fields = ["classical.ptolemy.ruleset_id", "classical.ptolemy.lot_of_fortune"]
    response = rest.post(
        spec.rest_path,
        json=BIRTH,
        params=[("fields", f) for f in fields] + [("strict_fields", "true")],
    )
    code, local = call_cli(
        spec,
        BIRTH,
        tmp_path,
        capsys,
        flags=["--fields", *fields, "--strict-fields", "--response-char-limit", "0"],
    )
    protocol = asyncio.run(native(spec, BIRTH, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    assert (
        local["classical"]["ptolemy"]["lot_of_fortune"]["formula"]
        == "ascendant + Moon - Sun (day and night)"
    )


def test_published_ptolemy_card_returns_supported_original_text_facts(rest):
    from fatebridge.application.examples import evidence_views

    spec = SPECS["astro_chart"]
    card = evidence_views(spec)["ptolemy"]
    response = rest.post(
        spec.rest_path,
        json=BIRTH,
        params=[("fields", f) for f in card["fields"]] + [("strict_fields", "true")],
    )
    assert response.status_code == 200
    result = response.json()
    assert not result.get("projection_warnings")
    assert result["classical"]["ptolemy"]["lot_of_fortune"]["longitude"] >= 0


def test_ready_uses_native_predictive_runtime_without_kerykeion(rest, monkeypatch):
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)
    response = rest.get("/ready")
    assert response.status_code == 200
    check = response.json()["checks"]["western_predictive_runtime"]
    assert check["ok"] is True
    assert check["kerykeion_available"] is False
    assert check["engine_backend"] == "fatebridge_swisseph_native"


@pytest.mark.parametrize("month,day,hour", [(3, 10, 2), (11, 3, 1)])
def test_invalid_analysis_dst_clock_is_rejected_across_surfaces(
    month, day, hour, rest, tmp_path, capsys
):
    spec = SPECS["transit"]
    payload = {
        **BIRTH,
        "birth_year": 1990,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 12,
        "birth_timezone": "America/New_York",
        "birth_longitude": -74,
        "birth_latitude": 40.7,
        "analysis_year": 2024,
        "analysis_month": month,
        "analysis_day": day,
        "analysis_hour": hour,
        "analysis_minute": 30,
    }
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 400 and code != 0 and protocol.is_error
    assert local["error_code"] == "validation_error"
    assert "分析钟时" in local["error"]


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen"])
def test_unrounded_facts_and_source_specific_reading_agree_across_surfaces(
    key, rest, tmp_path, capsys
):
    import math

    spec = SPECS[key]
    fields = [
        "chart_profile.coordinate_precision",
        "planets",
        "angles",
        "houses",
        "aspects",
        "aspect_evidence",
        "classical.ptolemy",
        "interpretation",
        "interpretation_evidence",
    ]
    response = rest.post(
        spec.rest_path,
        json=BIRTH,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, local = call_cli(
        spec,
        BIRTH,
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
        native(
            spec, BIRTH, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    for result in [response.json(), local, protocol.structured_content]:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert (
            result["chart_profile"]["coordinate_precision"]
            == "unrounded_computation_and_numeric_output"
        )
        planets = {p["id"]: p for p in result["planets"]}
        for point in planets.values():
            assert 0 <= point["longitude"] < 360 and 0 <= point["degree_in_sign"] < 30
            assert point["degree_in_sign"] == point["longitude"] % 30
        assert any(p["longitude"] != round(p["longitude"], 4) for p in planets.values())
        assert len(result["aspect_evidence"]) == len(result["aspects"])
        for aspect in result["aspect_evidence"]:
            difference = abs(
                planets[aspect["planet_a"]]["longitude"]
                - planets[aspect["planet_b"]]["longitude"]
            )
            separation = min(difference, 360 - difference)
            assert math.isclose(
                aspect["orb"], abs(separation - aspect["exact_angle"]), abs_tol=1e-12
            )
            assert aspect["orb"] <= aspect["orb_limit"]
        assert len(result["classical"]["ptolemy"]["sign_relationships"]) == 21
        assert "original_text_relations" in result["interpretation"]
        assert (
            result["interpretation_evidence"]["original_text_relations"]["kind"]
            == "primary_text_rule_interpretation"
        )
        assert "最强主相位" not in result["interpretation"]["aspect_pattern"]


def test_invalid_internal_coordinate_is_not_published_through_any_surface(
    rest, tmp_path, capsys, monkeypatch
):
    from dataclasses import replace

    import fatebridge.application.execution as execution

    original = execution.execute_spec

    def invalid_coordinate(actual, request):
        if actual.key == "astro_chart":
            actual = replace(
                actual,
                bind=lambda _: (
                    lambda: {"planets": [{"id": "Sun", "longitude": 360.0}]},
                    (),
                    {},
                ),
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", invalid_coordinate)
    spec = SPECS["astro_chart"]
    response = rest.post(spec.rest_path, json=BIRTH)
    code, local = call_cli(spec, BIRTH, tmp_path, capsys)
    protocol = asyncio.run(native(spec, BIRTH))
    assert response.status_code == 500 and code == 1 and protocol.is_error
    assert (
        local["error_code"]
        == response.json()["error_code"]
        == protocol.structured_content["error_code"]
        == "internal_error"
    )
