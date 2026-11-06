"""Replacement source differences and edition scope must reach actual readings."""

import asyncio
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.fengshui import source_comparison
from fatebridge.core.fengshui.xuankong import _chart
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from tests.fengshui.test_fengshui_source_comparison import request
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import rest_client

ROOT = Path(__file__).parents[2]


def test_all_216_replacement_source_rows_are_original_numbers_not_engine_outputs():
    original = json.loads(
        (
            ROOT / "tests/data/fengshui_replacement_diagrams_v1/reference.json"
        ).read_text()
    )
    data = json.loads(source_comparison.DATA.read_text())
    lookup = {(r["period"], r["facing_mountain"]): r for r in original["rows"]}
    assert len(data["replacement_rows"]) == 216
    for row in data["replacement_rows"]:
        raw = lookup[(row["period"], row["facing_mountain"])]
        assert row["diagram"]["palaces"] == raw["palaces"]
        assert row["diagram"]["capture_sha256"] == raw["native_sha256"]
        assert row["diagram"]["pdf_page"] == raw["pdf_page"]
    assert data["source_freezes"]["replacement_diagram_reference_sha256"] == (
        "43b04b453c5ae51cb6fc6e7ebb958a6e2da58e853b254e0c69f76e1458dd0fca"
    )
    assert data["corpus"]["total_diagram_numerals"] == 11664


def test_all_declared_replacement_candidates_keep_complete_numeric_comparison():
    charts = [
        _chart(
            period,
            (i, "replacement", "Synthetic declared numeric branch, not a source angle"),
        )
        for period in range(1, 10)
        for i in range(24)
    ]
    result = source_comparison.compare_natal_sources(charts)
    summary = result["summary"]
    assert (
        summary["candidate_count"] == summary["replacement_candidates_compared"] == 216
    )
    assert (
        summary["lower_candidates_compared"]
        == summary["replacement_candidates_not_covered"]
        == 0
    )
    assert summary["computed_integrity_failure_ids"] == []
    assert summary["status"] == "selected_source_difference"
    observed = []
    for chart, row in zip(charts, result["candidates"]):
        assert row["candidate_id"] == chart["candidate_id"]
        assert "prose" not in row
        assert row["source_section"]["source_id"] == "SRC1"
        assert "申听禅" in row["source_section"]["author"]
        assert (
            row["source_section"]["prose_comparison_status"]
            == "not_transcribed_or_compared"
        )
        assert row["numeric_branch_only"] is True
        assert row["source_angle_applicability_verified"] is False
        assert row["star_name_labels_verified"] is False
        observed.extend(
            (
                chart["candidate_id"],
                d["direction"],
                d["role"],
                d["source_value"],
                d["computed_value"],
            )
            for d in row["diagram"]["differences"]
        )
    assert observed == [
        ("5:子-午:replacement", "S", "mountain", 9, 6),
        ("9:坤-艮:replacement", "S", "mountain", 7, 1),
        ("9:坤-艮:replacement", "S", "facing", 1, 7),
    ]
    assert all(
        result[k] is False
        for k in (
            "source_angle_applicability_verified",
            "star_name_labels_and_complete_prose_verified",
            "whole_book_conformity_established",
            "independent_human_expert_review_complete",
            "calendar_accuracy_verified",
            "real_world_prediction_established",
        )
    )


@pytest.mark.parametrize("period,angle,page", [(5, 174, 515), (9, 39, 582)])
def test_actual_selected_replacement_includes_edition_conflict_and_fixed_text(
    period, angle, page
):
    inputs = request(
        period,
        angle,
        interpretation={"current_period_number": 9, "period_evidence": "虚构评价九运"},
    )
    result = calculate_xuankong_natal(**inputs)
    natal = result["layers"]["xuankong_natal"]
    assert natal["chart"]["chart_mode"] == "replacement"
    row = natal["source_comparison"]["candidates"][0]
    assert row["diagram"]["pdf_page"] == page
    assert row["status"] == "selected_source_difference"
    assert any(not v for v in row["diagram"]["source_plate_permutations"].values())
    assert all(row["computed_plate_integrity"].values())
    assert result["calculation_reading"]["status"] == "rendered"
    statement = next(
        s
        for s in result["calculation_reading"]["statements"]
        if s["kind"] == "source_comparison"
        and s["target_path"].endswith("candidates.0")
    )
    assert "申听禅" in statement["text"] and "正文未转录核对" in statement["text"]
    assert "兼向适用条件和星名未验证" in statement["text"]
    for difference in row["diagram"]["differences"]:
        assert (
            f"原图{difference['source_value']}、计算{difference['computed_value']}"
            in statement["text"]
        )
    assert "layers.xuankong_natal.candidates.0" in statement["basis_paths"]
    assert (
        "layers.xuankong_natal.source_comparison.candidates.0"
        in statement["basis_paths"]
    )


def test_ambiguous_mode_candidates_all_receive_their_own_source_section():
    result = calculate_xuankong_natal(**request(5, 175.5))
    natal = result["layers"]["xuankong_natal"]
    assert {c["chart_mode"] for c in natal["candidates"]} == {"lower", "replacement"}
    summary = natal["source_comparison"]["summary"]
    assert (
        summary["lower_candidates_compared"]
        == summary["replacement_candidates_compared"]
        == 1
    )
    assert summary["replacement_candidates_not_covered"] == 0
    assert len(summary["difference_candidate_ids"]) == 1
    for chart, row in zip(
        natal["candidates"], natal["source_comparison"]["candidates"]
    ):
        assert chart["candidate_id"] == row["candidate_id"]
        assert row["source_section"]["source_id"] == (
            "SLC1" if chart["chart_mode"] == "lower" else "SRC1"
        )
        assert row["source_angle_applicability_verified"] is False


def test_literal_matching_invalid_replacement_is_not_repaired_or_accepted():
    chart = _chart(5, (12, "replacement", "Synthetic numeric branch"))
    chart["palaces"]["S"]["mountain_star_number"] = 9
    chart["mountain_chart"]["S"] = 9
    before = deepcopy(chart)
    result = source_comparison.compare_natal_sources([chart])
    assert chart == before
    row = result["candidates"][0]
    assert row["local_numeric_agreement"] is True
    assert row["diagram"]["differences"] == []
    assert (
        result["summary"]["status"]
        == row["status"]
        == "computed_plate_integrity_failure"
    )
    assert row["computed_plate_integrity"]["mountain"] is False


@pytest.mark.parametrize("period,angle", [(5, 174), (9, 39), (5, 175.5)])
@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_replacement_source_facts_are_identical_on_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, period, angle, name
):
    inputs = request(
        period,
        angle,
        interpretation={"current_period_number": 9, "period_evidence": "虚构评价九运"},
    )
    if name == "assess":
        inputs = {
            "methods": ["xuankong_natal"],
            "house": inputs["house"],
            "xuankong": {
                "period": inputs["period"],
                "interpretation": inputs["interpretation"],
            },
        }

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_" + name, {**inputs, "response_char_limit": 0}
            )

    rest = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    mcp = asyncio.run(call())
    path = tmp_path / "input.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(["fengshui_" + name, "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not mcp.is_error and code == 0
    assert (
        without_transport(rest.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    assert (
        cli["coverage"]["natal_source_comparison"]["replacement_candidates_compared"]
        >= 1
    )
    assert (
        cli["layers"]["xuankong_natal"]["source_comparison"][
            "source_angle_applicability_verified"
        ]
        is False
    )


def test_generator_builds_current_source_profile_without_engine_import():
    process = subprocess.run(
        [
            sys.executable,
            "scripts/fengshui/build_fengshui_source_comparison.py",
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert (
        "import fatebridge"
        not in (
            ROOT / "scripts/fengshui/build_fengshui_source_comparison.py"
        ).read_text()
    )
