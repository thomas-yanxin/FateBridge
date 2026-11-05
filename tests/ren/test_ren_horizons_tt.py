"""Direct-TT source binding, exact numerical points and complete failure rows."""

import copy
import importlib.util
import json
import math
import shutil
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "independent_direct_tt_audit", ROOT / "scripts/ren/audit_ren_horizons_tt.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@lru_cache(maxsize=1)
def reference():
    return AUDIT.reference()


def profile():
    return next(
        p for p in reference()["specification"]["profiles"] if p["id"] == "de440"
    )


def synthetic_actual(case):
    # Grader probes only: these are deliberately manufactured reference echoes.
    # The actual production comparison is performed by the five CLI audits.
    day = AUDIT.tt_days(case["refined_root_tt"])
    base = math.floor(day)
    return {
        "selected_tt_parts": [float(base), float(day - base)],
        "provider": "jpl_de440",
        "model": "fatebridge_de440_solar_v1",
        "civil_datetime": case["published_moment"],
    }


def test_all_original_events_and_direct_tt_probes_reconstruct_from_raw():
    data = reference()
    assert len(data["reference"]["events"]) == 113
    assert data["reference"]["production_imported"] is False
    assert data["reference"]["production_calculations_performed"] is False
    assert data["protocol"]["params"]["TIME_TYPE"] == "'TT'"
    assert data["specification"]["criterion_seconds"] == 1
    assert data["specification"]["before_comparison_correction"][
        "original_protocol_preserved"
    ]
    assert (
        data["specification"]["profiles"][-1]["expected_model"]
        == "fatebridge_jpl_spk_solar_v1"
    )


@pytest.mark.parametrize("corpus", ["source", "comparison"])
@pytest.mark.parametrize("change", ["content", "rehash", "extra", "missing"])
def test_frozen_identity_inventory_and_content_cannot_be_rewritten(
    tmp_path, corpus, change
):
    source = AUDIT.CORPUS if corpus == "source" else AUDIT.COMPARISON
    target = tmp_path / "copy"
    shutil.copytree(source, target)
    path = target / ("reference.json" if corpus == "source" else "protocol.json")
    if change in {"content", "rehash"}:
        path.write_text(path.read_text() + " ")
        if change == "rehash":
            manifest = json.loads((target / "freeze.json").read_text())
            manifest["files"][path.name] = AUDIT.sha(path)
            (target / "freeze.json").write_text(json.dumps(manifest))
    elif change == "extra":
        (target / "unexpected.json").write_text("{}")
    else:
        path.unlink()
    with pytest.raises(ValueError, match="Frozen TT reference"):
        AUDIT.frozen(target, AUDIT.PIN if corpus == "source" else AUDIT.COMPARISON_PIN)


@pytest.mark.parametrize("change", ["scale", "label", "body", "frame", "nonfinite"])
def test_remote_parser_rejects_wrong_time_geometry_or_angles(tmp_path, change):
    from tests.support.ren_horizons_reference import parse

    path = AUDIT.CORPUS / "collection/refinement-get20/batch-00.response.json"
    query = json.loads(path.with_name("batch-00.query.json").read_text())
    labels = AUDIT.shlex.split(query["params"]["TLIST"])
    data = json.loads(path.read_text())
    if change == "scale":
        data["result"] = data["result"].replace("Date__(TT)", "Date__(UT)")
    elif change == "body":
        data["result"] = data["result"].replace("Sun (10)", "Moon (301)")
    elif change == "frame":
        data["result"] = data["result"].replace("RA_(ICRF-a-app)", "RA_(FK4-a-app)")
    elif change == "nonfinite":
        before, table = data["result"].split("$$SOE", 1)
        lines = table.splitlines()
        fields = lines[1].split(",")
        fields[-2] = "nan"
        lines[1] = ",".join(fields)
        data["result"] = before + "$$SOE" + "\n".join(lines)
    else:
        labels[0] = labels[1]
    target = tmp_path / "wrong.json"
    target.write_text(json.dumps(data))
    with pytest.raises((ValueError, StopIteration)):
        parse(target, labels)


def test_tt_label_is_not_an_utc_label_and_microseconds_are_retained():
    first = "2000-01-01 12:00:00.000000"
    second = "2000-01-01 12:00:00.000001"
    assert (AUDIT.tt_days(second) - AUDIT.tt_days(first)) * 86400000000 == 1
    with pytest.raises(ValueError, match="masquerade"):
        AUDIT.tt_days(first + "+00:00")


@pytest.mark.parametrize(
    "change", ["late", "wrong_model", "nonfinite", "missing", "naive"]
)
def test_failed_model_or_root_is_retained_in_the_complete_113_row_matrix(change):
    data = reference()
    first = data["reference"]["events"][0]

    def observe(case):
        actual = synthetic_actual(case)
        if case is not first:
            return actual
        if change == "late":
            actual["selected_tt_parts"][1] += 1.5 / 86400
        elif change == "wrong_model":
            actual["model"] = "other"
        elif change == "nonfinite":
            actual["selected_tt_parts"][1] = float("nan")
        elif change == "missing":
            raise RuntimeError("Unavailable source")
        else:
            actual["civil_datetime"] = "1900-01-05 18:04:00"
        return actual

    report = AUDIT.compare_cases(data, observe, profile())
    assert report["expected_count"] == report["compared_count"] == 113
    assert not report["all_declared_tt_comparisons_passed"]
    assert not report["original_minute_gate_reclassified"]
    assert not report["full_supported_calendar_domain_certified"]
    assert not report["goal_complete"]
    if change == "late":
        assert report["tt_failure_count"] == 1
    elif change == "wrong_model":
        assert report["source_identity_failures"] == 1
        assert report["tt_failure_count"] == 0
    else:
        assert report["unavailable_count"] == 1
        assert report["comparisons"][0]["within_original_tt_criterion"] is None


def test_complete_unavailable_source_retains_all_failed_event_identities():
    def unavailable(case):
        raise RuntimeError("No source")

    report = AUDIT.compare_cases(reference(), unavailable, profile())
    assert report["unavailable_count"] == len(report["comparisons"]) == 113
    assert report["maximum_tt_difference_seconds"] is None
    assert report["successful_calculations"] == 0
    assert not report["all_declared_tt_comparisons_passed"]


@pytest.mark.parametrize("change", ["missing", "duplicate"])
def test_narrowed_or_duplicated_cohort_cannot_be_a_complete_comparison(change):
    data = copy.deepcopy(reference())
    if change == "missing":
        data["reference"]["events"].pop()
    else:
        data["reference"]["events"][0] = data["reference"]["events"][1]
    with pytest.raises(ValueError, match="113-event"):
        AUDIT.compare_cases(data, synthetic_actual, profile())
