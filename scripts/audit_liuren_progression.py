"""Audit frozen original sequence examples, expansions and raw-empty conditions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_progression_v1"
FREEZE_SHA = "9f11503edbb242297afb17f3c2335f1f0682048e4315592ecde5748fa660360d"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
DAYS = ["甲乙丙丁戊己庚辛壬癸"[i % 10] + BRANCHES[i % 12] for i in range(60)]
KEYS = [
    "kind",
    "sequence_direction",
    "empty_branches",
    "branch_xun_kong",
    "raw_branch_empty_conditional_reading",
    "raw_branch_empty_conditional_direction",
    "effective_direction",
    "comprehensive_judgement",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != FREEZE_SHA:
        raise ValueError("Frozen progression manifest changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    if set(manifest["files"]) != {"reference.json", "source-pages.pdf"} or {
        p.name for p in folder.iterdir()
    } != {"reference.json", "source-pages.pdf", "freeze.json"}:
        raise ValueError("Frozen progression inventory changed")
    if any(sha(folder / n) != h for n, h in manifest["files"].items()):
        raise ValueError("Frozen progression reference changed")
    ref: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    if (
        len(ref["literal_examples"]) != 8
        or len(ref["rotation_expansions"]) != 48
        or len({tuple(r["branches"]) for r in ref["rotation_expansions"]}) != 48
        or len(ref["synthetic_cases"]) != 11
        or len(ref["day_empty_pairs"]) != 6
    ):
        raise ValueError("Complete progression denominators required")
    return ref


def expected(ref: dict[str, Any], day: str, branches: list[str]) -> dict[str, Any]:
    # Lookup in pre-candidate explicit expansions, independent of modular detector.
    match = next(
        (r for r in ref["rotation_expansions"] if r["branches"] == branches), None
    )
    kind, direction = (match["kind"], match["direction"]) if match else (None, None)
    empty = list(ref["day_empty_pairs"][DAYS.index(day) // 10])
    flags = [b in empty for b in branches]
    reading, conditional = None, direction
    if kind == "连茹":
        if flags[0]:
            reading, conditional = "初空进退受阻", None
        elif flags[2]:
            reading, conditional = (
                ("末空以退论", "退") if direction == "进" else ("末空以进言", "进")
            )
        else:
            reading = "按支序进读" if direction == "进" else "按支序退读"
    elif kind == "间断":
        if True in flags:
            reading, conditional = "见空不拘原进退说", None
        else:
            reading = "前进多阻" if direction == "进" else "后退有妨"
    return dict(
        kind=kind,
        sequence_direction=direction,
        empty_branches=empty,
        branch_xun_kong=flags,
        raw_branch_empty_conditional_reading=reading,
        raw_branch_empty_conditional_direction=conditional,
        effective_direction=None,
        comprehensive_judgement=None,
    )


def old_shape(board: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(board)
    value.pop("transmission_progression")
    value["rule_trace"] = [
        r
        for r in value["rule_trace"]
        if r["rule_id"] != "liuren.transmission_progression"
    ]
    # Only declared new layer metadata may differ; no blanket replacement.
    rules = value["ruleset"]
    for name in ["version", "source_title"]:
        rules[name] = old["ruleset"][name]
    rules["conventions"].pop("transmission_progression")
    return value


def audit(baseline: Path | None = None) -> dict[str, Any]:
    paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ] + [Path(__file__).resolve()]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    ref = reference()
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.liureng_progression import transmission_progression
    from fatebridge.core.output_chinese import Liuren
    from fatebridge.core.output_liuren_progression import require_complete_progression
    from scripts.audit_ren_classical import make_seed

    failures: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    digest = hashlib.sha256()
    for day, triple in itertools.product(DAYS, itertools.product(BRANCHES, repeat=3)):
        branches = list(triple)
        actual = transmission_progression(day, branches)
        exp = expected(ref, day, branches)
        got = {k: actual[k] for k in KEYS}
        counts[
            actual["raw_branch_empty_conditional_reading"] or "no_listed_structure"
        ] += 1
        digest.update(
            json.dumps(
                [day, branches, got], ensure_ascii=False, sort_keys=True
            ).encode()
        )
        if got != exp:
            failures.append(dict(day=day, branches=branches, actual=got, expected=exp))
    synthetic = []
    for c in ref["synthetic_cases"]:
        got = transmission_progression(c["day"], c["branches"])
        synthetic.append(
            dict(
                **c,
                matched=(
                    got["kind"],
                    got["sequence_direction"],
                    got["raw_branch_empty_conditional_reading"],
                )
                == (c["kind"], c["direction"], c["reading"]),
            )
        )
    base = json.loads(baseline.read_text())["rows"] if baseline else None
    if base is not None and (
        len(base) != 720 or len({(r["day"], r["general"]) for r in base}) != 720
    ):
        raise ValueError("Full720 preservation baseline required")
    base_map = {(r["day"], r["general"]): r["board"] for r in base} if base else {}
    boards, differences = [], []
    for day, general in itertools.product(DAYS, BRANCHES):
        b = build_liureng_board(
            make_seed(dict(day=day, hour="子")), month_general_override=general
        )
        Liuren.model_validate(b)
        require_complete_progression(b)
        branches = [
            b["three_transmissions"][n]["branch"]
            for n in ["initial", "middle", "final"]
        ]
        got = b["transmission_progression"]
        exp = expected(ref, day, branches)
        matched = {k: got[k] for k in KEYS} == exp
        if not matched:
            failures.append(dict(day=day, general=general, actual=got, expected=exp))
        if base_map and old_shape(b, base_map[day, general]) != base_map[day, general]:
            differences.append(dict(day=day, general=general))
        boards.append(
            dict(
                day=day,
                general=general,
                branches=branches,
                matched=matched,
                kind=got["kind"],
                reading=got["raw_branch_empty_conditional_reading"],
            )
        )
    jinkou_preserved = None
    if baseline:
        seed = make_seed(dict(day="丙寅", hour="子"))
        b = build_liureng_board(seed, month_general_override="卯")
        jinkou_preserved = build_jinkou_board(seed, b, di_fen="酉") == json.loads(
            baseline.with_name("baseline-jinkou.json").read_text()
        )
    unchanged = before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    passed = (
        not failures
        and all(r["matched"] for r in synthetic)
        and not differences
        and unchanged
        and jinkou_preserved is not False
    )
    return dict(
        literal_examples=8,
        rotational_expansions=48,
        synthetic_cases=synthetic,
        mathematical_cases=103680,
        mathematical_counts=dict(counts),
        mathematical_observation_sha256=digest.hexdigest(),
        symbolic_board_count=720,
        symbolic_boards=boards,
        failures=failures,
        baseline_compared=base is not None,
        preservation_differences=differences,
        jinkou_body_preserved=jinkou_preserved,
        source_manifest=before,
        implementation_unchanged=unchanged,
        engineering_checks_passed=passed,
        new_historical_events=0,
        new_empirical_events=0,
        full_classical_conformance=False,
        goal_complete=False,
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite audit output")
    result = audit(args.baseline)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ["source_manifest", "symbolic_boards", "synthetic_cases"]
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if result["engineering_checks_passed"] else 1)


if __name__ == "__main__":
    main()
