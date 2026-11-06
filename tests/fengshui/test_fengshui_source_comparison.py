"""Known printed disagreements must reach every relevant computed candidate."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.fengshui import source_comparison
from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.core.fengshui.xuankong import xuankong_natal
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from tests.fixtures.mcp_result_delivery import read_full_result
from tests.support.mcp_result_assertions import (
    same_run_projected_response,
    without_transport,
)
from tests.support.result_delivery import (
    assert_same_run_receipt as assert_stored_result,
)
from tests.support.result_delivery import store
from tests.support.transports import rest_client


def request(period=7, facing=60, **extra):
    return {
        "house": {"facing_degrees": facing, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": period,
            "evidence": "虚构固定宅盘，用于原书数表与引擎差异核对",
        },
        **extra,
    }


@pytest.mark.parametrize("period,facing", [(7, 60), (4, 270), (1, 90)])
def test_known_printed_disagreements_reach_the_actual_response(period, facing):
    output = calculate_xuankong_natal(**request(period, facing))
    natal = output["layers"]["xuankong_natal"]
    comparison = natal["source_comparison"]
    assert natal["status"] == "complete"
    assert comparison["summary"]["status"] == "selected_source_difference"
    assert comparison["summary"]["difference_candidate_ids"] == [
        natal["chart"]["candidate_id"]
    ]
    assert comparison["whole_book_conformity_established"] is False
    assert output["coverage"]["natal_source_comparison"] == comparison["summary"]
    if period == 7:
        assert natal["chart"]["palaces"]["E"]["mountain_star_number"] == 2
        row = comparison["candidates"][0]
        assert row["diagram"]["source_palaces"]["E"]["mountain"] == 5
        assert row["diagram"]["differences"] == [
            {
                "direction": "E",
                "role": "mountain",
                "source_value": 5,
                "computed_value": 2,
            }
        ]
        assert row["diagram"]["pdf_page"] == 353
        assert "原图5、计算2" in output["snapshot_text"]


def test_packaged_corpus_contains_every_frozen_source_row_without_correction():
    root = Path(__file__).parents[2]
    packaged = json.loads(
        (
            root / "src/fatebridge/data/fengshui/shen-natal-source-comparison-v2.json"
        ).read_text()
    )
    diagrams = json.loads(
        (root / "tests/data/fengshui_lower_diagrams_v1/reference.json").read_text()
    )
    clauses = json.loads(
        (root / "tests/data/fengshui_lower_clauses_v1/reference.json").read_text()
    )
    assert len(packaged["rows"]) == len(diagrams["rows"]) == len(clauses["rows"]) == 216
    originals = {(r["period"], r["facing_mountain"]): r for r in diagrams["rows"]}
    prose = {(r["period"], r["facing_mountain"]): r for r in clauses["rows"]}
    for row in packaged["rows"]:
        key = (row["period"], row["facing_mountain"])
        assert row["diagram"]["palaces"] == originals[key]["palaces"]
        assert row["prose"]["numeric_profile"] == {
            name: prose[key][name]
            for name in (
                "mountain_seed",
                "facing_seed",
                "mountain_flight",
                "facing_flight",
            )
        }


def test_all_216_lower_candidates_retain_every_audited_disagreement():
    observed = {}
    prose_profiles = diagram_numerals = matched_numerals = 0
    for period in range(1, 10):
        for index, mountain in enumerate(source_comparison.MOUNTAINS):
            # Source order begins 子 at north; every next mountain is 15 degrees.
            result = xuankong_natal(
                XuankongRequest.model_validate(request(period, index * 15))
            )
            row = result["source_comparison"]["candidates"][0]
            assert row["candidate_id"] == result["chart"]["candidate_id"]
            assert all(row["computed_plate_integrity"].values())
            prose_profiles += not row["prose"]["differences"]
            diagram_numerals += row["diagram"]["checked_numerals"]
            matched_numerals += 27 - len(row["diagram"]["differences"])
            if row["status"] != "selected_numeric_passages_match":
                observed[(period, mountain)] = (
                    len(row["prose"]["differences"]),
                    len(row["diagram"]["differences"]),
                )
    assert prose_profiles == 213
    assert diagram_numerals == 5832 and matched_numerals == 5831
    assert observed == {
        (4, "酉"): (2, 0),
        (1, "卯"): (1, 0),
        (6, "乾"): (1, 0),
        (7, "寅"): (0, 1),
    }


def test_every_boundary_candidate_is_compared_without_selecting_one_mode():
    for index in range(24):
        result = xuankong_natal(
            XuankongRequest.model_validate(request(7, index * 15 + 7.5))
        )
        comparison = result["source_comparison"]
        assert len(result["candidates"]) > 1
        assert [r["candidate_id"] for r in comparison["candidates"]] == [
            r["candidate_id"] for r in result["candidates"]
        ]
        assert comparison["summary"]["candidate_count"] == len(result["candidates"])
        for chart, row in zip(result["candidates"], comparison["candidates"]):
            assert ("prose" in row) is (chart["chart_mode"] == "lower")
            if chart["chart_mode"] == "replacement":
                assert row["diagram"]["checked_numerals"] == 27
                assert row["status"] == "selected_numeric_passages_match"
                assert row["local_numeric_agreement"] is True
                assert (
                    row["source_section"]["prose_comparison_status"]
                    == "not_transcribed_or_compared"
                )
            assert row["source_angle_applicability_verified"] is False


def test_comparison_does_not_mutate_or_repair_an_invalid_literal_matching_chart():
    chart = xuankong_natal(XuankongRequest.model_validate(request()))["chart"]
    original = deepcopy(chart)
    source_comparison.compare_natal_sources([chart])
    assert chart == original
    altered = deepcopy(chart)
    altered["palaces"]["E"]["mountain_star_number"] = 5
    altered["mountain_chart"]["E"] = 5
    result = source_comparison.compare_natal_sources([altered])
    row = result["candidates"][0]
    assert row["diagram"]["differences"] == []
    assert row["local_numeric_agreement"] is True
    assert row["computed_plate_integrity"]["mountain"] is False
    assert (
        row["status"]
        == result["summary"]["status"]
        == "computed_plate_integrity_failure"
    )
    assert result["whole_book_conformity_established"] is False


def test_arbitrary_permutation_preserving_wrong_cells_are_not_hidden_by_integrity():
    chart = xuankong_natal(XuankongRequest.model_validate(request(2, 180)))["chart"]
    for role in source_comparison.ROLES:
        for index, first in enumerate(source_comparison.DIRECTIONS):
            second = source_comparison.DIRECTIONS[(index + 1) % 9]
            changed = deepcopy(chart)
            a, b = (
                chart["palaces"][first][role + "_star_number"],
                chart["palaces"][second][role + "_star_number"],
            )
            for direction, value in ((first, b), (second, a)):
                changed["palaces"][direction][role + "_star_number"] = value
                changed[role + "_chart"][direction] = value
            row = source_comparison.compare_natal_sources([changed])["candidates"][0]
            assert all(row["computed_plate_integrity"].values())
            assert len(row["diagram"]["differences"]) == 2
            assert row["local_numeric_agreement"] is False


@pytest.mark.parametrize("mode", ["missing", "replacement"])
def test_uncomputed_has_no_match_and_replacement_only_receives_numeric_comparison(mode):
    request_data = {} if mode == "missing" else request(7, 126)
    output = calculate_xuankong_natal(**request_data)
    summary = output["coverage"]["natal_source_comparison"]
    assert summary["status"] == (
        "not_computed" if mode == "missing" else "selected_numeric_passages_match"
    )
    assert summary["lower_candidates_compared"] == 0
    assert summary["replacement_candidates_compared"] == (mode == "replacement")
    assert summary["source_angle_applicability_verified"] is False
    assert summary["whole_book_conformity_established"] is False


def test_packaged_source_cannot_be_silently_corrected_to_the_engine(
    monkeypatch, tmp_path
):
    raw = json.loads(source_comparison.DATA.read_text())
    row = next(
        r for r in raw["rows"] if r["period"] == 7 and r["facing_mountain"] == "寅"
    )
    row["diagram"]["palaces"]["E"]["mountain"] = 2
    changed = tmp_path / "source.json"
    changed.write_text(json.dumps(raw, ensure_ascii=False))
    source_comparison._bundle.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(source_comparison, "DATA", changed)
            with pytest.raises(RuntimeError, match="fixed edition"):
                source_comparison.comparison_provenance()
    finally:
        source_comparison._bundle.cache_clear()


@pytest.mark.parametrize("period,facing", [(7, 60), (4, 270), (9, 180), (7, 126)])
@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_source_comparison_matches_actual_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, period, facing, name
):
    inputs = request(period, facing)
    if name == "assess":
        inputs = {
            "methods": ["xuankong_natal"],
            "house": inputs["house"],
            "xuankong": {"period": inputs["period"]},
        }

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_" + name, {**inputs, "response_char_limit": 0}
            )

    response = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    protocol = asyncio.run(call())
    path = tmp_path / "source-case.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(["fengshui_" + name, "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    assert (
        cli["layers"]["xuankong_natal"]["source_comparison"]["summary"]
        == cli["coverage"]["natal_source_comparison"]
    )


def test_fixed_reading_includes_both_printed_and_computed_values_with_complete_basis():
    inputs = request(
        interpretation={
            "current_period_number": 9,
            "period_evidence": "明确的虚构评价九运",
        }
    )
    output = calculate_xuankong_natal(**inputs)
    reading = output["calculation_reading"]
    assert reading["status"] == "rendered"
    statements = [s for s in reading["statements"] if s["kind"] == "source_comparison"]
    assert len(statements) == 2
    assert "原图5、计算2" in statements[1]["text"]
    assert "layers.xuankong_natal.candidates.0" in statements[1]["basis_paths"]
    assert (
        "layers.xuankong_natal.source_comparison.candidates.0"
        in statements[1]["basis_paths"]
    )
    assert (
        reading["basis"]["layers.xuankong_natal.source_comparison.candidates.0"][
            "diagram"
        ]["source_palaces"]["E"]["mountain"]
        == 5
    )


def test_evaluation_period_does_not_change_the_historical_source_row():
    expected = calculate_xuankong_natal(**request())["layers"]["xuankong_natal"][
        "source_comparison"
    ]
    for period in range(1, 10):
        result = calculate_xuankong_natal(
            **request(
                interpretation={
                    "current_period_number": period,
                    "period_evidence": "独立虚构评价运",
                }
            )
        )
        assert result["layers"]["xuankong_natal"]["source_comparison"] == expected


def test_invalid_computation_preserves_both_integrity_and_source_difference_flags():
    chart = xuankong_natal(XuankongRequest.model_validate(request()))["chart"]
    chart["palaces"]["E"]["mountain_star_number"] = 1
    chart["mountain_chart"]["E"] = 1
    result = source_comparison.compare_natal_sources([chart])
    assert result["summary"]["difference_candidate_ids"] == [chart["candidate_id"]]
    assert result["summary"]["computed_integrity_failure_ids"] == [
        chart["candidate_id"]
    ]


@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_default_mcp_budget_keeps_source_difference_facts(name):
    inputs = request()
    if name == "assess":
        inputs = {
            "methods": ["xuankong_natal"],
            "house": inputs["house"],
            "xuankong": {"period": inputs["period"]},
        }

    async def call():
        async with Client(create_mcp_app(families="fengshui")) as client:
            response = await client.call_tool(
                "fengshui_" + name,
                {
                    **inputs,
                    "fields": [
                        "coverage.natal_source_comparison",
                        "layers.xuankong_natal.source_comparison",
                        "layers.xuankong_natal.chart.palaces.E",
                    ],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            return await same_run_projected_response(client, response)

    original = asyncio.run(call())
    natal = original["layers"]["xuankong_natal"]
    assert natal["chart"]["palaces"]["E"]["mountain_star_number"] == 2
    assert (
        natal["source_comparison"]["candidates"][0]["diagram"]["source_palaces"]["E"][
            "mountain"
        ]
        == 5
    )
    assert (
        original["coverage"]["natal_source_comparison"]["status"]
        == "selected_source_difference"
    )


@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_same_run_full_pages_and_independent_receipt_preserve_source_disagreement(
    name, store
):
    inputs = request(
        interpretation={
            "current_period_number": 9,
            "period_evidence": "独立虚构评价九运",
        }
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
        async with Client(create_mcp_app(families="fengshui")) as client:
            response = await client.call_tool(
                "fengshui_" + name,
                {**inputs, "fields": None, "response_char_limit": 4096},
            )
            assert not response.is_error and len(response.content[0].text) <= 4096
            ref = response.structured_content["result_delivery"]
            original = await read_full_result(client, response.structured_content)
            trusted = store.get(ref["result_id"])
            assert_stored_result(store, response.structured_content, trusted)
            return original, trusted

    original, trusted = asyncio.run(call())
    assert original == trusted
    assert original["run_metadata"] == trusted["run_metadata"]
    natal = original["layers"]["xuankong_natal"]
    assert natal["chart"]["palaces"]["E"]["mountain_star_number"] == 2
    assert (
        natal["source_comparison"]["candidates"][0]["diagram"]["source_palaces"]["E"][
            "mountain"
        ]
        == 5
    )
    assert "原图5、计算2" in original["calculation_reading"]["text"]
    assert (
        verify_fengshui_reading(original, trusted_payload=trusted)["status"]
        == "verified_served_fixed_reading"
    )
    changed = deepcopy(original)
    changed["layers"]["xuankong_natal"]["source_comparison"]["candidates"][0][
        "diagram"
    ]["source_palaces"]["E"]["mountain"] = 2
    assert (
        verify_fengshui_reading(changed, trusted_payload=trusted)["status"]
        == "rejected"
    )
