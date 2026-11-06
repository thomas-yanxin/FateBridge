"""Publisher facts are independent; coarse agreement is not clock acceptance."""

import ast
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.core.astro import native_execution, runtime
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_publisher import (
    publisher_natal_checks,
    summarize_runs,
)
from scripts.human_design.build_human_design_publisher_natal_reference import (
    extract_facts,
    facts_from_page,
)

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "tests/fixtures/human-design-cycle-publisher-plan.json"
REFERENCE_PATH = (
    ROOT / "src/fatebridge/data/human_design/publisher-natal-2005-reference.json"
)
PLAN = json.loads(PLAN_PATH.read_text())
REFERENCE = json.loads(REFERENCE_PATH.read_text())


# Minimal synthetic extraction probe, not the source's prose. The real PDF
# is independently hash-checked by the actual extractor acceptance command.
FACTS_ONLY = """Krishnamurti's Natal Chart
The Single Definition Manifestor Basic Thematic
[Birth Data for this lec-
ture: May 12, 1895, 12:25 PM, Madanapalle, India]
Copyright 2005 Jovian Archive Corporation
"""


@pytest.fixture(scope="module")
def current(tmp_path_factory):
    capture = tmp_path_factory.mktemp("publisher-current") / "current-runs.json.gz"
    report = publisher_natal_checks(ROOT, capture=capture)
    return json.loads(gzip.decompress(capture.read_bytes())), report


def forbidden(*args, **kwargs):
    raise AssertionError("Pure publisher check called a native producer")


def test_original_plan_facts_and_complete_sixteen_runs_are_immutable():
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "efb7ca4becc8751e2d8cdd0215bfd9cd8f2678efd97a97df69a1f1f6bc6dbc03"
    )
    assert (
        hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()
        == "d041734b1b08b6797587390ec176c66a08ee27dc34b984a540d6ec3bf5900154"
    )
    assert (
        PLAN["source"]["literal_clock"] == REFERENCE["example"]["clock"] == "12:25 PM"
    )
    assert (
        PLAN["source"]["timezone_supplied"]
        is REFERENCE["example"]["timezone_printed_in_birth_note"]
        is False
    )
    assert (
        sum(
            len(PLAN[group])
            for group in ("literal_hypotheses", "diagnostic_only_hypotheses")
        )
        == 4
    )
    assert PLAN["unchanged_thresholds"] == {
        "astronomy_arcsec": 2.0,
        "physical_design_root_seconds": 5.0,
        "clock_seconds": 0.0002,
    }


def test_extractor_has_no_engine_imports_and_does_not_correct_source_clock():
    script = (
        ROOT / "scripts/human_design/build_human_design_publisher_natal_reference.py"
    )
    tree = ast.parse(script.read_text())
    assert not any(
        isinstance(n, ast.ImportFrom) and (n.module or "").startswith("fatebridge")
        for n in ast.walk(tree)
    )
    assert facts_from_page(FACTS_ONLY) == REFERENCE


@pytest.mark.parametrize(
    "old,new",
    [
        ("PM", "AM"),
        ("12:25", "12:30"),
        ("1895", "1896"),
        ("Single Definition", "Split Definition"),
        ("Manifestor", "Generator"),
        ("Krishnamurti", "Another person"),
        ("Madanapalle", "Another city"),
        ("Copyright 2005", "Copyright 2006"),
    ],
)
def test_source_fact_contradictions_do_not_extract_a_repaired_success(old, new):
    with pytest.raises(ValueError):
        facts_from_page(FACTS_ONLY.replace(old, new))


def test_changed_pdf_is_rejected_before_text_extraction(tmp_path):
    path = tmp_path / "changed.pdf"
    path.write_bytes(b"changed source bytes")
    with (
        patch(
            "scripts.human_design.build_human_design_publisher_natal_reference.subprocess.run",
            forbidden,
        ),
        pytest.raises(ValueError, match="pinned bytes"),
    ):
        extract_facts(path)


@pytest.mark.parametrize("index", range(16))
def test_every_original_complete_run_remains_purely_verifiable(index, current):
    RUNS, _ = current
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert (
            verify_human_design_reading(RUNS[index]["run"])["status"]
            == "verified_fixed_template_reading"
        )


def test_one_source_example_two_facts_are_not_counted_as_sixteen_examples(current):
    RUNS, _ = current
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        report = summarize_runs(PLAN, REFERENCE, RUNS)
    assert report["independent_example_count"] == 1
    assert report["independent_structural_fact_count"] == 2
    assert (
        report["literal_hypothesis_computation_count"]
        == report["literal_structure_matches"]
        == 8
    )
    assert report["diagnostic_computation_count"] == 8
    assert report["diagnostic_matches_counted_as_acceptance"] == 0
    assert (
        report["publisher_time_zone_resolved"]
        is report["exact_birth_epoch_accepted"]
        is report["complete_activation_glyphs_accepted"]
        is report["full_source_accepted"]
        is False
    )
    assert report["prediction_sample_size"] == 0
    for contrast in report["literal_zone_contrasts"]:
        assert contrast["birth_tt_difference_seconds"] == pytest.approx(
            -530, abs=0.0002
        )
        assert (
            contrast["same_type_and_definition"]
            and contrast["same_profile"]
            and contrast["same_incarnation_cross"]
        )
        assert len(contrast["subdivision_changes"]) == 12
        assert [r["body"] for r in contrast["line_fixing_record_changes"]] == ["Moon"]
        assert contrast["exact_epoch_or_activation_acceptance_inferred"] is False


@pytest.mark.parametrize(
    "kind",
    [
        "drop",
        "duplicate",
        "promote_AM",
        "clock",
        "backend",
        "mode",
        "fake_graph",
        "fake_reading",
    ],
)
def test_incomplete_or_rehashed_repaired_cases_never_gain_source_acceptance(
    kind, current
):
    RUNS, _ = current
    rows = deepcopy(RUNS)
    if kind == "drop":
        rows.pop()
    elif kind == "duplicate":
        rows[1] = deepcopy(rows[0])
    elif kind == "promote_AM":
        rows[4]["category"] = "literal_hypotheses"
    elif kind == "clock":
        rows[0]["input"]["birth_hour"] = 0
    elif kind == "backend":
        rows[0]["backend"] = "moshier"
    elif kind == "mode":
        rows[0]["run"]["calculation_policy"]["node_mode"] = "mean"
    elif kind == "fake_graph":
        rows[0]["run"]["bodygraph"]["type"] = "generator"
    else:
        rows[0]["run"]["interpretation"][
            "design_time_precision_meaning"
        ] = "All source facts accepted"
    for row in rows:
        run = row["run"]
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
        pytest.raises(ValueError),
    ):
        summarize_runs(PLAN, REFERENCE, rows)


def test_new_source_contradiction_is_reported_instead_of_changing_inputs(current):
    RUNS, _ = current
    reference = deepcopy(REFERENCE)
    reference["example"]["expected_structural_fields"][
        "bodygraph.definition.kind"
    ] = "split"
    report = summarize_runs(PLAN, reference, RUNS)
    assert report["literal_structure_status"] == "failed"
    assert report["literal_structure_matches"] == 0
    assert report["literal_hypothesis_computation_count"] == 8
    assert report["diagnostic_matches_counted_as_acceptance"] == 0


def test_current_native_audit_retains_all_fixed_hypotheses_and_both_backends(current):
    _, report = current
    assert len(report["all_cases"]) == 16
    assert report["literal_structure_matches"] == 8
    assert {(r["backend"], r["node_mode"]) for r in report["all_cases"]} == {
        ("swieph", "true"),
        ("swieph", "mean"),
        ("moshier", "true"),
        ("moshier", "mean"),
    }
    assert report["exact_birth_epoch_accepted"] is False
