"""Qualify three Siku passages without upgrading unresolved rules or old gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_daquan_cross_scan_v1"
PIN = "ca9347ab9d5706f556d6b6717f804a912e245d129dae52422362bce1ac10872a"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen Siku scan identity changed")
    files = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(files) | {"freeze.json"}:
        raise ValueError("Frozen Siku scan inventory changed")
    for name, digest in files.items():
        if sha(folder / name) != digest:
            raise ValueError("Frozen Siku scan content changed: " + name)
    from tests.support.ren_source_arithmetic import daquan_cross_scan

    if daquan_cross_scan(folder) != json.loads((folder / "reference.json").read_text()):
        raise ValueError("Independent source arithmetic differs")
    return {
        key: json.loads((folder / (key + ".json")).read_text())
        for key in ("readings", "examples", "reference", "witness", "protocol")
    }


def normalized(text: str, replacements: list[list[str]]) -> str:
    for old, new in replacements:
        text = text.replace(old, new)
    return "".join(c for c in text if c not in "，。；、 \t\r\n")


def audit() -> dict[str, Any]:
    review = reference()
    from scripts.ren.audit_liuren_cross_harmony import PIN as OLD_PIN
    from scripts.ren.audit_liuren_cross_harmony import expected_facts
    from scripts.ren.audit_liuren_cross_harmony import reference as old_reference
    from scripts.ren.audit_liuren_day_placements import (
        expected_facts as placement_facts,
    )
    from scripts.ren.audit_liuren_day_placements import reference as placement_reference

    old = old_reference()
    placements = placement_reference()
    if OLD_PIN != review["protocol"]["old_reference_pin"]:
        raise ValueError("Original cross-harmony reference identity differs")
    from fatebridge.core.metaphysics.liureng_cross_harmony import cross_harmony
    from fatebridge.core.metaphysics.liureng_day_placements import (
        day_placement_patterns,
    )

    watched = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in watched}
    passages = []
    for item in review["readings"]["passages"]:
        previous = old["reading"][item["old_field"]]
        passages.append(
            dict(
                **item,
                previous_transcription=previous,
                selected_passage_agrees=normalized(previous, item["normalizations"])
                == normalized(item["literal"], item["normalizations"]),
            )
        )
    illustrations = []
    for item, expected in zip(
        review["examples"]["examples"], review["reference"]["rows"], strict=True
    ):
        if item["id"] != expected["id"]:
            raise ValueError("Printed mention and coordinate identities differ")
        if expected["input_status"] == "not_assessed_incomplete_context":
            illustrations.append(
                dict(
                    reading=item,
                    reference=expected,
                    actual=None,
                    calculation_agrees=None,
                    status="not_assessed_incomplete_context",
                )
            )
            continue
        actual = cross_harmony(expected["day_ganzhi"], expected["sky_by_earth"])
        selected = {k: actual[k] for k in ("stem_upper", "branch_upper", "matched")}
        agrees = selected == dict(
            stem_upper=expected["stem_upper"],
            branch_upper=expected["branch_upper"],
            matched=expected["formula_expected"],
        )
        illustrations.append(
            dict(
                reading=item,
                reference=expected,
                actual=selected,
                calculation_agrees=agrees,
                status="matched_selected_formula" if agrees else "different",
            )
        )
    original_rows = []
    for row, old_placement in zip(
        old["reference"]["contexts"], placements["contexts"], strict=True
    ):
        day, sky = row["day_ganzhi"], row["sky_by_earth"]
        if (old_placement["day_ganzhi"], old_placement["sky_by_earth"]) != (
            day,
            sky,
        ):
            raise ValueError("Original day-placement and cross cohorts differ")
        actual = cross_harmony(day, sky)
        expected_old = expected_facts(row)
        placement = day_placement_patterns(day, sky)
        expected_placement = placement_facts(old_placement, placements["reading"])
        original_rows.append(
            dict(
                day_ganzhi=day,
                rotation=row["rotation"],
                cross_facts_unchanged={k: actual[k] for k in expected_old}
                == expected_old,
                placement_facts_unchanged={k: placement[k] for k in expected_placement}
                == expected_placement,
                source_metadata_still_transcription_only=actual["source_kind"]
                == "frozen_primary_transcription_not_scan_collated",
                no_whole_book_certificate=actual["complete_classical_conformance"]
                is False,
            )
        )
    after = {str(p.relative_to(ROOT)): sha(p) for p in watched}
    if before != after:
        raise ValueError("Production source changed during Siku review")
    failures = [
        dict(kind="passage", **r) for r in passages if not r["selected_passage_agrees"]
    ]
    failures.extend(
        dict(kind="illustration", **r)
        for r in illustrations
        if r["calculation_agrees"] is False
    )
    failures.extend(
        dict(kind="original_cohort", **r)
        for r in original_rows
        if not all(v for k, v in r.items() if k not in ("day_ganzhi", "rotation"))
    )
    return dict(
        source_review_pin=PIN,
        original_cross_reference_pin=OLD_PIN,
        implementation_sha256=before,
        source_witness=review["witness"],
        selected_passages=passages,
        printed_mentions=len(illustrations),
        coordinate_assessable=sum(
            r["calculation_agrees"] is not None for r in illustrations
        ),
        coordinate_unknown=sum(r["calculation_agrees"] is None for r in illustrations),
        distinct_assessable_contexts=review["reference"][
            "distinct_assessable_contexts"
        ],
        illustrations=illustrations,
        original_contexts=len(original_rows),
        original_rows=original_rows,
        failures=failures,
        engineering_guard_passed=not failures,
        source_qualification="three_selected_passages_visually_collated_not_whole_book",
        subtype_formulae_adjudicated=False,
        original_D11_D12_adjudicated=False,
        new_historical_or_empirical_events=0,
        new_llm_processes=0,
        real_world_prediction="deferred_by_user",
        production_source_metadata_requalified=False,
        production_ruleset_version_changed=False,
        calculation_algorithm_changed=False,
        transport_validation="not_reassessed_no_contract_or_calculation_change",
        calendar_validation="not_reassessed",
        free_text_fidelity="not_reassessed",
        original_gates_unchanged=True,
        complete_classical_conformance=False,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing audit")
    result = audit()
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "printed_mentions",
                    "coordinate_assessable",
                    "coordinate_unknown",
                    "engineering_guard_passed",
                    "goal_complete",
                )
            }
        )
    )
    return 0 if result["engineering_guard_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
