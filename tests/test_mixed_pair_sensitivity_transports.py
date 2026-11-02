"""Confirmed sample grids across actual REST/MCP/CLI, including arc-range edges."""

import asyncio
import json
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

from fatebridge import api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("target", ["2000-02-01T00:00:00Z", "2000-01-01T04:30:00Z"])
def test_mixed_pair_sample_grid_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal, target
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = {
        "name": "虚构：交错因素接口验收",
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 4,
        "birth_minute": 30,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "zodiacal": zodiacal,
        "analysis_datetime": target,
        "birth_time_uncertainty_minutes": 0.5,
    }
    if variant:
        payload["chart_variant"] = variant
    fields = [
        "midpoint_analysis.factors",
        "midpoint_analysis.solar_arc_analysis.profile",
        "midpoint_analysis.solar_arc_analysis.mixed_pair_geometry.birth_time_sensitivity",
        "midpoint_analysis.solar_arc_analysis.birth_time_sensitivity.samples",
    ]
    as_of = "2026-01-01T00:00:00Z"
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
            ("as_of", as_of),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def native():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "as_of": as_of,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    protocol = asyncio.run(native())
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(payload))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(request_file),
            "--as-of",
            as_of,
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
    assert protocol.structured_content == json.loads(protocol.content[0].text)
    bodies = []
    for label, body in [
        ("rest", response.json()),
        ("mcp", protocol.structured_content),
        ("cli", cli),
    ]:
        (tmp_path / (label + ".json")).write_text(
            json.dumps(body, sort_keys=True, ensure_ascii=False, allow_nan=False)
        )
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        bodies.append({k: v for k, v in body.items() if k != "run_metadata"})
    assert bodies[0] == bodies[1] == bodies[2]
    direction = bodies[0]["midpoint_analysis"]["solar_arc_analysis"]
    sensitivity = direction["mixed_pair_geometry"]["birth_time_sensitivity"]
    assert sensitivity["sample_count"] == 3
    assert [s["offset_seconds"] for s in sensitivity["samples"]] == [-30.0, 0.0, 30.0]
    assert sensitivity["continuous_interval_proven"] is False
    assert sensitivity["sample_frequency_is_probability"] is False
    partial = target == "2000-01-01T04:30:00Z"
    assert sensitivity["status"] == ("partial" if partial else "sampled")
    assert sensitivity["unavailable_arc_sample_count"] == (1 if partial else 0)
    for i, sample in enumerate(sensitivity["samples"]):
        solar = direction["birth_time_sensitivity"]["samples"][i]
        assert sample["offset_seconds"] == solar["offset_seconds"]
        assert sample["solar_arc_degrees"] == solar.get("solar_arc_degrees")
    new_only = 0
    for period in (90, 45):
        summary = sensitivity["summary"][str(period)]
        assert summary["evaluated_relation_groups"] == 65835
        assert sum(summary["all_group_status_counts"].values()) == 65835
        for row in sensitivity["dials"][str(period)]["contacts"]:
            names = [row[k] for k in ("id_a", "id_b", "id_c", "id_d")]
            expected_present, expected_unknown, expected_backend = [], [], []
            for i, sample in enumerate(sensitivity["samples"]):
                unavailable = (
                    sample["solar_arc_degrees"] is None
                    and row["arc_required_for_relative_condition"]
                )
                if unavailable:
                    expected_unknown.append(i)
                    continue
                raw_orbs = []
                for assignment in row["factor_layer_assignments"]:
                    if sample["solar_arc_degrees"] is None:
                        assert row["midpoint_arc_coefficient"] == 0
                        values = [
                            Fraction(sample["factor_longitudes"][n]) for n in names
                        ]
                    else:
                        values = [
                            Fraction(sample["factor_longitudes"][n])
                            + (
                                Fraction(sample["solar_arc_degrees"])
                                if assignment[n] == "solar_arc"
                                else 0
                            )
                            for n in names
                        ]
                    delta = (
                        (values[0] + values[1] - values[2] - values[3]) / 2
                        + Fraction(period, 2)
                    ) % period - Fraction(period, 2)
                    raw_orbs.append(abs(delta))
                assert len(set(raw_orbs)) == 1
                hit = raw_orbs[0] <= 1
                if hit:
                    expected_backend.append(i)
                if set(names).intersection(sample["unresolved_reference_names"]):
                    expected_unknown.append(i)
                elif hit:
                    expected_present.append(i)
            assert row["present_sample_indices"] == expected_present
            assert row["unknown_sample_indices"] == expected_unknown
            assert row["backend_hit_sample_indices"] == expected_backend
            assert row["known_absent_sample_count"] == 3 - len(expected_present) - len(
                expected_unknown
            )
            if not row["nominal_backend_condition"] and expected_backend:
                new_only += 1
            if partial and row["midpoint_arc_coefficient"] == 0:
                assert row["unknown_sample_indices"] == []
                assert row["backend_evaluable_sample_count"] == 3
            elif partial:
                assert row["unknown_sample_indices"] == [2]
    assert new_only > 0
