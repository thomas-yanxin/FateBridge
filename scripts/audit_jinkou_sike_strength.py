"""Compare the complete Sike chapter without treating twelve rows as universal."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_sike_strength_v1"
PIN = "ce8fa80c94242aa1ee7e10a2e98bd65b5762e3982dbdd52ad49e7965b2360d9e"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen Sike strength identity changed")
    manifest = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(manifest) | {"freeze.json"}:
        raise ValueError("Frozen Sike strength inventory changed")
    for name, digest in manifest.items():
        if sha(folder / name) != digest:
            raise ValueError("Frozen Sike strength content changed: " + name)
    witness = json.loads((folder / "witness.json").read_text())
    if sha(ROOT / witness["source_path"]) != witness["source_sha256"]:
        raise ValueError("Original complete Jingben PDF changed")
    from tests.ren_source_arithmetic import sike_strength

    if sike_strength(folder) != json.loads((folder / "reference.json").read_text()):
        raise ValueError("Independent source arithmetic differs")
    return {
        key: json.loads((folder / (key + ".json")).read_text())
        for key in ("readings", "reference", "witness", "protocol")
    }


def audit() -> dict[str, Any]:
    data = reference()
    from scripts.audit_jinkou_strength import REFERENCE_FREEZE_SHA256 as OLD_SCAN_PIN
    from scripts.audit_jinkou_strength import audit as original_strength_audit
    from scripts.audit_ren_classical import REFERENCE_FREEZE_SHA256 as OLD_CASE_PIN
    from scripts.audit_ren_classical import load_frozen_corpus

    if (OLD_SCAN_PIN, OLD_CASE_PIN) != (
        data["protocol"]["old_scan_reference_pin"],
        data["protocol"]["old_classical_case_pin"],
    ):
        raise ValueError("Original source or case identity differs")
    if (
        sha(ROOT / "tests/fixtures/ren_depth_v2/freeze.json")
        != data["protocol"]["old_online_reference_pin"]
    ):
        raise ValueError("Original online inference reference identity differs")
    original = load_frozen_corpus()
    old_strength = original_strength_audit()
    from fatebridge.core.metaphysics.jinkou_strength import internal_strength

    paths = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    cases, actual_cases, failures = [], {}, []
    for reading, expected in zip(
        data["readings"]["cases"], data["reference"]["cases"], strict=True
    ):
        if reading["id"] != expected["id"]:
            raise ValueError("Sike case and independent answer identity differ")
        rows = [
            dict(label=p, element=e)
            for p, e in zip(
                data["readings"]["positions"], reading["elements"], strict=True
            )
        ]
        value = internal_strength(rows)
        selected = {
            k: value[k] for k in ("anchor_element", "candidate_elements", "powers")
        }
        expected_selected = {k: expected[k] for k in selected}
        bounded_math_unchanged = selected == expected_selected
        unqualified_certificate_absent = (
            value["source_evidence"]["daily_five_states_adjudicated"] is False
            and value["source_evidence"]["complete_classical_acceptance"] is False
        )
        actual_cases[reading["id"]] = value
        row = dict(
            reading=reading,
            actual=selected,
            independent_bounded_reference=expected_selected,
            bounded_math_unchanged=bounded_math_unchanged,
            unqualified_certificate_absent=unqualified_certificate_absent,
            calendar_reconstruction="not_attempted_missing_coordinates_not_filled",
        )
        cases.append(row)
        if not bounded_math_unchanged or not unqualified_certificate_absent:
            failures.append(dict(kind="bounded_inference", **row))
    mentions = []
    for reading, expected in zip(
        data["readings"]["mentions"], data["reference"]["raw_mentions"], strict=True
    ):
        if reading["id"] != expected["id"]:
            raise ValueError("Sike source mention identity differs")
        case = next(c for c in data["readings"]["cases"] if c["id"] == reading["case"])
        value = actual_cases[reading["case"]]
        if reading["target_kind"] == "element":
            index = case["elements"].index(reading["target"])
            actual = value["powers"][data["readings"]["positions"][index]]
        elif reading["target_kind"] == "position":
            actual = value["powers"][reading["target"]]
        else:
            actual = [value["powers"][p] for p in reading["target"]]
        if reading["stated"] == "衰":
            matched = None  # No source-qualified map from coarse 衰 to five states.
        elif isinstance(reading["stated"], list):
            matched = sorted(actual) == sorted(reading["stated"])
        else:
            matched = actual == reading["stated"]
        row = dict(
            reading=reading,
            current_bounded_state=actual,
            raw_same_state=matched,
            source_intended_layer=reading["intended_layer"],
            source_layer_adjudicated=False,
            raw_comparison_not_a_calendar_or_algorithm_error_verdict=True,
        )
        mentions.append(row)
        if actual != expected["actual"] or matched is not expected["raw_same_state"]:
            failures.append(dict(kind="reference_replay", **row))
    if before != {str(p.relative_to(ROOT)): sha(p) for p in paths}:
        raise ValueError("Production source changed during Sike strength review")
    return dict(
        source_review_pin=PIN,
        source_witness=data["witness"],
        implementation_sha256=before,
        cases=cases,
        case_count=len(cases),
        raw_strength_mentions=mentions,
        mention_count=len(mentions),
        raw_same_count=sum(r["raw_same_state"] is True for r in mentions),
        raw_different_count=sum(r["raw_same_state"] is False for r in mentions),
        raw_unmapped_count=sum(r["raw_same_state"] is None for r in mentions),
        duplicate_mention_ids=[
            r["id"] for r in data["readings"]["mentions"] if "duplicate_of" in r
        ],
        all_raw_strength_mentions_agree=all(
            r["raw_same_state"] is True for r in mentions
        ),
        source_intended_layers_adjudicated=False,
        unknown_months_not_inferred_from_month_general=True,
        original_classical_case_count=len(original["cases"]["cases"]),
        original_classical_unresolved=original["cases"]["unresolved"],
        original_scan_audit=old_strength,
        engineering_guard_failures=failures,
        engineering_guard_passed=not failures,
        old_gates_unchanged=True,
        production_algorithm_changed=False,
        new_historical_or_real_world_outcomes=0,
        new_llm_processes=0,
        real_world_prediction="deferred_by_user",
        calendar_validation="not_reassessed",
        free_text_fidelity="not_reassessed",
        classical_acceptance_passed=False,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing audit")
    report = audit()
    with args.output.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "case_count",
                    "mention_count",
                    "raw_same_count",
                    "raw_different_count",
                    "raw_unmapped_count",
                    "engineering_guard_passed",
                    "all_raw_strength_mentions_agree",
                )
            }
        )
    )
    return (
        0
        if report["engineering_guard_passed"]
        and report["all_raw_strength_mentions_agree"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
