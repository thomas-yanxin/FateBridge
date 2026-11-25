"""Portable controls for Xuan Kong source editions and qualified chart candidates."""

import math
from pathlib import Path

import pytest

from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.core.fengshui.xuankong import xuankong_natal
from tests.support.fengshui_transports import SPECS
from tests.support.transports import three_surfaces


def request(period_number: int, facing_degrees: float) -> dict:
    return {
        "house": {"facing_degrees": facing_degrees, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": period_number,
            "evidence": "虚构固定宅盘，用于原书数表与引擎差异核对",
        },
    }


@pytest.mark.parametrize(
    "period_number,facing_degrees,mountain_numbers,facing_numbers,prose_differences,diagram_differences",
    [
        (4, 270, [2, 3, 4, 5, 6, 7, 8, 9, 1], [6, 7, 8, 9, 1, 2, 3, 4, 5], 2, 0),
        (1, 90, [3, 2, 1, 9, 8, 7, 6, 5, 4], [8, 9, 1, 2, 3, 4, 5, 6, 7], 1, 0),
        (6, 315, [5, 6, 7, 8, 9, 1, 2, 3, 4], [7, 6, 5, 4, 3, 2, 1, 9, 8], 1, 0),
        (7, 60, [4, 5, 6, 7, 8, 9, 1, 2, 3], [1, 9, 8, 7, 6, 5, 4, 3, 2], 0, 1),
    ],
)
def test_disputed_prints_keep_independently_counted_flights(
    period_number: int,
    facing_degrees: float,
    mountain_numbers: list[int],
    facing_numbers: list[int],
    prose_differences: int,
    diagram_differences: int,
) -> None:
    """Literal print disagreements cannot change a complete nine-star flight."""
    result = xuankong_natal(
        XuankongRequest.model_validate(request(period_number, facing_degrees))
    )
    chart = result["chart"]
    flight_path = ("C", "NW", "W", "NE", "S", "N", "SW", "E", "SE")
    assert [
        chart["mountain_chart"][direction] for direction in flight_path
    ] == mountain_numbers
    assert [
        chart["facing_chart"][direction] for direction in flight_path
    ] == facing_numbers
    comparison = result["source_comparison"]["candidates"][0]
    assert len(comparison["prose"]["differences"]) == prose_differences
    assert len(comparison["diagram"]["differences"]) == diagram_differences


@pytest.mark.parametrize(
    "facing_degrees,expected_modes",
    [
        (math.nextafter(64.5, -math.inf), ["lower"]),
        (64.5, ["lower", "replacement"]),
        (math.nextafter(64.5, math.inf), ["replacement"]),
        (60, ["lower"]),
    ],
)
def test_edition_and_dispute_survive_real_boundary_transports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    facing_degrees: float,
    expected_modes: list[str],
) -> None:
    """Both boundary candidates retain their own source scope and printed values."""
    fields = [
        "layers.xuankong_natal",
        "coverage.natal_source_comparison",
        "rulesets",
        "rule_trace",
    ]
    output = three_surfaces(
        SPECS["xuankong_natal"],
        request(7, facing_degrees),
        fields,
        "2026-11-25T00:00:00Z",
        tmp_path,
        monkeypatch,
        capsys,
    )
    natal = output["layers"]["xuankong_natal"]
    assert [chart["chart_mode"] for chart in natal["candidates"]] == expected_modes
    assert natal["status"] == ("complete" if len(expected_modes) == 1 else "partial")
    rules = {record["ruleset_id"]: record for record in output["rulesets"]}
    assert rules["xuankong_zhongzhou_v1"]["version"] == "1.4.0"
    comparison = natal["source_comparison"]
    assert comparison["ruleset"]["version"] == "2.0.0"
    citations = rules[comparison["ruleset"]["ruleset_id"]]["source_citations"]
    assert set(citations) == set(comparison["ruleset"]["source_ids"]) == {"SLC1", "SRC1"}
    assert all(
        "2011年6月第1版、2016年2月第3次印刷" in citation["source_version"]
        for citation in citations.values()
    )
    assert output["coverage"]["natal_source_comparison"] == comparison["summary"]
    assert len(comparison["candidates"]) == len(expected_modes)
    traces = {record["ruleset_id"]: record for record in output["rule_trace"]}
    for ruleset_id in (
        "xuankong_zhongzhou_v1",
        "shen_2011_natal_numeric_comparison_v2",
    ):
        assert traces[ruleset_id]["version"] == rules[ruleset_id]["version"]
        assert traces[ruleset_id]["source_ids"] == rules[ruleset_id]["source_ids"]
    for chart, reference in zip(natal["candidates"], comparison["candidates"]):
        assert chart["candidate_id"] == reference["candidate_id"]
        assert reference["source_angle_applicability_verified"] is False
        if chart["chart_mode"] == "lower":
            assert chart["palaces"]["E"]["mountain_star_number"] == 2
            assert reference["diagram"]["source_palaces"]["E"]["mountain"] == 5
            assert reference["diagram"]["pdf_page"] == 353
        else:
            assert reference["source_section"]["source_id"] == "SRC1"
            assert "申听禅" in reference["source_section"]["author"]
            assert "prose" not in reference


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
@pytest.mark.parametrize(
    "case", ["boundary", "missing_period", "missing_bearing", "unique"]
)
def test_natal_candidates_preserve_confirmed_and_missing_facts(
    tool: str,
    case: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = request(8, 355.5 if case == "boundary" else 255)
    if case == "missing_period":
        del inputs["period"]
    if case == "missing_bearing":
        del inputs["house"]["facing_degrees"]
    if tool == "assess":
        inputs = {"methods": ["xuankong_natal"], "xuankong": inputs}
    fields = [
        f"layers.xuankong_natal.{field}"
        for field in (
            "status",
            "period_context",
            "orientation_context",
            "candidates",
            "missing_inputs",
            "chart",
        )
    ] + ["rulesets", "rule_trace"]
    result = three_surfaces(
        SPECS[tool],
        inputs,
        fields,
        "2026-11-25T00:00:00Z",
        tmp_path,
        monkeypatch,
        capsys,
    )
    natal = result["layers"]["xuankong_natal"]
    assert result["rulesets"] and result["rule_trace"]
    assert natal["orientation_context"]["uncertainty_degrees"] == 0
    assert (
        len(natal["candidates"])
        == {"boundary": 2, "missing_period": 0, "missing_bearing": 0, "unique": 1}[case]
    )
    if case == "unique":
        assert natal["chart"] == natal["candidates"][0]
        assert not natal["missing_inputs"]
    else:
        assert natal["chart"] is None
        assert natal["missing_inputs"]
    if case == "missing_period":
        assert natal["period_context"] is None
    if case == "missing_bearing":
        assert natal["orientation_context"]["facing_degrees"] is None
