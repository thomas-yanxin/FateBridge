"""Primary worked evidence and explicit missing/boundary semantics, separately."""

import hashlib
import json
import shutil
from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.taiyi_gates import (
    attach_gate_board,
    gate_cycle,
    gate_frame,
)
from fatebridge.core.metaphysics.taiyi_year import (
    assemble_board,
    cyclic_core,
    yearly_core,
)
from fatebridge.core.output_taiyi_gates import TaiyiGates
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_gates import CORPUS, audit, worked_board

CASES = json.loads((CORPUS / "worked-cases.json").read_text())["cases"]


def test_complete_primary_audit_retains_failed_and_unreadable_fields():
    report = audit()
    anchors = report["gate_anchor_list"]
    assert anchors["total_rows"] == 18
    assert anchors["required_fields"] == 36
    assert anchors["checked_fields"] == 34 and anchors["matching_fields"] == 27
    assert {d["id"] for d in anchors["disagreements"]} == {"G11", "G12", "G16", "G17"}
    assert anchors["unevaluated"][0]["id"] == "G18"
    worked = report["selected_worked_examples"]
    assert worked["total_cases"] == 4
    assert worked["checked_fields"] == 32 and worked["matching_fields"] == 29
    assert {(d["id"], d["field"]) for d in worked["disagreements"]} == {
        ("key-1561-xu-month", "duty_gate"),
        ("key-1561-xu-month", "unit_in_gate"),
        ("tongzong-1634-year", "general"),
    }
    assert report["classical_gate_acceptance_passed"] is False
    assert report["calendar_adapter_validated_for_ancient_dates"] is False


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_independent_determinate_markers_and_all_three_numerical_fields(case):
    board = worked_board(case)
    det = board["determinate_calculation"]
    for field in ("marker", "count", "general", "vice_general"):
        if case["id"] == "tongzong-1634-year" and field == "general":
            assert case["expected"][field] == 3 and det[field] == 2
        else:
            assert det[field] == case["expected"][field]
    assert sum(p["value"] for p in det["trace"]["path"]) == det["count"]
    assert board["core_board"]["dingmu"] == det["marker"]
    assert board["core_board"]["set_count"] == det["count"]


def test_wubeizhi_entire_eight_gate_arrangement_and_five_gates_conjunction():
    case = next(c for c in CASES if c["id"] == "wubeizhi-1571-year")
    board = worked_board(case)
    gates = board["gates"]
    assert {str(r["number"]): r["door"] for r in gates["moving_frame"]["rows"]} == case[
        "expected"
    ]["doors"]
    assert board["condition_assessment"]["three_gates"]["conditions_satisfied"] is True
    assert (
        board["condition_assessment"]["five_generals"]["conditions_satisfied"] is False
    )
    assert board["condition_assessment"]["menju_jiangfa"] is False
    # Source says 文昌巳临死门; the sector is 巽九, not a copied
    # Qimen palace number, nor the next principal position 午二.
    eye = board["condition_assessment"]["three_gates"]["checks"][1]
    assert (eye["position"], eye["sector_number"], eye["door"]) == ("巳", 9, "死")
    assert gates["old_open_frames"]["main"]["status"] == "not_assessed"
    assert gates["old_open_frames"]["main"]["anchor_number"] == 5
    assert "主大" in board["center_marks"]["markers"]


def test_distinct_source_anchors_and_subjects_never_select_favourable_profile():
    board = worked_board(CASES[0])
    gates = board["gates"]
    assert gates["selected_profile"] == "wang_annual_240"
    assert gates["moving_frame"]["anchor_number"] == 9
    assert gates["dingmu_comparison_frame"]["anchor_number"] == 9
    assert gates["dingmu_comparison_frame"]["anchor_source_value"] == "辰"
    old = gates["old_open_frames"]
    assert set(old) == {"taiyi", "main", "guest", "determinate"}
    assert [c["label"] for c in old["taiyi"]["three_gates"]["checks"]] == ["文昌"]
    assert [c["label"] for c in old["guest"]["three_gates"]["checks"]] == [
        "太乙",
        "始击",
    ]
    assert old["determinate"]["three_gates"]["conditions_satisfied"] is None
    original = deepcopy(board["condition_assessment"])
    gates["old_open_frames"] = {}
    gates["dingmu_comparison_frame"] = None
    assert board["condition_assessment"] == original


@pytest.mark.parametrize(
    "count,door,unit",
    [
        (1, "开", 1),
        (30, "开", 30),
        (31, "休", 1),
        (60, "休", 30),
        (61, "生", 1),
        (240, "惊", 30),
        (241, "开", 1),
        (480, "惊", 30),
    ],
)
def test_inclusive_thirty_unit_and_complete_cycle_boundaries(count, door, unit):
    result = gate_cycle(count)
    assert (result["duty_gate"], result["unit_in_gate"]) == (door, unit)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, "1", None])
def test_gate_counter_does_not_coerce_invalid_or_unknown_input(value):
    with pytest.raises(ValueError):
        gate_cycle(value)


def test_same_month_core_does_not_mean_same_gate_counter():
    boards = []
    for count in (335, 695):
        core = cyclic_core(count)
        core.update(ruler_branch="戌", ruler_label="月建", heshen="卯")
        board = assemble_board(core)
        attach_gate_board(board, "month")
        boards.append(board)
    assert (
        boards[0]["core_board"]["kook_number"] == boards[1]["core_board"]["kook_number"]
    )
    assert boards[0]["gates"]["counter"]["duty_gate"] == "伤"
    assert boards[1]["gates"]["counter"]["duty_gate"] == "惊"
    assert boards[1]["gates"]["counter"]["accumulation"] == 695


def _resolve(root, path):
    for key in path.split("."):
        root = root[int(key)] if isinstance(root, list) else root[key]
    return root


@pytest.mark.parametrize("mode", ["year", "month", "hour"])
def test_public_result_and_every_gate_evidence_path_refer_to_same_chart(mode):
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        calculation_mode=mode,
        use_true_solar_time=False,
    )
    board = result["taiyi"]
    gates = board["gates"]
    TaiyiGates.model_validate(gates)
    if mode == "hour":
        assert gates["counter"] is None and gates["selected_profile"] is None
        # An actual five-general blocker is decisive even without gate rules.
        assert board["condition_assessment"]["menju_jiangfa"] is False
        assert (
            board["determinate_calculation"]["status"]
            == "not_computed_for_selected_mode"
        )
        assert board["core_board"]["set_count"] is None
        assert "天正时实" in gates["reason"]
        return
    frames = [
        gates["moving_frame"],
        gates["dingmu_comparison_frame"],
        *gates["old_open_frames"].values(),
    ]
    for frame in frames:
        assert (
            _resolve(result, frame["anchor_source_path"])
            == frame["anchor_source_value"]
        )
    checks = [board["condition_assessment"]["three_gates"]] + [
        f["three_gates"] for f in gates["old_open_frames"].values()
    ]
    for assessment in checks:
        for check in assessment.get("checks", []):
            assert _resolve(result, check["source_path"]) == check["position"]
            assert _resolve(result, check["gate_source_path"])["door"] == check["door"]
    assert board["condition_assessment"]["summary"] in result["snapshot_text"]
    assert str(board["determinate_calculation"]["count"]) in result["snapshot_text"]


def test_annual_gate_uses_same_civil_lunar_year_and_retains_center_markers():
    for day, year in [(16, 2025), (17, 2026)]:
        result = calculate_taiyi_analysis(
            analysis_year=2026,
            analysis_month=2,
            analysis_day=day,
            analysis_hour=12,
            use_true_solar_time=False,
        )
        assert result["taiyi"]["gates"]["counter"]["accumulation"] == 3361 + year - 724
    # Regression property over the supported modern range, not historical
    # evidence: attaching twice may not duplicate or drop the center marker.
    year = next(
        y
        for y in range(1940, 2101)
        if (lambda b: b["core_board"]["set_general"] == 5)(_attached(y))
    )
    board = _attached(year)
    assert "定大" in board["center_marks"]["markers"]
    previous = deepcopy(board)
    attach_gate_board(board, "year", year)
    assert board == previous
    assert board["gates"]["old_open_frames"]["determinate"]["status"] == "not_assessed"


def _attached(year):
    board = assemble_board(yearly_core(year))
    attach_gate_board(board, "year", year)
    return board


@pytest.mark.parametrize("attempt", ["drop_anchor", "drop_worked_field", "image"])
def test_source_audit_rejects_deleted_failures_even_with_refreshed_manifest(
    tmp_path, attempt
):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    if attempt == "image":
        (corpus / "key-page38.jpg").write_bytes(b"altered")
    else:
        path = corpus / (
            "gate-anchors.json" if attempt == "drop_anchor" else "worked-cases.json"
        )
        data = json.loads(path.read_text())
        if attempt == "drop_anchor":
            data["cases"].pop(10)
        else:
            del data["cases"][2]["expected"]["duty_gate"]
        path.write_text(json.dumps(data))
        manifest = json.loads((corpus / "manifest.json").read_text())
        for source in manifest["source_files"]:
            if source["file"] == path.name:
                source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (corpus / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        audit(corpus)


def test_optional_gate_contracts_reject_text_booleans_and_false_numeric_anchors():
    for payload in [
        {"moving_frame": {"anchor_number": True}},
        {"moving_frame": {"three_gates": {"conditions_satisfied": "true"}}},
        {"counter": {"accumulation": "240"}},
    ]:
        with pytest.raises(ValidationError):
            TaiyiGates.model_validate(payload)
    with pytest.raises(ValueError):
        gate_frame(True, "开", "test")
