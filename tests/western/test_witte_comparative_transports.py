"""Actual specialty transports and independent reconstruction of returned inputs."""

import asyncio
import json
import math
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

from fatebridge import api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG

FRAME_TARGETS = {
    "sun_capricorn": ("Sun", 270),
    "meridian_cancer": ("Midheaven", 90),
    "ascendant_libra": ("Ascendant", 180),
    "moon_cancer": ("Moon", 90),
    "node_libra": ("North Node", 180),
}


def display(value):
    return min(float(value % 360), math.nextafter(360.0, 0.0))


def exact_groups(values):
    v = {name: Fraction(value) for name, value in values.items()}
    groups = {"radix": v}
    for key, (anchor, target) in FRAME_TARGETS.items():
        groups[key] = {
            name: (number - v[anchor] + v["Aries Point"] + target) % 360
            for name, number in v.items()
        }
    return {
        group: {
            name: {
                "original": number % 360,
                "opposition": (number + 180) % 360,
                "solstitial_reflection": (2 * v["Aries Point"] + 180 - number) % 360,
                "reflection_opposition": (2 * v["Aries Point"] - number) % 360,
            }
            for name, number in points.items()
        }
        for group, points in groups.items()
    }


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("radius", [None, 0, 0.5])
def test_comparative_geometry_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal, radius
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = {
        "name": "虚构：Witte比较坐标接口核验",
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 12,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "birth_longitude": 10.0,
        "birth_latitude": 20.0,
        "zodiacal": zodiacal,
    }
    if variant:
        payload["chart_variant"] = variant
    if radius is not None:
        payload["birth_time_uncertainty_minutes"] = radius
    fields = [
        "midpoint_analysis.factors",
        "midpoint_analysis.comparative_geometry",
        "midpoint_analysis.time_sensitivity",
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
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload, ensure_ascii=False))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(request),
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
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        (tmp_path / f"{label}.json").write_text(
            json.dumps(
                body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            )
        )
        body = dict(body)
        body.pop("run_metadata")
        bodies.append(body)
    assert bodies[0] == bodies[1] == bodies[2]
    layer = bodies[0]["midpoint_analysis"]
    g = layer["comparative_geometry"]
    assert g["status"] == "computed" and g["profile"]["native_factor_count"] == 22
    assert not g["profile"]["coordinates_are_new_observations"]
    assert (
        g["original_text_conformance"] == "not_assessed"
        and g["real_world_efficacy"] == "not_tested"
    )
    nominal = exact_groups({f["id"]: f["longitude"] for f in layer["factors"]})
    for group, expected in nominal.items():
        rows = (
            g["radix_systems"]
            if group == "radix"
            else g["frames"][group]["factor_systems"]
        )
        for name, points in expected.items():
            assert rows[name]["longitudes"] == {
                k: display(v) for k, v in points.items()
            }
            assert rows[name]["unique_point_count"] == len(set(points.values()))
    sensitivity = g["birth_time_sensitivity"]
    assert (
        not sensitivity["continuous_interval_proven"]
        and not sensitivity["sample_frequency_is_probability"]
    )
    if radius is None:
        assert (
            sensitivity["status"] == "not_assessed"
            and sensitivity["sample_count"] is None
        )
        assert sensitivity["point_spans"] is None and sensitivity["samples"] is None
        return
    count = 1 if radius == 0 else 3
    assert sensitivity["status"] == "sampled" and sensitivity["sample_count"] == count
    source = layer["time_sensitivity"]["samples"]
    assert len(sensitivity["samples"]) == len(source) == count
    samples = []
    for index, (derived, original) in enumerate(zip(sensitivity["samples"], source)):
        assert derived["sample_index"] == index
        for field in (
            "factor_longitudes",
            "julian_day_tt",
            "effective_utc",
            "recorded_utc",
            "offset_seconds",
        ):
            assert derived[field] == original[field]
        assert (
            derived["native_sample_reference"]
            == f"midpoint_analysis.time_sensitivity.samples[{index}]"
        )
        samples.append(exact_groups(original["factor_longitudes"]))
        for group, rows in samples[-1].items():
            for name, coordinates in rows.items():
                actual = derived["point_systems"][group][name]
                assert actual["longitudes"] == {
                    key: display(value) for key, value in coordinates.items()
                }
                assert actual["unique_point_count"] == len(set(coordinates.values()))
    for group, rows in nominal.items():
        for name, coordinates in rows.items():
            span = sensitivity["point_spans"][group][name]
            assert (
                span["resolved_sample_count"] == count
                and span["unresolved_sample_count"] == 0
            )
            for coordinate, number in coordinates.items():
                offsets = [
                    (sample[group][name][coordinate] - number + 180) % 360 - 180
                    for sample in samples
                ]
                expected = {
                    "minimum": float(min(offsets)),
                    "maximum": float(max(offsets)),
                }
                assert (
                    span["known_sampled_signed_offsets_from_nominal"][coordinate]
                    == expected
                )
                assert (
                    span["backend_sampled_signed_offsets_from_nominal"][coordinate]
                    == expected
                )
