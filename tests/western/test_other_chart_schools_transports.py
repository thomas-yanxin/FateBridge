"""Real REST, native MCP and CLI checks of the same specialized geometry."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import JsonValue, ValidationError

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.application.execution import execute_tool
from fatebridge.application.result_delivery import bound_response
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload
from tests.support.transports import call_calculation
from tests.unit_test.fixtures.western_specialty import (
    AS_OF,
    assert_specialized_facts_across_surfaces,
)

SPECS = {spec.key: spec for spec in CATALOG}


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
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    key: str,
    variant: str | None,
    fields: list[str],
    overrides: dict[str, JsonValue],
) -> None:
    assert_specialized_facts_across_surfaces(
        monkeypatch, capsys, tmp_path, key, variant, fields, overrides
    )


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
def test_custom_orbit_provenance_matches_three_transports(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    key: str,
    variant: str | None,
) -> None:
    from fatebridge.core import ephemeris_runtime
    from tests.fixtures.hamburg_orbits import write_orbits

    if ephemeris_runtime.swe is None:
        pytest.skip("Swiss Ephemeris required")
    else:
        pass
    source = write_orbits(tmp_path / "custom-orbits", cupido_anomaly="200.7409")
    previous = ephemeris_runtime.configured_ephemeris_path()
    try:
        with monkeypatch.context() as patch:
            patch.setenv("SE_EPHE_PATH", str(source.parent))
            ephemeris_runtime.configure_ephemeris_path()
            assert_specialized_facts_across_surfaces(
                patch,
                capsys,
                tmp_path,
                key,
                variant,
                ["midpoint_analysis.profile", "midpoint_analysis.factors"],
                {},
                expect_external_elements=True,
            )
    finally:
        ephemeris_runtime.configure_ephemeris_path(
            previous if previous is not None else ""
        )


def test_full_geometry_delivery_is_the_same_run_and_hashes_exact_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
        else:
            pass
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
    assert "real_world_efficacy" not in complete["midpoint_analysis"]


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
def test_new_professional_facts_reject_wrong_nested_types(key: str, payload) -> None:
    with pytest.raises(ValidationError):
        SPECS[key].output_model.model_validate(payload)
