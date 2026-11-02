"""Primary witness anchors and necessary layout sets, never prediction scores."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_course_layout_v1"
PIN = "08bb40a3de13ad607f3ceb059fa00bac322ecd15b77a83ef359e25845f52d245"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(path: Path = CORPUS) -> dict[str, Any]:
    if sha(path / "freeze.json") != PIN:
        raise ValueError("Course layout source manifest changed")
    files = json.loads((path / "freeze.json").read_text())["files"]
    expected = {
        "zhuji-1.pdf",
        "zhuji-2.pdf",
        "gugong-419.pdf",
        "readings.json",
        "protocol.json",
        "life-reference.json",
        "course-readings.json",
        "noble-tanyuan-reference.json",
    }
    if set(files) != expected or {p.name for p in path.iterdir()} != expected | {
        "freeze.json"
    }:
        raise ValueError("Course layout source inventory changed")
    for name, digest in files.items():
        if sha(path / name) != digest:
            raise ValueError("Course layout source bytes changed: " + name)
    return {
        name.removesuffix(".json"): json.loads((path / name).read_text())
        for name in expected
        if name.endswith(".json")
    }


def audit() -> dict[str, Any]:
    ref = reference()
    from fatebridge.core.metaphysics.liureng import twelve_god_layout
    from fatebridge.core.metaphysics.liureng_course_layout import (
        layout_compatibility_basis,
        pair_layout_necessity,
    )
    from fatebridge.core.metaphysics.liureng_life_stages import life_stage_cycle
    from fatebridge.core.metaphysics.ren_gods import noble_start

    source = ROOT / "src/fatebridge/core/metaphysics/liureng_course_layout.py"
    before = sha(source)
    readings = ref["readings"]
    tables = {
        "liuren_common_v1": {r["stem"]: r for r in readings["common_noble_starts"]},
        "tanyuan_xieji_v1": {
            r["stem"]: r for r in ref["noble-tanyuan-reference"]["noble_starts"]
        },
    }
    clauses = [
        c for c in ref["course-readings"]["selected_clauses"] if c["id"].startswith("S")
    ]
    stages = ref["life-reference"]["stage_order"]
    anchors = ref["life-reference"]["anchors"]
    sequence = readings["noble_sequence"]
    failures = []
    literal_peaks = []
    literal_nobles = []
    pair_rows = []
    alternatives = []
    cycles = {}
    expected_pairs = {}
    for anchor in anchors:
        stem = anchor["stem"]
        cursor = BRANCHES.index(anchor["changsheng"])
        direction = 1 if anchor["direction"] == "顺" else -1
        by_stage = {
            stage: BRANCHES[(cursor + direction * i) % 12]
            for i, stage in enumerate(stages)
        }
        cycles[stem] = by_stage
        peak = readings["imperial_branches_by_day_stem"][stem]
        actual_peak = next(b for b, s in life_stage_cycle(stem).items() if s == "帝旺")
        literal_peaks.append(
            dict(
                stem=stem,
                expected=peak,
                actual=actual_peak,
                passed=by_stage["帝旺"] == peak == actual_peak,
            )
        )
        for profile, table in tables.items():
            for daylight, key in [(False, "night"), (True, "day")]:
                actual_start = noble_start(stem, daylight, profile)  # type: ignore[arg-type]
                row = dict(
                    stem=stem,
                    profile=profile,
                    daylight=daylight,
                    expected=table[stem][key],
                    actual=actual_start,
                    passed=actual_start == table[stem][key],
                )
                literal_nobles.append(row)
                if not row["passed"]:
                    failures.append(row)
        for clause in clauses:
            candidates = set()
            rank = sequence.index(clause["required_god"])
            for profile, table in tables.items():
                for daylight, key in [(False, "night"), (True, "day")]:
                    for direction in (1, -1):
                        branch = BRANCHES[
                            (BRANCHES.index(table[stem][key]) + direction * rank) % 12
                        ]
                        candidates.add(branch)
                        alternatives.append(
                            dict(
                                stem=stem,
                                id=clause["id"],
                                profile=profile,
                                daylight=daylight,
                                direction=direction,
                                god_branch=branch,
                                stage_branch=by_stage[clause["required_stage"]],
                            )
                        )
            expected = dict(
                required_stage_branch=by_stage[clause["required_stage"]],
                possible_god_branches=[b for b in BRANCHES if b in candidates],
                compatible_in_any_supported_noble_layout=by_stage[
                    clause["required_stage"]
                ]
                in candidates,
            )
            got = pair_layout_necessity(
                stem, clause["required_stage"], clause["required_god"]
            )
            row = dict(
                stem=stem,
                id=clause["id"],
                expected=expected,
                actual=got,
                passed=expected == got,
            )
            pair_rows.append(row)
            expected_pairs[stem, clause["id"]] = expected
            if not row["passed"]:
                failures.append(row)
    # Exhaust actual supported layouts, independently of nine-gate selection.
    # Both directions must actually occur somewhere in these hour/general grids.
    observed: dict[tuple[str, str], set[str]] = {
        (a["stem"], c["id"]): set() for a in anchors for c in clauses
    }
    layout_rows = []
    for anchor, profile, daylight, hour, general in itertools.product(
        anchors, tables, (False, True), BRANCHES, BRANCHES
    ):
        stem = anchor["stem"]
        layout = twelve_god_layout(hour_branch=hour, month_general_branch=general, day_stem=stem, is_diurnal=daylight, guiren_profile=profile)  # type: ignore[arg-type]
        for clause in clauses:
            observed[stem, clause["id"]].add(
                next(
                    b
                    for b, g in layout["god_by_sky"].items()
                    if g == clause["required_god"]
                )
            )
        layout_rows.append(
            dict(
                stem=stem,
                profile=profile,
                daylight=daylight,
                hour=hour,
                general=general,
                noble_earth=layout["noble_earth_branch"],
                reverse=layout["is_reverse"],
            )
        )
    for row in pair_rows:
        actual = [b for b in BRANCHES if b in observed[row["stem"], row["id"]]]
        row["actual_supported_layout_union"] = actual
        row["layout_union_passed"] = actual == row["expected"]["possible_god_branches"]
        if not row["layout_union_passed"]:
            failures.append(row)
    basis = layout_compatibility_basis()
    metadata_passed = (
        basis["source_reference_sha256"] == PIN
        and basis["unresolved_authorial_intent_ids"] == ["S05"]
        and basis["authorial_intent_adjudicated"] is None
        and basis["original_conditions_rewritten"] is False
        and basis["is_initial_transmission_guarantee"] is False
    )
    source_witness_checks = []
    for w in basis["witnesses"]:
        match = next(
            part
            for witness in readings["witnesses"]
            for part in witness["parts"]
            if part["source_sha256"] == w["source_sha256"]
        )
        source_witness_checks.append(
            dict(
                id=w["id"],
                sha256_matches=sha(CORPUS / match["file"]) == w["source_sha256"],
                url_matches=match["source_url"] == w["source_url"],
            )
        )
    return dict(
        source_reference_sha256=PIN,
        new_primary_witnesses=2,
        literal_peak_anchors=literal_peaks,
        noble_anchors=literal_nobles,
        new_common_noble_anchors=20,
        reused_tanyuan_noble_anchors=20,
        derived_pair_rows=pair_rows,
        orientation_contexts=alternatives,
        actual_layout_rows=layout_rows,
        actual_layout_count=len(layout_rows),
        source_witness_checks=source_witness_checks,
        metadata_passed=metadata_passed,
        failures=failures,
        chongwei_compatible_stems=[
            r["stem"]
            for r in pair_rows
            if r["id"] == "S05"
            and r["actual"]["compatible_in_any_supported_noble_layout"]
        ],
        engineering_checks_passed=not failures
        and all(r["passed"] for r in literal_peaks)
        and metadata_passed
        and all(r["sha256_matches"] and r["url_matches"] for r in source_witness_checks)
        and before == sha(source),
        implementation_unchanged=before == sha(source),
        authorial_intent_adjudicated=None,
        full_classical_conformance=False,
        new_historical_events=0,
        new_empirical_events=0,
        new_model_processes=0,
        goal_complete=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if not isinstance(v, list)},
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if result["engineering_checks_passed"] else 1)


if __name__ == "__main__":
    main()
