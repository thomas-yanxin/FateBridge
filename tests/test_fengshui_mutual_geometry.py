"""Printed positions, directed traces and rejection of mislabelled author output."""

import asyncio
import gzip
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.fengshui import natal_interpretation as engine
from fatebridge.core.fengshui.mutual_geometry import (
    validate_author_phase,
    validate_mutual_geometry,
)
from fatebridge.core.fengshui.timeliness import classify_timeliness
from fatebridge.services import fengshui as service
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import FengshuiCalculationError
from fatebridge.validation.fengshui_mutual_geometry import (
    audit_mutual_geometry_reference,
    load_mutual_geometry_reference,
)
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from tests.test_fengshui_surfaces import mcp_call, rest_client

SOURCE = Path(__file__).parent / "fixtures/fengshui_mutual_geometry_v1"
ARCHIVE = Path(__file__).parent / "fixtures/fengshui_author_phase_fault_v1"


def inputs(current=7, angle=180):
    config = {"timeliness_ruleset_id": "wang_zhongzhou_timeliness_v1"}
    if current is not None:
        config.update(
            current_period_number=current,
            period_evidence="Synthetic explicit evaluation",
        )
    return {
        "house": {"facing_degrees": angle, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": 7,
            "evidence": "Synthetic history, not a real dwelling",
        },
        "interpretation": config,
    }


def executed(value):
    spec = next(s for s in CATALOG if s.key == "fengshui_xuankong_natal")
    return execute_tool(spec, spec.request_model.model_validate(value))


def test_all_printed_positions_and_directed_overlaps_conform_without_five_credit():
    result = audit_mutual_geometry_reference(load_mutual_geometry_reference(SOURCE))
    assert result["scoped_geometry_acceptance_passed"] is True
    assert (result["source_position_count"], result["ordered_overlap_paths"]) == (
        16,
        16,
    )
    assert result["source_conditioned_star_cases"] == 81
    assert result["five_period_geometric_derivation_verified"] is False
    assert result["whole_book_conformity_established"] is False
    assert result["real_world_prediction_established"] is False


def test_seven_example_keeps_the_two_opposite_directional_lookups_separate():
    geo = classify_timeliness(4, 7)["mutual_use_reference"]["geometry"]
    assert [
        (
            p["current_layout"],
            p["diagram_direction"],
            p["coincident_trigram"],
            p["coincident_star_number"],
        )
        for p in geo["paths"]
    ] == [("later_heaven", "W", "坎", 1), ("earlier_heaven", "SE", "巽", 4)]
    assert geo["selected_star_path_indices"] == [1]
    assert classify_timeliness(4, 7)["traditional_label"] == "死"
    two = classify_timeliness(4, 2)["mutual_use_reference"]["geometry"]
    assert two["printed_period_numbers"] == [2, 1, 4]
    assert two["diagram_derived_numbers"] == [2, 4, 1]
    assert two["diagram_members_match_table"] is True


@pytest.mark.parametrize("current", [None, 5])
def test_unknown_and_five_do_not_invent_a_trigram_or_diagram_proof(current):
    geo = classify_timeliness(2, current)["mutual_use_reference"]["geometry"]
    assert geo["paths"] == geo["diagram_derived_numbers"] == []
    assert geo["diagram_members_match_table"] is None
    assert geo["printed_period_numbers"] == ([] if current is None else [5, 2, 8])


def test_phase_and_membership_error_rejection_covers_every_star_and_period():
    for current in range(1, 10):
        for number in range(1, 10):
            actual = classify_timeliness(number, current)
            validate_author_phase(actual, number=number, current=current)
            wrong = deepcopy(actual)
            wrong["phase"] = "dormant" if actual["phase"] == "growing" else "growing"
            wrong["traditional_label"] = "死" if wrong["phase"] == "dormant" else "生"
            with pytest.raises(FengshuiCalculationError):
                validate_author_phase(wrong, number=number, current=current)
            wrong = deepcopy(actual)
            wrong["mutual_use_reference"]["numeric_membership"] = not wrong[
                "mutual_use_reference"
            ]["numeric_membership"]
            with pytest.raises(FengshuiCalculationError):
                validate_author_phase(wrong, number=number, current=current)


@pytest.mark.parametrize(
    "fault",
    [
        "swap",
        "direction",
        "paired_star",
        "members",
        "path_index",
        "boolean",
        "site_permission",
    ],
)
def test_semantically_wrong_trace_cannot_pass_with_correct_members(fault):
    geo = deepcopy(classify_timeliness(4, 7)["mutual_use_reference"]["geometry"])
    if fault == "swap":
        geo["paths"].reverse()
    elif fault == "direction":
        geo["paths"][0]["diagram_direction"] = "N"
    elif fault == "paired_star":
        geo["paths"][0]["coincident_star_number"] = 9
    elif fault == "members":
        geo["diagram_derived_numbers"] = [7, 4, 1]
    elif fault == "path_index":
        geo["selected_star_path_indices"] = [0]
    elif fault == "boolean":
        geo["diagram_derived_numbers"][1] = True
    else:
        geo["site_eligibility_established"] = True
    with pytest.raises(FengshuiCalculationError):
        validate_mutual_geometry(geo, number=4, current=7)


def test_rehashed_primary_capture_is_not_a_new_oracle(tmp_path):
    folder = tmp_path / "source"
    shutil.copytree(SOURCE, folder)
    value = json.loads((folder / "reference.json").read_text())
    value["earlier_heaven"]["W"] = "离"
    (folder / "reference.json").write_text(json.dumps(value))
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest["reference.json"] = hashlib.sha256(
        (folder / "reference.json").read_bytes()
    ).hexdigest()
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_mutual_geometry_reference(folder)


@pytest.mark.parametrize(
    "current,derived,five,unknown", [(7, 18, 0, 0), (5, 0, 18, 0), (None, 0, 0, 18)]
)
def test_served_reading_coverage_is_bound_to_the_actual_available_derivation(
    current, derived, five, unknown
):
    result = executed(inputs(current))
    checked = verify_fengshui_reading(
        result, trusted_run_metadata=deepcopy(result["run_metadata"])
    )
    assert checked["status"] == "verified_served_fixed_reading"
    assert checked["author_geometry_record_count"] == 18
    assert checked["author_geometry_derived_record_count"] == derived
    assert checked["author_geometry_five_table_only_count"] == five
    assert checked["author_geometry_unknown_count"] == unknown
    assert checked["author_geometry_coverage_verified"] is (derived > 0)
    assert (
        sum(
            s["kind"] == "mutual_use_geometry"
            for s in result["calculation_reading"]["statements"]
        )
        == 18
    )


def mutate_author(original, fault):
    def changed(number, current):
        value = original(number, current)
        if (number, current) == (4, 7):
            if fault == "phase":
                value.update(phase="growing", traditional_label="生")
            elif fault == "offset":
                value["forward_cycle_offset"] = 1
            elif fault == "membership":
                value["mutual_use_reference"]["numeric_membership"] = False
            elif fault == "geometry":
                value["mutual_use_reference"]["geometry"]["paths"].reverse()
        return value

    return changed


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
@pytest.mark.parametrize("fault", ["phase", "offset", "membership", "geometry"])
def test_injected_author_errors_are_rejected_on_all_protocols(
    monkeypatch, tmp_path, capsys, tool, fault
):
    monkeypatch.setattr(
        engine, "classify_timeliness", mutate_author(engine.classify_timeliness, fault)
    )
    value = inputs()
    if tool == "assess":
        value = {"methods": ["xuankong_natal"], "xuankong": value}
    http = rest_client(monkeypatch).post("/api/fengshui/" + tool, json=value)
    mcp = asyncio.run(mcp_call(tool, value))
    path = tmp_path / "input.json"
    path.write_text(json.dumps(value))
    code = run(["fengshui_" + tool, "--request-file", str(path), "--fields", "status"])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 503 and mcp.is_error and code == 1
    for result in (http.json(), mcp.structured_content, cli):
        assert result["error_code"] == "fengshui_calculation_inconsistent"
        assert result["retryable"] is False
        assert result["issues"][0]["path"] == "runtime.fengshui.interpretation"
        assert "calculation_reading" not in result


def test_service_seal_cannot_accept_a_self_consistent_but_wrong_candidate_star(
    monkeypatch,
):
    original = service.analyze_natal_interpretation

    def wrong(*args, **kwargs):
        value = original(*args, **kwargs)
        candidate = value["candidates"][0]
        candidate["palaces"]["N"]["mountain_star_number"] = 9
        return value

    monkeypatch.setattr(service, "analyze_natal_interpretation", wrong)
    result = executed(inputs())
    assert result["error_code"] == "fengshui_calculation_inconsistent"


@pytest.mark.parametrize(
    "label,expected",
    [("correct", "verified_served_fixed_reading"), ("fault", "rejected")],
)
def test_actual_old_run_is_judged_from_its_original_receipt_without_recomputation(
    label, expected
):
    assert (
        hashlib.sha256((ARCHIVE / "hashes.json").read_bytes()).hexdigest()
        == "6e22b780c4d043697f3332189f112f1b87fb9f5c41a573aebfa0c8fcb31a39c4"
    )
    manifest = json.loads((ARCHIVE / "hashes.json").read_text())
    for name, digest in manifest.items():
        assert hashlib.sha256((ARCHIVE / name).read_bytes()).hexdigest() == digest
    result = json.loads(
        gzip.decompress((ARCHIVE / (label + "-result.json.gz")).read_bytes())
    )
    receipt = json.loads((ARCHIVE / (label + "-trusted-receipt.json")).read_text())
    checked = verify_fengshui_reading(result, trusted_run_metadata=receipt)
    assert checked["status"] == expected
    assert checked["author_geometry_coverage_verified"] is False
    assert checked["author_geometry_record_count"] == 0
