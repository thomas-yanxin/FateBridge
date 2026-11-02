"""Author table fidelity and its boundary with existing site conditions."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.models import XuankongInterpretationRequest
from fatebridge.core.fengshui.timeliness import (
    classify_timeliness,
    timeliness_provenance,
)
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.fengshui_timeliness import audit_timeliness_reference
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport

REFERENCE = Path(__file__).parent / "fixtures/fengshui_timeliness_v1/reference.json"
PROFILE = "wang_zhongzhou_timeliness_v1"


def _inputs(natal=2, current=7, angle=0):
    config = {"timeliness_ruleset_id": PROFILE}
    if current is not None:
        config.update(
            current_period_number=current, period_evidence="独立核实的评价时运"
        )
    return {
        "house": {"facing_degrees": angle, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": natal,
            "evidence": "历史宅运单独确认",
        },
        "interpretation": config,
    }


def test_complete_printed_tables_and_rejected_incomplete_oracles():
    reference = json.loads(REFERENCE.read_text())
    result = audit_timeliness_reference(reference)
    assert result["checked"] == result["matched"] == 162
    assert result["whole_book_conformity_established"] is False
    assert result["real_world_prediction"] == "not_tested"
    assert result["chapter_consistency_established"] is False
    assert result["primary_source_disagreements"][0][
        "adjacent_prose_usable_numbers"
    ] == [7, 8]
    assert classify_timeliness(9, 7)["traditional_label"] == "生"
    for section in ("basic_phase_rows", "mutual_use_rows"):
        partial = deepcopy(reference)
        partial[section].pop()
        with pytest.raises(ValueError):
            audit_timeliness_reference(partial)
    bad = deepcopy(reference)
    bad["basic_phase_rows"][6]["旺"], bad["basic_phase_rows"][6]["衰"] = [5], [7, 6]
    assert audit_timeliness_reference(bad)["scoped_acceptance_passed"] is False


def test_wraparound_remote_past_and_mutual_use_are_not_interchangeable():
    assert classify_timeliness(1, 9)["phase"] == "growing"
    assert classify_timeliness(8, 1)["phase"] == "declining"
    # The author's own example: four is basically dormant in seven, yet the
    # separate mutual-use list includes it. Do not force either fact away.
    four = classify_timeliness(4, 7)
    assert four["traditional_label"] == "死"
    assert four["mutual_use_reference"]["numeric_membership"] is True
    assert classify_timeliness(5, 7)["traditional_label"] == "衰"
    assert (
        classify_timeliness(5, 7)["mutual_use_reference"]["numeric_membership"] is False
    )
    assert (
        classify_timeliness(2, 5)["mutual_use_reference"]["numeric_membership"] is True
    )
    four["mutual_use_reference"]["period_numbers"].clear()
    assert classify_timeliness(4, 7)["mutual_use_reference"]["period_numbers"] == [
        7,
        1,
        4,
    ]
    record = timeliness_provenance()
    assert (
        record["sources"][0]["retrieved_sha256"]
        == json.loads(REFERENCE.read_text())["source"]["retrieved_sha256"]
    )
    record["sources"].clear()
    assert timeliness_provenance()["sources"]


@pytest.mark.parametrize(
    "number,current", [(True, 1), (1, False), (0, 1), (1, 10), (1.0, 1)]
)
def test_strict_star_and_period_identity(number, current):
    with pytest.raises(ValueError):
        classify_timeliness(number, current)


def test_all_evaluation_periods_preserve_original_charts_and_external_conditions():
    evaluations = 0
    for current in range(1, 10):
        for natal in range(1, 10):
            for angle in (0, 6, 7.5):
                inputs = _inputs(natal, current, angle)
                base_inputs = deepcopy(inputs)
                base_inputs["interpretation"].pop("timeliness_ruleset_id")
                before = calculate_xuankong_natal(**base_inputs)
                after = calculate_xuankong_natal(**inputs)
                old_layer = before["layers"]["xuankong_natal"]
                layer = after["layers"]["xuankong_natal"]
                assert {k: v for k, v in layer.items() if k != "interpretation"} == {
                    k: v for k, v in old_layer.items() if k != "interpretation"
                }
                old = old_layer["interpretation"]
                new = layer["interpretation"]
                assert "timeliness_ruleset" not in old
                assert new["timeliness_ruleset"]["ruleset_id"] == PROFILE
                assert (
                    new["overall_auspiciousness"]
                    == old["overall_auspiciousness"]
                    == "not_produced"
                )
                for previous, candidate in zip(old["candidates"], new["candidates"]):
                    assert candidate["candidate_only"] == previous["candidate_only"]
                    for direction, palace in candidate["palaces"].items():
                        original = previous["palaces"][direction]
                        assert (
                            palace["external_form_analysis"]
                            == original["external_form_analysis"]
                        )
                        assert palace["ordered_pair"] == original["ordered_pair"]
                        for role in ("mountain", "facing"):
                            phase = palace["timeliness"][role]["author_classification"]
                            assert phase["star_number"] == palace[f"{role}_star_number"]
                            assert phase["current_period_number"] == current
                            assert phase["verdict_scope"].endswith(
                                "not_site_quality_fortune_or_action_permission"
                            )
                evaluations += 1
    assert evaluations == 243


def test_missing_period_stays_unknown_and_selection_is_strict():
    result = calculate_xuankong_natal(**_inputs(current=None))
    interpretation = result["layers"]["xuankong_natal"]["interpretation"]
    assert interpretation["status"] == "partial"
    for palace in interpretation["candidates"][0]["palaces"].values():
        for role in ("mountain", "facing"):
            phase = palace["timeliness"][role]["author_classification"]
            assert phase["phase"] == "unknown"
            assert phase["mutual_use_reference"]["numeric_membership"] is None
    invalid = {"timeliness_ruleset_id": "unregistered_folklore"}
    with pytest.raises(ValidationError):
        XuankongInterpretationRequest.model_validate(invalid)
    assert not Draft202012Validator(
        XuankongInterpretationRequest.model_json_schema()
    ).is_valid(invalid)


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
def test_author_profile_rest_mcp_cli_schema_and_snapshot(
    monkeypatch, tmp_path, capsys, tool
):
    inputs = _inputs()
    if tool == "assess":
        inputs = {"methods": ["xuankong_natal"], "xuankong": inputs}
    spec = next(s for s in CATALOG if s.key == "fengshui_" + tool)
    response = rest_client(monkeypatch).post(spec.rest_path, json=inputs)
    assert response.status_code == 200, response.text
    protocol = asyncio.run(mcp_call(tool, inputs))
    assert not protocol.is_error
    request_file = tmp_path / "author.json"
    request_file.write_text(json.dumps(inputs))
    assert run(["fengshui_" + tool, "--request-file", str(request_file)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    Draft202012Validator(spec.output_model.model_json_schema()).validate(cli)
    interpretation = cli["layers"]["xuankong_natal"]["interpretation"]
    assert interpretation["timeliness_ruleset"]["sources"][0]["source_id"] == "WZT1"
    assert any(r["ruleset_id"] == PROFILE for r in cli["rulesets"])
    assert any(r.get("ruleset_id") == PROFILE for r in cli["rule_trace"])
    assert any(
        r["rule_id"] == PROFILE + ".basic_phase" for r in interpretation["rule_trace"]
    )
    assert "王氏基本时令" in cli["snapshot_text"]
    assert "不证明现场可用" in cli["snapshot_text"]
