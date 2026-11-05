"""Exact uncertainty bounds and complete, candidate-specific angle support."""

import asyncio
import json
import math
from fractions import Fraction

import pytest

from fatebridge.cli import run
from fatebridge.core.fengshui.xuankong import _selectors
from fatebridge.services.fengshui import calculate_xuankong_natal
from tests.test_fengshui_depth_audit import natal as natal_request
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport


def natal(angle, radius=0):
    data = natal_request(angle=angle)
    data["house"]["bearing_uncertainty_degrees"] = radius
    return data


def test_rounded_half_ulp_endpoints_do_not_manufacture_candidates():
    # Numerical semantics only: this does not assert physical sub-ULP accuracy.
    # These cover a palace line, a mountain line and a lower/replacement line.
    for boundary in (22.5, 7.5, 355.5):
        for side in (-math.inf, math.inf):
            angle = math.nextafter(boundary, side)
            radius = math.ulp(boundary) / 2
            assert abs(Fraction(angle) - boundary) > Fraction(radius)
            assert {s[:2] for s in _selectors(angle, radius)} == {
                s[:2] for s in _selectors(angle, 0)
            }


def test_actual_endpoint_contact_still_keeps_both_one_sided_limits():
    for boundary in (22.5, 7.5, 355.5):
        before = math.nextafter(boundary, -math.inf)
        after = math.nextafter(boundary, math.inf)
        both = {s[:2] for s in _selectors(boundary, 0)}
        assert len(both) == 2
        assert {s[:2] for s in _selectors(before, boundary - before)} == both
        assert {s[:2] for s in _selectors(after, after - boundary)} == both


def test_multiple_angle_reasons_are_retained_even_when_chart_is_unique():
    data = natal(angle=4, radius=1)
    layer = calculate_xuankong_natal(**data)["layers"]["xuankong_natal"]
    # [3, 5] spans central 子 and its same-polarity wing; one chart.
    zi = next(c for c in layer["candidates"] if c["facing"]["name"] == "子")
    assert zi["chart_mode"] == "lower"
    assert zi["mode_reason"] == "multiple_supported_angle_regions"
    support = zi["bearing_support"]
    assert support["mode_reasons"] == [
        "central_nine_degrees",
        "same_palace_same_polarity_no_replacement",
    ]
    assert support["regions"] == [
        {
            "from_degrees_exact": "3",
            "until_degrees_exact": "9/2",
            "endpoints_included": True,
            "mode_reason": "central_nine_degrees",
        },
        {
            "from_degrees_exact": "9/2",
            "until_degrees_exact": "5",
            "endpoints_included": True,
            "mode_reason": "same_palace_same_polarity_no_replacement",
        },
    ]
    # An independently confirmed sitting trigram must not discard either
    # supported angle region merely because their chart is the same.
    single = calculate_xuankong_natal(
        **{**data, "house": {**data["house"], "sitting_trigram": "离"}}
    )["layers"]["xuankong_natal"]
    assert single["status"] == "complete"
    assert single["chart"]["bearing_support"] == support


def test_north_wrap_has_all_four_candidates_and_exact_endpoint_only_support():
    result = calculate_xuankong_natal(**natal(angle=0, radius=7.5))
    layer = result["layers"]["xuankong_natal"]
    candidates = {
        (c["facing"]["name"], c["chart_mode"]): c for c in layer["candidates"]
    }
    assert set(candidates) == {
        ("壬", "replacement"),
        ("子", "replacement"),
        ("子", "lower"),
        ("癸", "lower"),
    }
    for key, boundary in [(("壬", "replacement"), "-15/2"), (("癸", "lower"), "15/2")]:
        support = candidates[key]["bearing_support"]
        assert len(support["regions"]) == 1
        assert support["regions"][0]["from_degrees_exact"] == boundary
        assert support["regions"][0]["until_degrees_exact"] == boundary
        assert support["regions"][0]["endpoints_included"]
        assert support["source_ids"] == ["X2"]
    assert "角区支持不表示概率或测量认证" in result["snapshot_text"]
    assert "[-15/2, -15/2]°" in result["snapshot_text"]
    assert result == calculate_xuankong_natal(**natal(angle=360, radius=7.5))


@pytest.mark.parametrize("angle,radius", [(0, 7.5), (6, 2), (22.5, 1), (355.5, 0)])
def test_all_reported_support_is_within_the_original_exact_measurement(angle, radius):
    layer = calculate_xuankong_natal(**natal(angle=angle, radius=radius))["layers"][
        "xuankong_natal"
    ]
    lower, upper = Fraction(angle) - Fraction(radius), Fraction(angle) + Fraction(
        radius
    )
    for chart in layer["candidates"]:
        support = chart["bearing_support"]
        assert set(support["mode_reasons"]) == {
            r["mode_reason"] for r in support["regions"]
        }
        for region in support["regions"]:
            start, end = Fraction(region["from_degrees_exact"]), Fraction(
                region["until_degrees_exact"]
            )
            assert lower <= start <= end <= upper


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
def test_exact_boundaries_and_candidate_support_match_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, tool
):
    angle = math.nextafter(22.5, -math.inf)
    data = natal(angle=angle, radius=math.ulp(22.5) / 2)
    if tool == "assess":
        data = {"methods": ["xuankong_natal"], "xuankong": data}
    http = rest_client(monkeypatch).post("/api/fengshui/" + tool, json=data)
    protocol = asyncio.run(mcp_call(tool, data))
    path = tmp_path / "angle.json"
    path.write_text(json.dumps(data))
    assert run(["fengshui_" + tool, "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    layer = http.json()["layers"]["xuankong_natal"]
    assert layer["status"] == "complete" and len(layer["candidates"]) == 1
    assert layer["chart"]["facing"]["name"] == "癸"


def test_strict_projection_keeps_new_support_on_real_mcp():
    result = asyncio.run(
        mcp_call(
            "xuankong_natal",
            {
                **natal(angle=6, radius=1),
                "fields": [
                    "layers.xuankong_natal.chart.bearing_support",
                    "rulesets",
                    "rule_trace",
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    assert not result.is_error
    support = result.structured_content["layers"]["xuankong_natal"]["chart"][
        "bearing_support"
    ]
    assert support["regions"][0]["from_degrees_exact"] == "5"
    assert support["regions"][0]["until_degrees_exact"] == "7"
    assert support["mode_reasons"] == ["same_palace_same_polarity_no_replacement"]
