"""Exposed-source retrieval must retain every discrepancy and never grade by lookup."""

import ast
import gzip
import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge
from fatebridge.core.output_source_annotations import SourceCurrentCalculation
from fatebridge.core.requests.bazi import BaziSourceCompareRequest
from fatebridge.core.source_annotations import (
    compare_records,
    compare_registered_annotations,
)
from fatebridge.services.source_comparison import calculate_bazi_source_compare

ROOT = Path(__file__).resolve().parents[1]
ORDER = ("year", "month", "day", "hour")
PRESERVED_V7 = (
    ROOT
    / "docs/validation/bazi-source-contrast-dependencies-v1/before/src/fatebridge/core/strength.py"
)


def test_predeclared_numerical_dependencies_and_versioned_structural_rule():
    protocol = json.loads(
        (ROOT / "tests/fixtures/bazi_source_comparison_v1/protocol.json").read_text()
    )
    adoption = ROOT / "tests/fixtures/bazi_complete_bureau_adoption_v1"
    binding = json.loads((adoption / "formatted-source-binding.json").read_text())
    package = Path(fatebridge.__file__).resolve().parent
    for relative, expected in protocol["arithmetic_dependencies"].items():
        path = package / relative.removeprefix("src/fatebridge/")
        if relative == "src/fatebridge/core/strength.py":
            before = adoption / "strength-v6-before.py.txt"
            assert hashlib.sha256(before.read_bytes()).hexdigest() == expected
            assert (
                hashlib.sha256(PRESERVED_V7.read_bytes()).hexdigest()
                == binding["adopted_strength_sha256"]
            )

            def assignments(source):
                tree = ast.parse(source)
                return {
                    n.targets[0].id: ast.dump(n.value, include_attributes=False)
                    for n in tree.body
                    if isinstance(n, ast.Assign)
                    and isinstance(n.targets[0], ast.Name)
                    and n.targets[0].id
                    in {"SHARES", "PHASE_FACTORS", "DEFAULT_POLICY", "STEM_PAIRS"}
                }

            assert assignments(before.read_text()) == assignments(path.read_text())
        else:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def load_preserved_strength(version):
    path = (
        ROOT
        / "tests/fixtures/bazi_complete_bureau_adoption_v1/strength-v6-before.py.txt"
        if version == 6
        else PRESERVED_V7
    )
    name = f"fatebridge.core._source_comparison_preserved_v{version}"
    import types

    module = types.ModuleType(name)
    module.__package__ = "fatebridge.core"
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def numeric_assessment(value):
    """Remove only declared structural grade and source metadata, retaining all numbers."""
    value = deepcopy(value)
    for key in ("method_id", "sources", "strength_level"):
        value.pop(key)
    value["stem_energy_accounting"].pop("source_order_review", None)
    for key in ("rule", "source_id"):
        value["structural_decision"].pop(key)
    value["sensitivity"].pop("candidate_strengths")
    for variant in value["sensitivity"]["variants"]:
        variant.pop("strength")
    return value


def test_all_existing_birth_request_contracts_and_catalog_order_are_preserved():
    from fatebridge.core.requests import bazi
    from fatebridge.core.requests.birth import BaziClockRequest
    from fatebridge.services.catalog.bazi import SPECS

    fixture = ROOT / "tests/fixtures/bazi_source_comparison_v1"
    protocol = json.loads((fixture / "protocol.json").read_text())

    def load_before(relative, name):
        path = fixture / "before" / relative
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == protocol["before_shared_files"][relative]
        )
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    before = load_before(
        "src/fatebridge/core/requests/bazi.py",
        "_bazi_source_requests_before",
    )
    models = {
        name: model
        for name, model in vars(before).items()
        if isinstance(model, type)
        and issubclass(model, BaziClockRequest)
        and model.__module__ == before.__name__
    }
    assert len(models) >= 11
    for name, model in models.items():
        assert model.model_json_schema() == getattr(bazi, name).model_json_schema()
    catalog = load_before(
        "src/fatebridge/services/catalog/bazi.py",
        "_bazi_source_catalog_before",
    )
    assert [s.key for s in SPECS] == [s.key for s in catalog.SPECS] + [
        "bazi_source_compare"
    ]
    for old, current in zip(catalog.SPECS, SPECS):
        for attr in (
            "family",
            "rest_path",
            "mcp_name",
            "cpu_bound",
            "include_snapshot_text",
            "summary",
            "operation_label_zh",
        ):
            assert getattr(old, attr) == getattr(current, attr)


def test_all_source_records_survive_citation_repairs_and_unproved_identities_stay_unknown():
    package = Path(fatebridge.__file__).resolve().parent
    versions = [
        json.loads(
            (package / f"data/reference/bazi-source-annotations-v{n}.json").read_text()
        )
        for n in (1, 2, 3)
    ]
    original = versions[0]["records"]
    for data in versions[1:]:
        assert [
            {k: v for k, v in r.items() if k != "source_reference"}
            for r in data["records"]
        ] == [{k: v for k, v in r.items() if k != "source_reference"} for r in original]
    records = versions[-1]["records"]
    assert len(records) == 349
    unknown = [r for r in records if r["source_reference"]["url"] is None]
    assert len(unknown) == 6 and {r["group"] for r in unknown} == {
        "prior_stem_transformation"
    }
    assert all(r["source_reference"]["title"] is None for r in unknown)
    case = next(
        r for r in records if r["reference_id"] == "legacy:ditian_zhonghe_wang_example"
    )
    assert "中和" in case["source_reference"]["title"]
    assert "衰旺" not in case["source_reference"]["title"]
    assert case["source_reference"]["url"].endswith("/16288")
    for record in records:
        reference = record["source_reference"]
        if reference.get("identity_evidence"):
            relative, pointer = reference["identity_evidence"].split("#", 1)
            path = ROOT / relative
            assert (
                hashlib.sha256(path.read_bytes()).hexdigest()
                == reference["identity_evidence_sha256"]
            )
            value = json.loads(path.read_text())
            for key in pointer.strip("/").split("/"):
                value = value[key]
            assert value == reference["whole_pdf_sha256"]


def test_all349_v6_v7_receipts_replay_and_current_matches_before_refactor():
    p = ROOT / "docs/validation/bazi-fixed-second-offset-source-corpus-v1.json.gz"
    assert (
        hashlib.sha256(p.read_bytes()).hexdigest()
        == Path(str(p) + ".sha256").read_text().strip()
    )
    before = json.loads(gzip.decompress(p.read_bytes()))
    baseline, historical = load_preserved_strength(6), load_preserved_strength(7)
    accepted_path = (
        ROOT / "tests/fixtures/architecture_refactor_v1/bazi349-before.json.gz"
    )
    assert hashlib.sha256(accepted_path.read_bytes()).hexdigest() == (
        "fc1bcca2cf7a9cc028830f9fcd21670fd3bdfa5d36b67a1f0e5893ee8987f408"
    )
    accepted_rows = json.loads(gzip.decompress(accepted_path.read_bytes()))
    assert len(accepted_rows) == 349
    accepted = {
        (row["group"], row["id"]): row["current_calculation"] for row in accepted_rows
    }
    # Historical receipts keep their original literal input/lookup. The current
    # index separately exposes reviewed readings; never alias old wrong pillars.
    historical_index = json.loads(
        (
            ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v5.json"
        ).read_text()
    )
    revised_ids = {
        r["input_reading_revision"]["original_index_record"]["reference_id"]
        for r in json.loads(
            (
                ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v6.json"
            ).read_text()
        )["records"]
        if "input_reading_revision" in r
    }
    from fatebridge.core.elements import ElementAnalysis
    from fatebridge.core.strength import assess_strength

    records = original_mismatches = unknown = improved = regressed = changed_unknown = 0
    distinct_mismatches = set()
    for group in before["groups"].values():
        for row in group["rows"]:
            pillars = dict(zip(ORDER, map(tuple, row["pillars"])))
            phases = ElementAnalysis.seasonal_phases(pillars["month"][1])
            old = baseline.assess_strength(pillars, phases)
            review = old["stem_energy_accounting"].pop("source_order_review")
            assert review["candidate_numeric_policy_adopted"] is False
            assert review["calculation_effect"] == "none"
            assert old == row["assessment"]
            original_mismatches += row["matches"] is False
            result = calculate_bazi_source_compare(*row["pillars"])
            assert "error" not in result, result
            current = result["current_calculation"]
            assessment = current["assessment"]
            assert current["method_id"] == "season_root_revelation_relations_v10"
            # The source lookup never selects or replaces the computed grade.
            assert assessment == assess_strength(pillars, phases)
            assert current == accepted[row["group"], row["id"]]
            SourceCurrentCalculation.model_validate(current)
            previous = historical.assess_strength(pillars, phases)
            assert previous["method_id"] == "season_root_revelation_relations_v7"
            assert numeric_assessment(previous) == numeric_assessment(old)
            assert current["calculation_overridden"] is False
            comparison = compare_records(
                [
                    r
                    for r in historical_index["records"]
                    if r["pillars"] == row["pillars"]
                ],
                previous["strength_level"],
            )
            matched = next(
                r
                for r in comparison["records"]
                if r["group"] == row["group"] and r["case_id"] == row["id"]
            )
            assert matched["retained_strength_annotation"] == row["expected_strength"]
            current_records = result["source_comparison"]["records"]
            if matched["reference_id"] in revised_ids:
                assert all(
                    r["reference_id"] != matched["reference_id"]
                    for r in current_records
                )
            else:
                assert any(
                    r["reference_id"] == matched["reference_id"]
                    for r in current_records
                )
            actual = previous["strength_level"]
            if row["expected_strength"] is None:
                assert matched["comparison"] == "unadjudicated"
                unknown += 1
                changed_unknown += actual != row["actual_strength"]
            else:
                agrees = actual == row["expected_strength"]
                assert matched["comparison"] == ("agrees" if agrees else "differs")
                improved += not row["matches"] and agrees
                regressed += row["matches"] and not agrees
            if comparison["status"] == "known_annotation_mismatch":
                distinct_mismatches.add(tuple(row["pillars"]))
            assert comparison["full_original_text_conformance_certified"] is False
            assert comparison["new_independent_validation_credit"] == 0
            records += 1
    assert records == 349 and original_mismatches > 0
    assert len(distinct_mismatches) == 23
    assert (improved, regressed, unknown, changed_unknown) == (3, 0, 234, 2)


def test_literal_position_order_and_returned_records_cannot_poison_index():
    pillars = dict(zip(ORDER, [tuple(s) for s in ["庚午", "乙酉", "庚午", "壬午"]]))
    first = compare_registered_annotations(pillars, "强")
    assert first["status"] == "known_annotation_mismatch"
    assert first["computed_strength"] == "强"
    assert first["retained_expected_strengths"] == ["弱"]
    original = deepcopy(first)
    first["records"][0]["retained_strength_annotation"] = "强"
    first["reference_index"]["total_registered_records"] = 0
    assert (
        compare_registered_annotations(dict(reversed(list(pillars.items()))), "强")
        == original
    )


def test_unknown_absent_conflicting_and_missing_computation_never_certify():
    base = {"retained_strength_annotation": None}
    assert compare_records([base], "强")["status"] == "unadjudicated_records_only"
    assert compare_records([], "强")["status"] == "no_registered_literal_case"
    rows = [
        {"retained_strength_annotation": "强"},
        {"retained_strength_annotation": "弱"},
        base,
    ]
    result = compare_records(rows, "强")
    assert result["status"] == "conflicting_registered_annotations"
    assert result["literal_match_count"] == 3
    assert (
        result["agreeing_known_count"]
        == result["differing_known_count"]
        == result["unknown_or_unannotated_count"]
        == 1
    )
    assert result["calculation_overridden"] is False
    assert compare_records([rows[0]], None)["status"] == "current_grade_missing"
    assert result["full_original_text_conformance_certified"] is False


def test_only_supplied_literal_pillars_are_used_and_calendar_conflicts_are_retained():
    req = BaziSourceCompareRequest(
        year_pillar="丁卯", month_pillar="丙寅", day_pillar="辛亥", hour_pillar="庚寅"
    )
    result = calculate_bazi_source_compare(**req.model_dump())
    assert result["input_context"]["month_stem_matches_recorded_year"] is False
    assert result["input_context"]["birth_datetime_reconstructed"] is False
    assert result["input_context"]["historical_birth_datetime_verified"] is False
    assert result["input_context"]["literal_source_changed"] is False
    with pytest.raises(ValidationError):
        BaziSourceCompareRequest(
            year_pillar="甲子", month_pillar="丙寅", day_pillar="甲子"
        )
    with pytest.raises(ValidationError):
        BaziSourceCompareRequest(
            year_pillar="甲子",
            month_pillar="丙寅",
            day_pillar="甲子",
            hour_pillar="甲子",
            birth_year=1990,
        )


@pytest.mark.parametrize("bad", ["甲", "甲子\n", "甲子甲", "甲A", "A子", "甲子 丙寅"])
def test_malformed_literal_input_is_rejected_without_slicing_or_repair(bad):
    with pytest.raises(ValidationError):
        BaziSourceCompareRequest(
            year_pillar=bad, month_pillar="丙寅", day_pillar="甲子", hour_pillar="甲子"
        )
    assert "error" in calculate_bazi_source_compare(bad, "丙寅", "甲子", "甲子")
