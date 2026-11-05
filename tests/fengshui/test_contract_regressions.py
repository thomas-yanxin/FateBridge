"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import hashlib
import json
from copy import deepcopy

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.fengshui.opposite import opposite_star_comparison
from fatebridge.core.fengshui.reading import _opposite_statements
from fatebridge.core.fengshui.xuankong import _chart
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import assess, calculate_xuankong_natal
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from tests.fengshui.test_fengshui_opposite import OPPOSITE_REFERENCE
from tests.fengshui.test_fengshui_structure_reading import MOUNTAINS, request
from tests.fengshui.test_fengshui_surfaces import SPECS, rest_client, without_transport


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
def test_default_budget_reads_the_same_run_and_keeps_source_difference(tool):
    value = {
        "house": {"facing_degrees": 135, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": 6,
            "evidence": "Synthetic pagination audit, not a real dwelling",
        },
        "interpretation": {"host_guest_ruleset_id": "shen_2011_host_guest_v1"},
    }
    if tool == "assess":
        value = {"methods": ["xuankong_natal"], "xuankong": value}

    async def read_original():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool("fengshui_" + tool, value)
            assert not result.is_error
            assert len(result.content[0].text) <= 8192
            inline = result.structured_content
            ref = inline["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            assert manifest["sha256"] == ref["sha256"]
            chunks, uri, offset = [], ref["first_page_uri"], 0
            while uri is not None:
                page = json.loads((await client.read_resource(uri))[0].text)
                assert page["sha256"] == ref["sha256"]
                assert page["offset"] == offset
                chunks.append(page["text"])
                offset += len(page["text"])
                assert page["next_offset"] == (
                    offset if offset < ref["total_chars"] else None
                )
                uri = page["next_uri"]
            raw = "".join(chunks)
            assert len(raw) == ref["total_chars"]
            assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
            original = json.loads(raw)
            assert original["run_metadata"] == manifest["run_metadata"]
            assert (
                original["run_metadata"]["run_id"] == inline["run_metadata"]["run_id"]
            )
            checked = verify_fengshui_reading(
                original, trusted_run_metadata=deepcopy(manifest["run_metadata"])
            )
            assert checked["status"] == "verified_served_fixed_reading"
            assert checked["host_guest_relation_count"] == 8
            assert checked["host_guest_literal_source_differences"] == 1
            assert checked["host_guest_coverage_verified"] is True
            assert checked["whole_book_conformity_established"] is False

    asyncio.run(read_original())


@pytest.mark.parametrize(
    "case", OPPOSITE_REFERENCE["cases"], ids=lambda c: c["printed_example_id"]
)
def test_each_rendered_pair_names_the_independently_printed_roles_palaces_numbers_and_condition(
    case,
):
    result = calculate_xuankong_natal(**request(case))
    reading = result["calculation_reading"]
    by_target = {
        s["target_path"]: s
        for s in reading["statements"]
        if s["kind"] == "opposite_star_pair"
    }
    prefix = "layers.xuankong_natal.candidates.0.structure.classical_patterns.opposite_star_comparison.pairs."
    assert set(by_target) == {prefix + row[0] for row in case["pairs"]}
    for mountain_direction, facing_direction, mountain, facing, total, matched in case[
        "pairs"
    ]:
        text = by_target[prefix + mountain_direction]["text"]
        assert f"山星{mountain}在{mountain_direction}宫" in text
        assert f"向星{facing}在{facing_direction}宫" in text
        assert f"已算数和{total}，" in text
        assert "对宫合十条件" + ("符合" if matched else "不符合") in text
    summary = next(
        s["text"] for s in reading["statements"] if s["kind"] == "opposite_star_summary"
    )
    assert (
        "八个有向对宫条件：" + ("符合" if case["all_eight_match"] else "不符合")
        in summary
    )


def test_summary_reads_eight_pair_result_instead_of_substituting_a_matching_center():
    # A valid pair of permutations modified for this formatter check; no claim
    # that this is a printed or genuine traditional natal case.
    index = next(i for i, m in enumerate(MOUNTAINS) if m["name"] == "寅")
    chart = deepcopy(_chart(5, (index, "lower", "synthetic_text_counterexample")))
    chart["facing_chart"]["NW"], chart["facing_chart"]["E"] = (
        chart["facing_chart"]["E"],
        chart["facing_chart"]["NW"],
    )
    chart["structure"]["classical_patterns"]["opposite_star_comparison"] = (
        opposite_star_comparison(chart)
    )
    summary = _opposite_statements(chart)[0][2]
    assert "八个有向对宫条件：不符合" in summary
    assert "中宫仅作数字相加2+8=10，数和为十条件符合" in summary
    assert "不参与八宫合取" in summary


@pytest.mark.parametrize("scene", ["home", "workstation", "shared_rental"])
@pytest.mark.parametrize("layout_flag", [{}, {"analyze_layout": False}])
def test_reference_label_does_not_create_missing_physical_facts(scene, layout_flag):
    result = assess(scene=scene, methods=[], **layout_flag)
    assert result["method_details"]["status"] == "reference_only"
    assert result["status"] == "complete"
    assert result["coverage"]["missing_inputs"] == []
    assert result["layers"] == {}
    # A completed reference lookup does not claim a completed site assessment.
    assert "layout_analysis" not in result
    assert "analysis_progress" not in result["coverage"]


def test_explicit_empty_layout_request_still_requires_observations():
    result = assess(scene="home", methods=[], analyze_layout=True)
    assert result["method_details"]["status"] == "reference_only"
    progress = result["layout_analysis"]["analysis_progress"]
    assert progress["interpretation_status"] == "insufficient_evidence"
    assert progress["follow_up"]["conclusion_candidates"]


def test_reference_with_actual_observation_retains_its_independent_assessment():
    result = assess(
        scene="workstation",
        methods=[],
        analyze_layout=False,
        form_observations=[
            {
                "object_id": "desk",
                "purpose": "desk",
                "entrance_visible": False,
                "observation_basis": "user_confirmed",
                "evidence": "正常坐姿看不到入口",
            }
        ],
    )
    progress = result["layout_analysis"]["analysis_progress"]
    assert progress["interpretation_status"] == "available"
    assert not progress["assessment_complete"]


def test_reference_intake_matches_rest_mcp_cli(monkeypatch, tmp_path, capsys):
    inputs = {
        "scene": "home",
        "methods": [],
        "analyze_layout": False,
    }
    response = rest_client(monkeypatch).post(SPECS["assess"].rest_path, json=inputs)

    async def call():
        async with Client(create_mcp_app(families="fengshui")) as client:
            return await client.call_tool(
                "fengshui_assess", {**inputs, "response_char_limit": 0}
            )

    protocol = asyncio.run(call())
    request_file = tmp_path / "reference.json"
    request_file.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(["fengshui_assess", "--request-file", str(request_file)])
    cli_result = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol.is_error
    assert code == 0
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli_result)
    )
    assert response.json()["status"] == "complete"
    assert response.json()["coverage"]["missing_inputs"] == []
