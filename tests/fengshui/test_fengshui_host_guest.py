"""Source-bound host/guest operations, retained disagreements and fail-closed text."""

import asyncio
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.fengshui import host_guest, natal_interpretation, reading
from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.core.fengshui.xuankong import _bundle, _chart
from fatebridge.services import fengshui as service
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import FengshuiCalculationError
from fatebridge.validation.fengshui_host_guest import (
    audit_host_guest_reference,
    load_host_guest_reference,
)
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from tests.support.fengshui_transports import mcp_call
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import rest_client

SOURCE = Path(__file__).parents[1] / "data/fengshui_host_guest_v1"


def inputs():
    return {
        "house": {"facing_degrees": 135, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": 6,
            "evidence": "Synthetic source audit, not a real dwelling",
        },
        "interpretation": {"host_guest_ruleset_id": "shen_2011_host_guest_v1"},
    }


def executed(value):
    spec = next(s for s in CATALOG if s.key == "fengshui_xuankong_natal")
    return execute_tool(spec, spec.request_model.model_validate(value))


def analysis(result):
    return result["layers"]["xuankong_natal"]["interpretation"]["host_guest_analysis"]


def test_all_source_roles_stay_in_the_denominator_without_per_case_basis_switching():
    report = audit_host_guest_reference(load_host_guest_reference(SOURCE))
    assert report["scoped_operation_definitions_passed"] is True
    assert report["derived_operation_cases"] == 81
    assert report["source_clause_count"] == 216
    assert (
        report["source_role_count_checked"]
        == report["source_role_count_required"]
        == 432
    )
    assert report["source_role_matches"] == 422
    assert len(report["source_role_differences"]) == 6
    assert len(report["source_role_ambiguous"]) == 4
    assert report["complete_literal_relation_acceptance_passed"] is False
    assert report["per_case_basis_substitution_used"] is False
    assert report["source_angle_applicability_verified"] is False
    assert report["whole_book_conformity_established"] is False
    assert report["real_world_prediction_established"] is False


def test_every_declared_numeric_chart_and_both_modes_use_eight_separate_relations():
    for period in range(1, 10):
        for index in range(24):
            for mode in ("lower", "replacement"):
                chart = _chart(period, (index, mode, "Declared numeric unit case"))
                natal = {"candidates": [chart]}
                value = host_guest.analyze(natal)
                counts = host_guest.validate({"host_guest_analysis": value}, natal)
                assert counts["relations"] == 8
                item = value["candidates"][0]
                assert len(item["unassigned_palaces"]) == 7
                assert item["unassigned_palaces"]["C"] == "center_not_covered"
                if mode == "replacement":
                    assert counts["source_matches"] == 0
                    assert all(
                        a["literal_clause_comparison"]["matched"] is None
                        for a in item["axes"].values()
                    )


def test_opposite_host_direction_reverses_operations_for_all_star_pairs():
    opposite = {
        "生入": "生出",
        "生出": "生入",
        "克入": "克出",
        "克出": "克入",
        "比和": "比和",
    }
    for host in range(1, 10):
        for guest in range(1, 10):
            assert (
                host_guest.classify(guest, host)["label"]
                == opposite[host_guest.classify(host, guest)["label"]]
            )
    for other in (2, 5, 8):
        assert host_guest.classify(5, other)["label"] == "比和"


def test_axis_pair_and_period_pair_stay_visible_when_only_one_matches_a_clause():
    result = executed(inputs())
    a = analysis(result)["candidates"][0]["axes"]["facing"]
    assert [r["label"] for r in a["relations"]] == ["克出", "比和", "克入", "克出"]
    # 运盘 must mean this palace's 5, not the historical period 6.
    assert a["relations"][2]["host"] == {"role": "period", "number": 5, "element": "土"}
    assert a["relations"][-1]["host"] == {
        "role": "facing",
        "number": 4,
        "element": "木",
    }
    comparison = a["literal_clause_comparison"]
    assert comparison["literal_labels"] == ["克入"]
    assert comparison["matched"] is False
    assert comparison["basis_determined_from_clause_alone"] is False
    assert comparison["comparison_basis"] == "axis_pair_as_defined_p453_p910"
    check = verify_fengshui_reading(result, trusted_payload=deepcopy(result))
    assert check["status"] == "verified_served_fixed_reading"
    assert check["host_guest_coverage_verified"] is True
    assert check["host_guest_relation_count"] == 8
    assert check["host_guest_literal_source_differences"] == 1
    assert "保留差异" in result["snapshot_text"]
    assert "不是评价时令" in result["snapshot_text"]
    assert (
        len(
            [
                s
                for s in result["calculation_reading"]["statements"]
                if s["kind"] == "host_guest_source_comparison"
            ]
        )
        == 2
    )


@pytest.mark.parametrize("period,facing,page", [(7, "乙", 381), (3, "戌", 399)])
def test_repeated_shan_in_original_text_is_not_silently_changed_to_xiang(
    period, facing, page
):
    index = next(i for i, m in enumerate(_bundle()["mountains"]) if m["name"] == facing)
    chart = _chart(period, (index, "lower", "Literal repeated source noun"))
    natal = {"candidates": [chart]}
    value = host_guest.analyze(natal)
    counts = host_guest.validate({"host_guest_analysis": value}, natal)
    assert counts["source_ambiguous"] == 2
    axes = value["candidates"][0]["axes"]
    assert axes["sitting"]["literal_clause_comparison"]["literal_labels"] == [
        "克出",
        "生入",
    ]
    assert axes["facing"]["literal_clause_comparison"]["literal_labels"] == []
    assert all(
        a["literal_clause_comparison"]["pdf_page"] == page for a in axes.values()
    )


def test_default_profile_and_wang_timeliness_are_orthogonal_to_host_guest():
    value = inputs()
    default = deepcopy(value)
    default["interpretation"] = {}
    out = service.calculate_xuankong_natal(**default)
    assert (
        "host_guest_analysis" not in out["layers"]["xuankong_natal"]["interpretation"]
    )
    assert "natal_host_guest" not in out["coverage"]
    unknown = service.calculate_xuankong_natal(**value)
    value["interpretation"].update(
        timeliness_ruleset_id="wang_zhongzhou_timeliness_v1",
        current_period_number=7,
        period_evidence="Synthetic current period",
    )
    explicit = service.calculate_xuankong_natal(**value)
    assert analysis(unknown) == analysis(explicit)
    assert analysis(explicit)["evaluation_timeliness_applied"] is False
    assert analysis(explicit)["overall_auspiciousness"] == "not_produced"


def test_no_chart_and_multiple_candidates_preserve_their_actual_scope():
    value = host_guest.analyze({})
    assert host_guest.validate({"host_guest_analysis": value}, {})["relations"] == 0
    assert value["status"] == "no_computed_chart"
    charts = [_chart(6, (i, "lower", "Multiple candidate unit case")) for i in (9, 10)]
    value = host_guest.analyze({"candidates": charts})
    assert all(c["candidate_only"] is True for c in value["candidates"])
    assert (
        host_guest.validate({"host_guest_analysis": value}, {"candidates": charts})[
            "relations"
        ]
        == 16
    )


def test_rehashed_source_reading_cannot_replace_the_before_implementation_oracle(
    tmp_path,
):
    folder = tmp_path / "source"
    shutil.copytree(SOURCE, folder)
    value = json.loads((folder / "reference.json").read_text())
    value["full_lower_clauses"][0]["labels"]["山"] = ["比和"]
    (folder / "reference.json").write_text(json.dumps(value))
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest["reference.json"] = hashlib.sha256(
        (folder / "reference.json").read_bytes()
    ).hexdigest()
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_host_guest_reference(folder)


def corrupt(value, fault):
    first = value["candidates"][0]
    a = first["axes"]["facing"]
    record = a["relations"][-1]
    if fault == "swap_roles":
        record["host"], record["guest"] = record["guest"], record["host"]
        record.update(
            host_guest.classify(record["host"]["number"], record["guest"]["number"])
        )
    elif fault == "same_element_wrong_number":
        a["relations"][0]["guest"]["number"] = 2  # 5 and 2 are both earth.
    elif fault == "historical_period_as_palace_star":
        a["relations"][2]["host"].update(number=6, element="金")
        a["relations"][2].update(host_guest.classify(6, 4))
    elif fault == "direction":
        a["direction"] = "NW"
    elif fault == "other_palace":
        first["unassigned_palaces"].pop("C")
    elif fault == "switch_comparison_basis":
        a["literal_clause_comparison"].update(
            comparison_basis="period_facing", matched=True, status="matches"
        )
    elif fault == "boolean":
        first["natal_period_number"] = True
    elif fault == "site_permission":
        value["site_eligibility_established"] = True
    else:
        raise AssertionError(fault)
    return value


@pytest.mark.parametrize(
    "fault",
    [
        "swap_roles",
        "same_element_wrong_number",
        "historical_period_as_palace_star",
        "direction",
        "other_palace",
        "switch_comparison_basis",
        "boolean",
        "site_permission",
    ],
)
def test_independent_validator_rejects_semantic_errors_even_with_self_consistent_labels(
    fault,
):
    chart = _chart(6, (9, "lower", "Synthetic integrity test"))
    natal = {"candidates": [chart]}
    value = corrupt(host_guest.analyze(natal), fault)
    with pytest.raises(FengshuiCalculationError) as caught:
        host_guest.validate({"host_guest_analysis": value}, natal)
    assert caught.value.reason == "natal_host_guest_inconsistent"


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
@pytest.mark.parametrize(
    "fault",
    [
        "swap_roles",
        "same_element_wrong_number",
        "historical_period_as_palace_star",
        "direction",
        "other_palace",
        "switch_comparison_basis",
    ],
)
def test_wrong_relations_are_rejected_on_all_protocols_with_reading_disabled_and_projection(
    monkeypatch, tmp_path, capsys, tool, fault
):
    original = natal_interpretation.analyze_host_guest
    monkeypatch.setattr(
        natal_interpretation,
        "analyze_host_guest",
        lambda *a, **k: corrupt(original(*a, **k), fault),
    )
    value = inputs()
    value["interpretation"]["include_calculation_reading"] = False
    if tool == "assess":
        value = {"methods": ["xuankong_natal"], "xuankong": value}
    http = rest_client(monkeypatch).post(
        "/api/fengshui/" + tool,
        json=value,
        params={"fields": "status", "strict_fields": "true"},
    )
    mcp = asyncio.run(
        mcp_call(tool, {**value, "fields": ["status"], "strict_fields": True})
    )
    path = tmp_path / "input.json"
    path.write_text(json.dumps(value))
    code = run(
        [
            "fengshui_" + tool,
            "--request-file",
            str(path),
            "--fields",
            "status",
            "--strict-fields",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 503 and mcp.is_error and code == 1
    for result in (http.json(), mcp.structured_content, cli):
        assert result["error_code"] == "fengshui_calculation_inconsistent"
        assert result["retryable"] is False
        assert result["issues"][0]["path"] == "runtime.fengshui.interpretation"
        assert "calculation_reading" not in result


def test_service_seal_also_rejects_mutation_after_the_domain_guard(monkeypatch):
    original = service.analyze_natal_interpretation

    def wrong(*args, **kwargs):
        value = original(*args, **kwargs)
        corrupt(value["host_guest_analysis"], "swap_roles")
        return value

    monkeypatch.setattr(service, "analyze_natal_interpretation", wrong)
    assert executed(inputs())["error_code"] == "fengshui_calculation_inconsistent"


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
def test_valid_source_difference_is_delivered_successfully_and_equally_on_all_protocols(
    monkeypatch, tmp_path, capsys, tool
):
    value = inputs()
    if tool == "assess":
        value = {"methods": ["xuankong_natal"], "xuankong": value}
    http = rest_client(monkeypatch).post("/api/fengshui/" + tool, json=value)
    mcp = asyncio.run(mcp_call(tool, value))
    path = tmp_path / "input.json"
    path.write_text(json.dumps(value))
    code = run(["fengshui_" + tool, "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not mcp.is_error and code == 0
    assert (
        without_transport(http.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    assert (
        analysis(cli)["candidates"][0]["axes"]["facing"]["literal_clause_comparison"][
            "status"
        ]
        == "differs"
    )


def test_offline_guard_rejects_an_actual_fault_run_with_its_genuine_served_receipt(
    monkeypatch,
):
    original = natal_interpretation.analyze_host_guest
    with monkeypatch.context() as disabled:
        disabled.setattr(
            natal_interpretation,
            "analyze_host_guest",
            lambda *a, **k: corrupt(original(*a, **k), "switch_comparison_basis"),
        )
        for module in (natal_interpretation, service, reading):
            disabled.setattr(module, "validate_host_guest", lambda *a, **k: {})
        result = executed(inputs())
        assert "run_metadata" in result
        receipt = deepcopy(result)
    checked = verify_fengshui_reading(result, trusted_payload=result)
    assert checked["status"] == "rejected"
    assert {e["code"] for e in checked["errors"]} >= {"host_guest_inconsistent"}
    assert checked["host_guest_coverage_verified"] is False


def test_new_profile_is_explicit_and_invalid_ids_fail_request_validation():
    value = inputs()
    value["interpretation"]["host_guest_ruleset_id"] = "invented_unified_authority"
    with pytest.raises(ValueError):
        XuankongRequest.model_validate(value)
