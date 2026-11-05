"""The new bounded cohort must retain missing strata and literal failures."""

import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_official import official_chart_checks

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
EVIDENCE = ROOT / "tests/data/human_design/profile_observations"
PLAN_PATH = ROOT / "tests/fixtures/human-design-profile-coverage-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
COHORT = json.loads((EVIDENCE / "cohort.json").read_text())


def builder_module():
    # The builder's dependencies parse source PDFs only; no engine import is
    # used to manufacture official expected activations or labels.
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(
            "profile_coverage_builder",
            SCRIPTS / "build_human_design_profile_coverage.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def test_all768_inputs_are_frozen_disjoint_and_not_official_expected_values():
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "ea4e0cd15bd228a3002bd055aaeaae28264b5edf0d51505af1828c29e78ce143"
    )
    assert PLAN["case_count"] == len(PLAN["cases"]) == 768
    assert PLAN["expected_new_official_values"] is None
    assert PLAN["old_input_overlap_count"] == 0
    expected_profiles = {
        "1/3",
        "1/4",
        "2/4",
        "2/5",
        "3/5",
        "3/6",
        "4/6",
        "4/1",
        "5/1",
        "5/2",
        "6/2",
        "6/3",
    }
    assert {
        (
            c["engine_diagnostic_not_official_expected_values"]["personality_sun_gate"],
            c["engine_diagnostic_not_official_expected_values"]["profile"],
        )
        for c in PLAN["cases"]
    } == {(g, p) for g in range(1, 65) for p in expected_profiles}
    assert len({c["engine_utc"] for c in PLAN["cases"]}) == 768
    old_inputs = set()
    for name, digest in PLAN["preserved_cohorts_sha256"].items():
        raw = (ROOT / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        if name.endswith(("official-charts.json", "official-cross-charts.json")):
            old_inputs.update(
                json.dumps(c["birth_input"], sort_keys=True)
                for c in json.loads(raw)["cases"]
            )
    assert not old_inputs.intersection(
        json.dumps(c["birth_input"], sort_keys=True) for c in PLAN["cases"]
    )


def test_rational_profile_intervals_cover_the_gate_without_gaps_or_overlap():
    end = Fraction(0)
    for i, row in enumerate(PLAN["profile_intervals_within_gate"]):
        start, stop, mid = (
            Fraction(row[k])
            for k in (
                "start_inclusive_degrees",
                "end_exclusive_degrees",
                "midpoint_degrees",
            )
        )
        assert start == end and start < mid < stop
        assert stop - start == (Fraction(13, 16) if i % 2 == 0 else Fraction(1, 8))
        p = int(mid // Fraction(15, 16)) + 1
        d = int(((mid - 88) % Fraction(45, 8)) // Fraction(15, 16)) + 1
        assert row["profile"] == f"{p}/{d}"
        end = stop
    assert end == Fraction(45, 8)


def test_source_only_builder_reproduces_all24_without_hiding744_missing_rows():
    assert (
        builder_module().build(EVIDENCE / "observations.jsonl", EVIDENCE / "pdfs")
        == COHORT
    )
    assert COHORT["collection_status"] == "incomplete"
    assert COHORT["planned_case_count"] == 768
    assert COHORT["observed_case_count"] == 24
    assert len(COHORT["missing_planned_ids"]) == 744
    assert COHORT["source"]["independent_pdf_properties_checked"] == 24
    assert COHORT["source"]["pdf_diagram_independently_transcribed"] is False


def test_complete_mode_rejects_the_passing_subset():
    with pytest.raises(ValueError, match="744 planned rows missing"):
        builder_module().build(
            EVIDENCE / "observations.jsonl", EVIDENCE / "pdfs", require_complete=True
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "unplanned",
        "identity",
        "before_plan",
        "column",
        "pdf_hash",
        "pdf_path",
        "source_label",
    ],
)
def test_builder_rejects_source_binding_corruption_without_replacing_cases(
    tmp_path, mutation
):
    rows = [json.loads((EVIDENCE / "observations.jsonl").read_text().splitlines()[0])]
    row = rows[0]
    if mutation == "duplicate":
        rows.append(deepcopy(row))
    elif mutation == "unplanned":
        row["id"] = "not-planned"
    elif mutation == "identity":
        row["facts"]["properties"]["Name"] = "a different case"
    elif mutation == "before_plan":
        row["collected_at_utc"] = "1980-01-01T00:00:00+00:00"
    elif mutation == "column":
        row["facts"]["columns"]["personality"].pop()
    elif mutation == "pdf_hash":
        row["source"]["pdf_sha256"] = "0" * 64
    elif mutation == "pdf_path":
        row["source"]["pdf_filename"] = "../elsewhere.pdf"
    elif mutation == "source_label":
        row["facts"]["properties"]["Incarnation Cross"] += " (silent alias)"
    observation = tmp_path / "mutated.jsonl"
    observation.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    with pytest.raises(ValueError):
        builder_module().build(observation, EVIDENCE / "pdfs")


def test_all624_gate_lines24_mechanics_and18_literal_failures_are_retained():
    check = official_chart_checks(COHORT)
    assert check["gate_lines_checked"] == check["gate_lines_matched"] == 624
    assert check["charts_with_all_mechanics_matched"] == 24
    assert check["charts_checked"] == 24
    assert check["charts_matched"] == check["cross_names_exactly_matched"] == 6
    assert check["status"] == "failed"
    assert sum(not c["structure_checks"]["cross_name"] for c in check["cases"]) == 18


def test_current_readings_verify_without_full_source_or_model_claim():
    from tests.support.human_design_current import complete_run

    for case in COHORT["cases"]:
        run = complete_run(**case["birth_input"])
        check = verify_human_design_reading(run)
        assert check["status"] == "verified_fixed_template_reading", case["id"]
        assert check["checked_fixing_reading_count"] == 26
        assert run["validation"]["all_three_axes_full_marks"] is False
        assert run["source_summary"]["full_source_acceptance_passed"] is False
