"""Frozen actual-pipeline evidence and failure-preservation regressions."""

import json
from pathlib import Path

import pytest

from scripts.astrodice_lunar_pipeline import plan, write_new
from scripts.audit_astrodice_lunar_pipeline import audit
from scripts.audit_astrodice_lunar_pipeline_receipts import audit as receipts
from scripts.audit_astrodice_lunar_pipeline_receipts import (
    interiors,
    native_receipt,
    require_unpromoted,
)
from scripts.verify_astrodice_lunar_pipeline import verify

ROOT = Path(__file__).parents[1]
RUN = ROOT / "docs/validation/astrodice-lunar-pipeline-run-2026-10-28"


@pytest.mark.parametrize("split", ["development", "heldout"])
def test_independent_reference_and_frozen_first_grades_replay(split):
    reference = RUN / f"{split}-reference-first.json"
    proof = RUN / f"{split}-independent-first.json"
    assert verify(RUN, reference) == json.loads(proof.read_text())
    assert audit(
        RUN, split, RUN / f"native-{split}-first", reference, proof
    ) == json.loads((RUN / f"{split}-audit-first.json").read_text())


def test_known_failure_remains_even_though_all_fresh_rows_pass():
    development = json.loads((RUN / "development-audit-first.json").read_text())
    heldout = json.loads((RUN / "heldout-audit-first.json").read_text())
    failed = [r for r in development["rows"] if not r["qualified"]]
    assert len(failed) == 1 and failed[0]["backend"] == "swieph"
    assert failed[0]["label"] == "3000-12-07T04:07:32"
    assert (
        failed[0]["signed_fixed_longitude_rate_error_arcsec_per_source_day"]["lower"]
        > 0.002
    )
    assert all(r["qualified"] for r in heldout["rows"])
    assert (
        development["original_production_gate"]
        == heldout["original_production_gate"]
        == 2
    )
    assert development["original_overall_gate"] == heldout["original_overall_gate"] == 1
    assert (
        development["rate_line_arcsec_per_source_day"]
        == heldout["rate_line_arcsec_per_source_day"]
        == "0.002"
    )


@pytest.mark.parametrize("split", ["development", "heldout"])
@pytest.mark.parametrize("kind", ["row", "clock", "direction"])
def test_independent_reference_rejects_rebound_or_incomplete_samples(
    split, kind, tmp_path
):
    data = json.loads((RUN / f"{split}-reference-first.json").read_text())
    if kind == "row":
        data["rows"].pop()
    elif kind == "clock":
        data["rows"][0]["exact_binary64_numeric_jd"] = "2451545"
    else:
        data["rows"][0]["model"]["direction"][0] = ["0", "0"]
    path = tmp_path / "mutant.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(RUN, path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("physical_TT_equivalence_certified", True),
        ("original_failure_records_regraded", True),
        ("complete_moving_frame_derivative_certified", True),
        ("original_overall_gate", 0),
        ("original_production_gate", 0),
    ],
)
def test_postopening_guard_rejects_promoted_claims_without_regrading(field, value):
    data = json.loads((RUN / "heldout-audit-first.json").read_text())
    data[field] = value
    with pytest.raises(ValueError):
        require_unpromoted(data)


@pytest.mark.parametrize("kind", ["binary", "backend", "file", "derivative", "restore"])
def test_actual_receipt_rejects_detached_native_evidence(kind):
    native = json.loads(
        (RUN / "native-heldout-first/jpl_record_window-0.json").read_text()
    )
    if kind == "binary":
        native["native_library_sha256"] = "0" * 64
    elif kind == "backend":
        native["native_calls"][0]["returned_flags"] = 258
    elif kind == "file":
        native["trace"]["files"][0]["sha256"] = "0" * 64
    elif kind == "derivative":
        native["direction_derivative_per_native_argument_day_j2000"][0] += 1e-6
    else:
        native["metadata"]["lunar_light_time"]["fixed_frame_source_derivative"][
            "center_native_states_reproduced_exactly"
        ] = False
    manifest = json.loads((RUN / "inputs-before-evaluation.json").read_text())
    source = Path(plan(RUN)["reference_source"])
    errors = {
        "binary": "Native binary detached",
        "backend": "physical backend changed",
        "file": "source identity detached",
        "derivative": "Derived evidence detached",
        "restore": "Source restoration",
    }
    with pytest.raises(ValueError, match=errors[kind]):
        native_receipt(native, manifest, source)


def test_missing_native_row_is_refused(tmp_path):
    for path in sorted((RUN / "native-heldout-first").glob("*.json"))[1:]:
        (tmp_path / path.name).write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="population"):
        audit(
            RUN,
            "heldout",
            tmp_path,
            RUN / "heldout-reference-first.json",
            RUN / "heldout-independent-first.json",
        )


def test_unavailable_native_result_is_retained_as_failed(tmp_path):
    directory = RUN / "native-heldout-first"
    for path in directory.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    path = tmp_path / "jpl_record_window-0.json"
    native = json.loads(path.read_text())
    native.update(
        status="error",
        error="synthetic unavailable-source fault",
        error_type="EphemerisSourceError",
    )
    path.write_text(json.dumps(native))
    grade = audit(
        RUN,
        "heldout",
        tmp_path,
        RUN / "heldout-reference-first.json",
        RUN / "heldout-independent-first.json",
    )
    assert len(grade["rows"]) == 6
    failed = [r for r in grade["rows"] if not r["qualified"]]
    assert len(failed) == 1 and failed[0]["status"] == "error"
    assert failed[0]["error_type"] == "EphemerisSourceError"


def test_no_old_or_first_output_can_be_overwritten(tmp_path):
    path = tmp_path / "first.json"
    write_new(path, {"failure": True})
    with pytest.raises(FileExistsError):
        write_new(path, {"failure": False})
    assert json.loads(path.read_text()) == {"failure": True}


def test_all_actual_receipts_and_unique_source_derivatives_are_checked():
    result = receipts(RUN)
    assert len(result["rows"]) == 12
    assert all(row["status"] == "verified" for row in result["rows"])
    assert len(result["source_interiors"]) == 12
    assert sum(len(x["interiors"]) for x in result["source_interiors"]) == 24
    assert result["new_numerical_rows_or_grades"] == 0


def test_source_boundary_cannot_bless_unique_centre_derivative():
    protocol = plan(RUN)
    source = Path(protocol["reference_source"])
    raw = (source / "record-responses/case-00.bin").read_bytes()
    import struct
    from fractions import Fraction

    boundary = str(Fraction(struct.unpack_from("<d", raw)[0]))
    with pytest.raises(ValueError, match="boundary"):
        interiors(source, 0, [boundary, boundary])
