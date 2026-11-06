"""Real REST, native MCP and CLI checks of the same specialized geometry."""

import asyncio
import hashlib
import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.application.execution import execute_tool
from fatebridge.application.result_delivery import bound_response
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload

SPECS = {spec.key: spec for spec in CATALOG}
AS_OF = "2026-10-22T00:00:00Z"


@pytest.mark.parametrize(
    "key,variant,fields,overrides",
    [
        ("astro_germany", None, ["midpoint_analysis"], {}),
        ("astro_chart13", None, ["sector_profile", "thirteen_sectors", "planets"], {}),
        (
            "astro_chart",
            "germany",
            [
                "midpoint_analysis.profile",
                "midpoint_analysis.dials.90",
                "midpoint_analysis.real_world_efficacy",
            ],
            {},
        ),
        ("astro_chart", "chart13", ["sector_profile", "thirteen_sectors"], {}),
        *[
            (
                key,
                variant,
                (
                    ["base_chart.person_info", "midpoint_analysis.time_sensitivity"]
                    if key == "astro_germany" or variant == "germany"
                    else ["person_info", "time_sensitivity"]
                ),
                {
                    "name": "条件性太阳钟时接口验收",
                    "birth_place": "Hamburg: declared city coordinates",
                    "birth_year": 1879,
                    "birth_month": 5,
                    "birth_day": 14,
                    "birth_hour": 23,
                    "birth_minute": 0,
                    "birth_timezone": None,
                    "birth_longitude": 10.0,
                    "birth_latitude": 53.55,
                    "birth_clock_basis": basis,
                    "birth_time_uncertainty_minutes": 0.25,
                },
            )
            for basis in ("local_mean_solar", "local_apparent_solar")
            for key, variant in [
                ("astro_germany", None),
                ("astro_chart", "germany"),
                ("astro_chart13", None),
                ("astro_chart", "chart13"),
            ]
        ],
        *[
            (
                key,
                variant,
                (
                    [
                        "base_chart.person_info",
                        "midpoint_analysis.profile",
                        "midpoint_analysis.time_sensitivity",
                        "midpoint_analysis.dials.90",
                    ]
                    if key == "astro_germany" or variant == "germany"
                    else [
                        "person_info",
                        "sector_profile",
                        "time_sensitivity",
                        "planets",
                    ]
                ),
                {
                    "name": "原刊时钟精度接口验收",
                    "birth_place": "Hamburg: later author city coordinates",
                    "birth_year": 1879,
                    "birth_month": 5,
                    "birth_day": 14,
                    "birth_hour": 22,
                    "birth_minute": 20,
                    "birth_second": 50,
                    "birth_timezone": "UTC",
                    "birth_longitude": 10.0,
                    "birth_latitude": 53.55,
                    "birth_time_uncertainty_minutes": 0.25,
                },
            )
            for key, variant in [
                ("astro_germany", None),
                ("astro_chart", "germany"),
                ("astro_chart13", None),
                ("astro_chart", "chart13"),
            ]
        ],
        (
            "astro_germany",
            None,
            [
                "midpoint_analysis.profile",
                "midpoint_analysis.factors",
                "midpoint_analysis.interpretations",
                "midpoint_analysis.rule_trace",
                "midpoint_analysis.sources",
            ],
            {
                "name": "虚构：敏感点接口验收",
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 4,
                "birth_minute": 30,
                "birth_timezone": "UTC",
                "birth_longitude": 0.0,
                "birth_latitude": 0.0,
            },
        ),
        (
            "astro_germany",
            None,
            ["midpoint_analysis.time_sensitivity"],
            {"birth_time_uncertainty_minutes": 5},
        ),
        (
            "astro_chart",
            "germany",
            ["midpoint_analysis.time_sensitivity"],
            {"birth_time_uncertainty_minutes": 5},
        ),
        (
            "astro_chart13",
            None,
            ["time_sensitivity"],
            {"birth_time_uncertainty_minutes": 5},
        ),
        (
            "astro_chart",
            "chart13",
            ["time_sensitivity"],
            {"birth_time_uncertainty_minutes": 5},
        ),
        *[
            (
                key,
                variant,
                [
                    "midpoint_analysis.solar_arc_analysis.profile",
                    "midpoint_analysis.solar_arc_analysis.interpretations",
                    "midpoint_analysis.solar_arc_analysis.birth_time_sensitivity",
                    "midpoint_analysis.solar_arc_analysis.daily_meridian",
                    "midpoint_analysis.solar_arc_analysis.real_world_efficacy",
                ],
                {
                    "name": "虚构：太阳弧接口验收",
                    "birth_year": 2000,
                    "birth_month": 1,
                    "birth_day": 1,
                    "birth_hour": 4,
                    "birth_minute": 30,
                    "birth_timezone": "UTC",
                    "birth_longitude": 0.0,
                    "birth_latitude": 0.0,
                    "birth_time_uncertainty_minutes": 5,
                    "analysis_datetime": "2000-02-01T00:00:00Z",
                },
            )
            for key, variant in [("astro_germany", None), ("astro_chart", "germany")]
        ],
    ],
)
def test_specialized_facts_across_three_real_surfaces(
    monkeypatch,
    capsys,
    tmp_path,
    key,
    variant,
    fields,
    overrides,
    expected_element_source_hash=None,
):
    spec = SPECS[key]
    payload = {**astro_payload(), **overrides}
    if variant:
        payload["chart_variant"] = variant
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

    async def native():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
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
    assert native_json == json.loads(protocol.content[0].text)
    for body in (response.json(), native_json, cli):
        assert body["run_metadata"]["tool_name"] == spec.run_metadata_name
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [response.json(), native_json, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    geometry = bodies[0].get("midpoint_analysis", {})
    if "meridian_houses" in geometry:
        from scripts.western.audit_meridian_house_geometry import (
            read_protocol,
            signed,
            vector_longitude,
        )

        meridian = geometry["meridian_houses"]
        profile = meridian["profile"]
        assert meridian["ruleset_id"] == "witte1923_natal_meridian_house_geometry_v1"
        assert len(meridian["cusps"]) == 12
        assert profile["first_cusp_replaces_physical_ascendant"] is False
        assert profile["base_chart_houses_replaced"] is False
        for row in meridian["cusps"]:
            expected = vector_longitude(
                row["right_ascension"], profile["true_obliquity"]
            )
            assert (
                abs(signed(row["longitude"], expected - profile["ayanamsha_apparent"]))
                <= read_protocol()["geometry_tolerance_degrees"]
            )
    if "profile" in geometry:
        physical_source = geometry["profile"]["physical_ephemeris_source"]
        assert len(physical_source["by_factor"]) == 10
        assert physical_source["accuracy_certified"] is False
        assert physical_source["atomic_file_read_proven"] is False
        assert all(
            "/" not in row["filename"] and "\\" not in row["filename"]
            for row in physical_source["files"]
        )
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
    if expected_element_source_hash is not None:
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
        if "birth_second" in overrides:
            base = (
                bodies[0]["base_chart"]
                if key == "astro_germany" or variant == "germany"
                else bodies[0]
            )
            assert base["person_info"]["utc_datetime"] == "1879-05-14T22:20:50+00:00"
            assert [row["recorded_utc"] for row in sensitivity["samples"]] == [
                "1879-05-14T22:20:35+00:00",
                "1879-05-14T22:20:50+00:00",
                "1879-05-14T22:21:05+00:00",
            ]
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
    Draft202012Validator(spec.output_model.model_json_schema()).validate(
        response.json()
    )


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
def test_custom_orbit_provenance_matches_three_transports(
    monkeypatch, capsys, tmp_path, key, variant
):
    from fatebridge.core import ephemeris_runtime
    from tests.fixtures.hamburg_orbits import write_orbits

    if ephemeris_runtime.swe is None:
        pytest.skip("Swiss Ephemeris required")
    source = write_orbits(tmp_path / "custom-orbits", cupido_anomaly="200.7409")
    previous = ephemeris_runtime.configured_ephemeris_path()
    try:
        with monkeypatch.context() as patch:
            patch.setenv("SE_EPHE_PATH", str(source.parent))
            ephemeris_runtime.configure_ephemeris_path()
            test_specialized_facts_across_three_real_surfaces(
                patch,
                capsys,
                tmp_path,
                key,
                variant,
                ["midpoint_analysis.profile", "midpoint_analysis.factors"],
                {},
                expected_element_source_hash=hashlib.sha256(
                    source.read_bytes()
                ).hexdigest(),
            )
    finally:
        ephemeris_runtime.configure_ephemeris_path(
            previous if previous is not None else ""
        )


def test_full_geometry_delivery_is_the_same_run_and_hashes_exact_bytes(
    monkeypatch, tmp_path
):
    store = delivery.ResultStore(tmp_path / "geometry-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    spec = SPECS["astro_germany"]
    result = execute_tool(
        spec,
        spec.request_model.model_validate(astro_payload()),
        options=ExecutionOptions(as_of=AS_OF),
    )
    response = bound_response(result, 8192)
    receipt = response["result_delivery"]
    chunks = []
    offset = 0
    while True:
        page = store.page(receipt["result_id"], offset)
        chunks.append(page["text"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    content = "".join(chunks)
    assert len(content) == receipt["total_chars"]
    complete = json.loads(content)
    assert (
        json.loads(Path(receipt["file_path"]).read_bytes())[
            receipt["file_payload_path"]
        ]
        == complete
    )
    assert complete["run_metadata"]["run_id"] == response["run_metadata"]["run_id"]
    assert len(complete["midpoint_analysis"]["midpoint_axes"]) == 253
    assert complete["midpoint_analysis"]["real_world_efficacy"] == "not_tested"


@pytest.mark.parametrize(
    "key,payload",
    [
        (
            "astro_germany",
            {
                "midpoint_analysis": {
                    "profile": {
                        "physical_ephemeris_source": {"files": [{"de_number": "441"}]}
                    }
                }
            },
        ),
        (
            "astro_chart",
            {
                "midpoint_analysis": {
                    "profile": {
                        "physical_ephemeris_source": {
                            "by_factor": {"Sun": {"file_ids": "not-an-array"}}
                        }
                    }
                }
            },
        ),
        (
            "astro_chart13",
            {
                "time_sensitivity": {
                    "physical_ephemeris_sources": [{"accuracy_certified": "false"}]
                }
            },
        ),
        (
            "astro_germany",
            {
                "base_chart": {
                    "person_info": {
                        "clock_conversion": {"clock_accuracy_certified": "false"}
                    }
                }
            },
        ),
        (
            "astro_chart13",
            {"person_info": {"clock_conversion": {"ut1_roundtrip_error_seconds": "0"}}},
        ),
        ("astro_germany", {"midpoint_analysis": {"factors": [{"longitude": "0"}]}}),
        (
            "astro_germany",
            {
                "midpoint_analysis": {
                    "dials": {"45": {"two_factor_contacts": [{"aspect_degrees": "45"}]}}
                }
            },
        ),
        (
            "astro_chart",
            {"midpoint_analysis": {"unique_two_factor_pair_count": "3"}},
        ),
        (
            "astro_germany",
            {
                "midpoint_analysis": {
                    "dials": {
                        "90": {
                            "three_factor_contacts": [{"contains_hypothetical": "true"}]
                        }
                    }
                }
            },
        ),
        ("astro_chart13", {"sector_profile": {"astronomical_constellations": "false"}}),
        (
            "astro_chart13",
            {"time_sensitivity": {"continuous_interval_proven": "false"}},
        ),
        (
            "astro_germany",
            {"midpoint_analysis": {"time_sensitivity": {"sample_count": "21"}}},
        ),
    ],
)
def test_new_professional_facts_reject_wrong_nested_types(key, payload):
    with pytest.raises(ValidationError):
        SPECS[key].output_model.model_validate(payload)
