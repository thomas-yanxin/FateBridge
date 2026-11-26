"""Keep native specialty chart controls on the same synthetic clock."""

import asyncio
import json
import math
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import TypedDict

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from jsonschema import Draft202012Validator
from pydantic import JsonValue

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.western.audit_meridian_house_geometry import (
    read_protocol,
    signed,
    vector_longitude,
)
from tests.fixtures.surface_payloads import astro_payload
from tests.support.transports import call_calculation

AS_OF = "2026-10-22T00:00:00Z"
SPECS = {spec.key: spec for spec in CATALOG}


class SpecialtyChartRequest(TypedDict):
    name: str
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birth_timezone: str
    birth_time_uncertainty_minutes: int
    hsys: int


SPECIALTY_CHART_REQUEST: SpecialtyChartRequest = {
    "name": "虚构：黄道地平面退化核验",
    "birth_year": 2000,
    "birth_month": 1,
    "birth_day": 1,
    "birth_hour": 12,
    "birth_minute": 0,
    "birth_timezone": "UTC",
    "birth_time_uncertainty_minutes": 1,
    "hsys": 1,
}


def assert_specialized_facts_across_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    key: str,
    variant: str | None,
    fields: list[str],
    overrides: dict[str, JsonValue],
    *,
    expect_external_elements: bool = False,
) -> None:
    spec = SPECS[key]
    payload = {**astro_payload(), **overrides}
    if variant:
        payload["chart_variant"] = variant
    else:
        pass
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", field) for field in fields],
        ],
    )

    async def native() -> CallToolResult:
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client,
                spec.tool_name,
                {
                    **payload,
                    "as_of": AS_OF,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    protocol = asyncio.run(native())
    request_file = tmp_path / "specialized-request.json"
    request_file.write_text(json.dumps(payload))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(request_file),
            "--as-of",
            AS_OF,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert code == 0, cli
    native_json = protocol.structured_content
    for body in (response.json(), native_json, cli):
        assert body["run_metadata"]["tool_name"] == spec.tool_name
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [response.json(), native_json, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    geometry = bodies[0].get("midpoint_analysis", {})
    if "meridian_houses" in geometry:
        meridian = geometry["meridian_houses"]
        profile = meridian["profile"]
        tolerance = read_protocol()["geometry_tolerance_degrees"]
        assert meridian["ruleset_id"] == "witte1923_natal_meridian_house_geometry_v1"
        assert len(meridian["cusps"]) == 12
        assert profile["first_cusp_replaces_physical_ascendant"] is False
        assert profile["base_chart_houses_replaced"] is False
        for row in meridian["cusps"]:
            expected = (
                vector_longitude(row["right_ascension"], profile["true_obliquity"])
                + profile["source_ecliptic_longitude_origin"]
                - profile["ayanamsha_apparent"]
            )
            assert abs(signed(row["longitude"], expected)) <= tolerance
    else:
        pass
    if "profile" in geometry:
        physical_source = geometry["profile"]["physical_ephemeris_source"]
        assert len(physical_source["by_factor"]) == 10
        assert physical_source["accuracy_certified"] is False
        assert physical_source["atomic_file_read_proven"] is False
        assert all(
            "/" not in row["filename"] and "\\" not in row["filename"]
            for row in physical_source["files"]
        )
    else:
        pass
    for dial in geometry.get("dials", {}).values():
        contacts = dial["two_factor_contacts"]
        assert contacts
        assert all(row["id_a"] != row["id_b"] for row in contacts)
        assert all(row["aspect_degrees"] in (0, 45, 90, 135, 180) for row in contacts)
        assert all(0 <= row["separation_degrees"] <= 180 for row in contacts)
    if "unique_two_factor_pair_count" in geometry:
        assert geometry["unique_two_factor_pair_count"] == len(
            {
                (row["id_a"], row["id_b"])
                for dial in geometry["dials"].values()
                for row in dial["two_factor_contacts"]
            }
        )
    else:
        pass
    if expect_external_elements:
        element_source = bodies[0]["midpoint_analysis"]["profile"][
            "hypothetical_element_source"
        ]
        assert element_source["status"] == "external_file"
        assert "sha256" not in element_source
        assert str(tmp_path) not in json.dumps(element_source)
        hypotheses = [
            row
            for row in bodies[0]["midpoint_analysis"]["factors"]
            if row["kind"] == "hypothetical"
        ]
        assert len(hypotheses) == 8
        assert all(row["element_name"] for row in hypotheses)
    else:
        pass
    if (
        "birth_year" in overrides
        and "analysis_datetime" not in overrides
        and "midpoint_analysis.interpretations" in fields
    ):
        # A deliberately selected fictional integration stimulus, not a birth
        # case or an event observation attributed to the original book.
        layer = bodies[0]["midpoint_analysis"]
        assert len(layer["interpretations"]) == 1
        reading = layer["interpretations"][0]
        values = {row["id"]: row["longitude"] for row in layer["factors"]}
        assert reading["factor_longitudes"] == {
            name: values[name] for name in ("Mars", "Jupiter", "Zeus", "Midheaven")
        }
        assert reading["contains_hypothetical"] is True
        theta = math.radians(
            values["Mars"] + values["Jupiter"] - values["Zeus"] - values["Midheaven"]
        )
        actual_orb = abs(math.degrees(math.atan2(math.sin(theta), math.cos(theta))))
        assert reading["direct_orb_degrees"] == pytest.approx(actual_orb, abs=1e-11)
        assert actual_orb <= reading["maximum_orb_degrees"]
        assert reading["source_id"] == "udo_rudolph_1996_abc_excerpt"
        assert reading["claim_type"] == "source_attributed_symbolic_interpretation"
    else:
        pass
    if (
        "birth_time_uncertainty_minutes" in overrides
        and "analysis_datetime" not in overrides
    ):
        sensitivity = (
            bodies[0]["midpoint_analysis"]["time_sensitivity"]
            if key == "astro_germany" or variant == "germany"
            else bodies[0]["time_sensitivity"]
        )
        assert sensitivity["status"] == "sampled"
        assert sensitivity["physical_ephemeris_models_consistent"] is True
        sources = sensitivity["physical_ephemeris_sources"]
        assert sources
        assert all(
            0 <= s["physical_source_index"] < len(sources)
            for s in sensitivity["samples"]
        )
        assert (
            sensitivity["uncertainty_minutes"]
            == overrides["birth_time_uncertainty_minutes"]
        )
        assert sensitivity["maximum_recorded_sample_gap_seconds"] <= 30
        if overrides["birth_time_uncertainty_minutes"] == 5:
            assert sensitivity["sample_count"] == 21
            assert sensitivity["maximum_recorded_sample_gap_seconds"] == 30
        else:
            pass
        assert sensitivity["continuous_interval_proven"] is False
        if "birth_clock_basis" in overrides:
            base = (
                bodies[0]["base_chart"]
                if key == "astro_germany" or variant == "germany"
                else bodies[0]
            )
            conversion = base["person_info"]["clock_conversion"]
            assert conversion["input_clock_basis"] == overrides["birth_clock_basis"]
            assert conversion["input_wall_datetime"] == "1879-05-14T23:00:00"
            assert conversion["converted_utc"] == base["person_info"]["utc_datetime"]
            assert conversion["clock_accuracy_certified"] is False
            assert abs(conversion["ut1_roundtrip_error_seconds"]) <= 0.0002
            assert sensitivity["input_clock_basis"] == overrides["birth_clock_basis"]
            assert sensitivity["recorded_interval_start_clock"] == "1879-05-14T22:59:45"
            assert sensitivity["recorded_interval_end_clock"] == "1879-05-14T23:00:15"
        else:
            pass
        if "birth_second" in overrides:
            base = (
                bodies[0]["base_chart"]
                if key == "astro_germany" or variant == "germany"
                else bodies[0]
            )
            assert base["person_info"]["utc_datetime"] == "1879-05-14T22:20:50+00:00"
            first_sample, center_sample, last_sample = sensitivity["samples"]
            assert center_sample["recorded_utc"] == "1879-05-14T22:20:50+00:00"
            center_tt_days = Fraction(
                center_sample["physical_timing"]["recorded_tt_jd_exact"]
            )
            center_utc_label = datetime.fromisoformat(center_sample["recorded_utc"])
            # note (historical clock): The pre-UTC label has one native UT1 day cell plus microsecond display rounding.
            label_resolution = timedelta(
                seconds=math.ulp(center_sample["julian_day_ut1"]) * 86_400,
                microseconds=1,
            )
            for sample, offset_seconds in ((first_sample, -15), (last_sample, 15)):
                sample_tt_days = Fraction(
                    sample["physical_timing"]["recorded_tt_jd_exact"]
                )
                assert (sample_tt_days - center_tt_days) * 86_400 == offset_seconds
                sample_utc_label = datetime.fromisoformat(sample["recorded_utc"])
                expected_label = center_utc_label + timedelta(seconds=offset_seconds)
                assert abs(sample_utc_label - expected_label) <= label_resolution
        else:
            pass
    else:
        pass
    if "analysis_datetime" in overrides:
        layer = bodies[0]["midpoint_analysis"]["solar_arc_analysis"]
        assert layer["profile"]["analysis_utc"] == "2000-02-01T00:00:00+00:00"
        assert layer["profile"]["year_days"] == 365.25
        assert layer["profile"]["directed_factors_are_observations"] is False
        assert len(layer["interpretations"]) == 1
        reading = layer["interpretations"][0]
        assert reading["factor_layers"]["Midheaven"] == "solar_arc"
        assert reading["birth_time_sampled_status"] == "varies_across_samples"
        assert layer["birth_time_sensitivity"]["sample_count"] == 21
        assert layer["real_world_efficacy"] == "not_tested"
        day = layer["daily_meridian"]
        assert day["ruleset_id"] == "witte1924_ecliptic_day_meridian_v1"
        comparison = day["source_comparison"]
        assert comparison["status"] == "printed_arithmetic_difference_explained"
        assert comparison["computed_for_current_chart"] is False
        assert comparison["historical_example_difference_arcminutes"] == 184
        assert comparison["difference_is_universal_correction"] is False
        assert comparison["original_variants_fully_reconciled"] is False
        profile = day["profile"]
        assert profile["analysis_utc"] == "2000-02-01T00:00:00+00:00"
        theta = math.radians(
            profile["natal_upper_meridian_longitude"]
            + profile["solar_arc_degrees"]
            - profile["natal_tropical_sun"]
            + profile["target_tropical_sun"]
        )
        expected = math.degrees(math.atan2(math.sin(theta), math.cos(theta))) % 360
        assert profile["upper_meridian_longitude"] == pytest.approx(expected, abs=2e-12)
        assert day["birth_time_sensitivity"]["sample_count"] == 21
        assert profile["meridians_are_observations"] is False
    else:
        pass
    Draft202012Validator(spec.output_model.model_json_schema()).validate(
        response.json()
    )
