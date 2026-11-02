"""Current source truth must not overwrite history or reward wrong operators."""

import gzip
import hashlib
import importlib.util
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit_bazi_current_collation.py"
FIRST = ROOT / "docs/validation/bazi-current-collation-first-v1.json.gz"


def runner():
    spec = importlib.util.spec_from_file_location("_current_collation_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def first():
    assert (
        hashlib.sha256(FIRST.read_bytes()).hexdigest()
        == FIRST.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(gzip.decompress(FIRST.read_bytes()))


def test_full_historical_replay_and_all_unknowns_are_preserved():
    report = first()
    historical = json.loads(
        (ROOT / "docs/validation/bazi-stem-effects-first-v2.json").read_text()
    )
    assert report["historical_groups"] == historical["groups"]
    assert report["historical_adoption_gates"] == historical["adoption_gates"]
    assert report["historical_summary"]["records"] == 146
    assert report["current_summary"]["distinct_literal_charts"] == 117
    assert report["current_summary"]["strength_known_records"] == 57
    assert report["current_summary"]["strength_unknown_records"] == 89
    # Only four named checks change; every prediction, force receipt, strength,
    # known/unknown status and other source judgment stays exactly equal.
    deltas = {(d["group"], d["id"]): d for d in report["label_and_anchor_deltas"]}
    assert len(deltas) == 4
    for group, rows in report["current_groups"].items():
        for old, current in zip(report["historical_groups"][group], rows):
            if (group, current["id"]) in deltas:
                restored = deepcopy(current)
                restored["source_checks"] = old["source_checks"]
                assert restored == old
            else:
                assert current == old


def test_corrected_pair_fails_candidate_without_double_counting():
    report = first()
    before, after = report["historical_summary"], report["current_summary"]
    assert after["pair_occurrences"] == 25
    assert after["distinct_pairs"] == 22
    assert after["distinct_known_pairs"] == 6
    assert after["distinct_unknown_pairs"] == 16
    assert before["methods"]["candidate_v2"] == {
        "matching": 5,
        "mismatching": 0,
        "unsupported": 1,
    }
    assert after["methods"]["candidate_v2"] == {
        "matching": 4,
        "mismatching": 1,
        "unsupported": 1,
    }
    for delta in report["label_and_anchor_deltas"]:
        if delta["id"] == "DTCW1947-GS-12":
            assert delta["historical_check"]["reference"]["expected_converted"] is True
            assert delta["current_check"]["reference"]["expected_converted"] is False
            assert delta["current_check"]["observations"]["candidate_v2"] == {
                "applicable": True,
                "converted": True,
                "matches": False,
            }
    assert report["new_independent_cases"] == 0
    assert not report["operator_gain"] and not report["adopted"]
    assert not report["classical_acceptance_passed"]


@pytest.mark.parametrize(
    "kind,error",
    [
        ("duplicate", "Duplicate correction"),
        ("wrong_old", "no longer matches"),
        ("wrong_type", "wrong type"),
        ("wrong_case", "Unknown correction case"),
        ("wrong_field", "Unsupported correction field"),
        ("wrong_page", "another source page"),
        ("no_correction", "No source corrections"),
    ],
)
def test_misaddressed_or_invalid_correction_cannot_silently_apply(kind, error):
    audit = runner()
    _, development, errata = audit.load_inputs()
    if kind == "duplicate":
        errata["corrections"].append(deepcopy(errata["corrections"][0]))
    elif kind == "wrong_old":
        errata["corrections"][0]["original_value"] = False
    elif kind == "wrong_type":
        errata["corrections"][0]["corrected_value"] = "false"
    elif kind == "wrong_case":
        errata["corrections"][0]["case_id"] = "unknown"
    elif kind == "wrong_field":
        errata["corrections"][0]["field"] = "expected_strength"
    elif kind == "wrong_page":
        errata["corrections"][0]["pdf_page"] = 210
    else:
        errata["corrections"] = []
    with pytest.raises(ValueError, match=error):
        audit.corrected_reference(development, errata)


def test_same_physical_pair_cannot_hide_conflicting_labels():
    audit = runner()
    groups = first()["current_groups"]
    row = next(r for r in groups["exposed_v4"] if r["id"] == "DTCW1947-GS-12")
    row["source_checks"][0]["reference"]["expected_converted"] = True
    with pytest.raises(ValueError, match="Conflicting references"):
        audit.summarize(groups)


def test_correction_must_reach_every_declared_subject_and_exact_pair():
    audit = runner()
    _, development, errata = audit.load_inputs()
    groups = first()["historical_groups"]
    without = {
        g: [r for r in rows if r["id"] != "DTCW1947-GS-12"]
        for g, rows in groups.items()
    }
    with pytest.raises(ValueError, match="Not every declared correction"):
        audit.collate_groups(without, development, errata)
    row = next(r for r in groups["exposed_v4"] if r["id"] == "DTCW1947-GS-12")
    row["source_checks"][0]["reference"]["positions"] = ["month", "hour"]
    with pytest.raises(ValueError, match="Historical pair reference changed"):
        audit.collate_groups(groups, development, errata)


def test_fresh_replay_matches_all_first_fields_and_cannot_overwrite(tmp_path):
    path = tmp_path / "replay.json.gz"
    command = [sys.executable, str(SCRIPT), "--output", str(path)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(gzip.decompress(path.read_bytes()))
    for key, value in first().items():
        if key not in {"recorded_at_utc", "runner_sha256"}:
            assert report[key] == value, key
    assert report["runner_sha256"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    assert report["historical_runner_sha256"] == first()["runner_sha256"]
    before = path.read_bytes()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0 and "reserved" in result.stderr
    assert path.read_bytes() == before
