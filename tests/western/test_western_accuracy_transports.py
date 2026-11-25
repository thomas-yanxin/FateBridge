"""Real REST, native MCP and CLI agree on corrected western facts."""

import pytest
from jsonschema import Draft202012Validator

from tests.support.transports import SPECS, business, cached_output_validator
from tests.support.transports import inputs as representative_inputs
from tests.support.transports import native, rest, surface_calls
from tests.unit_test.fixtures.western_natal import GREENWICH_EQUINOX_BIRTH as BIRTH


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen"])
def test_civil_time_horizon_and_primary_text_facts_across_transports(
    key: str, surface_calls
) -> None:
    spec = SPECS[key]
    payload = {**BIRTH, "hsys": 0}
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params={"response_char_limit": 0},
        flags=["--response-char-limit", "0"],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        cached_output_validator(spec.output_model).validate(result)
        assert result["classical"]["sect"] == "day"
        assert result["chart_profile"]["calendar"] == "proleptic_gregorian"
        assert result["classical"]["ptolemy"]["status"] == "computed_subset"


def test_new_evidence_supports_strict_projection_on_all_transports(
    surface_calls,
) -> None:
    spec = SPECS["astro_hellen"]
    fields = [
        "classical.ptolemy.planets.Sun.triplicity_primary",
        "classical.sect",
        "chart_profile.time_scale",
        "classical.syzygy.solver.strictly_before_birth",
        "classical.syzygy.zodiac",
        "planetary_hours.hour_start_utc",
        "planetary_hours.hour_end_utc",
    ]
    flags = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response, protocol, code, local = surface_calls(
        spec,
        BIRTH,
        params=[("fields", field) for field in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
        options=flags,
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


def test_explanation_references_can_be_checked_against_the_original_receipt(
    rest,
) -> None:
    from validation.claims import CalculationClaim, verify_calculation_claims

    result = rest.post(
        "/api/astrology/chart", json=BIRTH, params={"response_char_limit": 0}
    ).json()
    metadata = result["run_metadata"]
    claims = []
    for path, value in (
        ("angles.ascendant.longitude", result["angles"]["ascendant"]["longitude"]),
        ("planets.0.longitude", result["planets"][0]["longitude"]),
    ):
        claims.append(
            CalculationClaim(path=path, value=value, run_id=metadata["run_id"])
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
        )
    )
    assert verify_calculation_claims(result, claims)["status"] == "rejected"


def test_dst_gap_fails_consistently_instead_of_returning_a_chart(surface_calls) -> None:
    spec = SPECS["astro_chart"]
    payload = {
        **BIRTH,
        "birth_month": 3,
        "birth_day": 10,
        "birth_hour": 2,
        "birth_timezone": "America/New_York",
    }
    response, protocol, code, local = surface_calls(spec, payload)
    assert response.status_code == 400 and code != 0 and protocol.is_error
    assert local["error_code"] == "validation_error"


@pytest.mark.parametrize("key", ["solarreturn", "lunarreturn", "transit"])
def test_native_timing_time_scales_and_full_precision_agree_across_surfaces(
    key: str, surface_calls
) -> None:
    from tests.support.transports import AS_OF

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
    else:
        pass
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params=[("fields", field) for field in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("as_of", AS_OF),
        ],
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
    assert response.status_code == 200 and code == 0 and not protocol.is_error, (
        response.json(),
        local,
    )
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        cached_output_validator(spec.output_model).validate(result)
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
        else:
            pass


def test_robbins_fortune_formula_and_value_are_projectable_on_all_surfaces(
    surface_calls,
) -> None:
    spec = SPECS["astro_chart"]
    fields = ["classical.ptolemy.ruleset_id", "classical.ptolemy.lot_of_fortune"]
    response, protocol, code, local = surface_calls(
        spec,
        BIRTH,
        params=[("fields", f) for f in fields] + [("strict_fields", "true")],
        options={"fields": fields, "strict_fields": True},
        flags=["--fields", *fields, "--strict-fields", "--response-char-limit", "0"],
    )
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


def test_published_ptolemy_card_returns_supported_original_text_facts(rest) -> None:
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


def test_ready_reports_native_predictive_runtime(rest) -> None:
    response = rest.get("/ready")
    assert response.status_code == 200
    check = response.json()["checks"]["western_predictive_runtime"]
    assert check["ok"] is True
    assert check["swisseph_available"] is True
    assert check["engine_backend"] == "fatebridge_swisseph_native"


@pytest.mark.parametrize("month,day,hour", [(3, 10, 2), (11, 3, 1)])
def test_invalid_analysis_dst_clock_is_rejected_across_surfaces(
    month: int, day: int, hour: int, surface_calls
) -> None:
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
    response, protocol, code, local = surface_calls(spec, payload)
    assert response.status_code == 400 and code != 0 and protocol.is_error
    assert local["error_code"] == "validation_error"
    assert "分析钟时" in local["error"]


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen"])
def test_unrounded_facts_and_source_specific_reading_agree_across_surfaces(
    key: str, surface_calls
) -> None:
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
    ]
    response, protocol, code, local = surface_calls(
        spec,
        BIRTH,
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
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    for result in [response.json(), local, protocol.structured_content]:
        cached_output_validator(spec.output_model).validate(result)
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


def test_invalid_internal_coordinate_is_not_published_through_any_surface(
    monkeypatch: pytest.MonkeyPatch, surface_calls
) -> None:
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
        else:
            pass
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", invalid_coordinate)
    spec = SPECS["astro_chart"]
    response, protocol, code, local = surface_calls(spec, BIRTH)
    assert response.status_code == 500 and code == 1 and protocol.is_error
    assert (
        local["error_code"]
        == response.json()["error_code"]
        == protocol.structured_content["error_code"]
        == "internal_error"
    )


def test_analysis_clock_retains_unspecified_offset_issue(surface_calls) -> None:
    payload = {
        "name": "虚构钟面审计",
        "birth_year": 1976,
        "birth_month": 6,
        "birth_day": 1,
        "birth_hour": 12,
        "birth_minute": 0,
        "birth_timezone": "Antarctica/Vostok",
        "birth_longitude": 106.84,
        "birth_latitude": -78.46,
        "house_system": "W",
        "analysis_year": 1994,
        "analysis_month": 1,
        "analysis_day": 31,
        "analysis_hour": 20,
        "analysis_minute": 0,
    }
    response, protocol, code, local = surface_calls(
        SPECS["western_timing_analysis"], payload
    )
    assert response.status_code == 422 and protocol.is_error and code == 1
    for body in (response.json(), protocol.structured_content, local):
        assert body["error_code"] == "validation_error" and body["retryable"] is False
        assert body["issues"] == [
            {"path": "request", "code": "unresolved_timezone_offset"}
        ]
