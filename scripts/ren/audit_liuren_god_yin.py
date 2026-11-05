"""Audit primary lookup examples and a separately declared symbolic matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_god_yin_v1"
PIN = "884b06655608003346afc473daf704feff08de88c4a71a43174f5c99998ff30d"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"
GODS = "贵人 螣蛇 朱雀 六合 勾陈 青龙 天空 白虎 太常 玄武 太阴 天后".split()
PROFILES: list[Literal["liuren_common_v1", "tanyuan_xieji_v1"]] = [
    "liuren_common_v1",
    "tanyuan_xieji_v1",
]
WATCH = (
    "src/fatebridge/core/metaphysics/liureng_god_yin.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/ren_gods.py",
    "src/fatebridge/core/output_liuren_god_yin.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/output_ren_anchors.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/ren/audit_liuren_god_yin.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference() -> dict[str, Any]:
    if sha(CORPUS / "freeze.json") != PIN:
        raise ValueError("Frozen yin-spirit protocol changed")
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    if {p.name for p in CORPUS.iterdir()} != set(frozen["files"]) | {"freeze.json"}:
        raise ValueError("Frozen yin-spirit source inventory changed")
    if any(sha(CORPUS / n) != d for n, d in frozen["files"].items()):
        raise ValueError("Frozen yin-spirit source bytes changed")
    value: dict[str, Any] = json.loads((CORPUS / "cases.json").read_text())
    return value


def audit() -> dict[str, Any]:
    ref = reference()
    before = {n: sha(ROOT / n) for n in WATCH}
    from scripts.ren.audit_ren_classical import load_frozen_corpus, make_seed
    from scripts.ren.audit_ren_depth import load_reference

    common = load_frozen_corpus()["rules"]["guiren"]
    selected = load_reference()["tanyuan-rules"]["noble_starts"]
    starts = {
        "liuren_common_v1": {row["stem"]: row for row in common},
        "tanyuan_xieji_v1": {row["stem"]: row for row in selected},
    }
    from fatebridge.core.metaphysics.liureng import build_liureng_board

    literal = []
    for case in ref["explicit_examples"]:
        board = build_liureng_board(
            make_seed({"day": "甲子", "hour": "子", "month": "寅"}),
            month_general_override="申",
            guiren_profile="tanyuan_xieji_v1",
            is_diurnal_override=case.get("is_diurnal", True),
        )
        row = next(r for r in board["god_yin"]["rows"] if r["god"] == case["god"])
        keys = [
            k
            for k in [
                "riding_earth_branch",
                "riding_branch",
                "yin_branch",
                "derivation",
            ]
            if k in case
        ]
        literal.append(
            dict(id=case["id"], matched=all(row[k] == case[k] for k in keys))
        )
    failures = []
    boards, rows_checked, predicate_leaks = 0, 0, 0
    for day_index in range(60):
        day = STEMS[day_index % 10] + BRANCHES[day_index % 12]
        for offset in range(12):
            # Twelve month branches are cycled across the twelve offsets;
            # this is not the full Cartesian product of months and offsets.
            month = BRANCHES[offset]
            for profile in PROFILES:
                for diurnal in (False, True):
                    board = build_liureng_board(
                        make_seed({"day": day, "hour": "子", "month": month}),
                        month_general_override=BRANCHES[offset],
                        guiren_profile=profile,
                        is_diurnal_override=diurnal,
                    )
                    expected_start = starts[profile][day[0]][
                        "day" if diurnal else "night"
                    ]
                    expected_other = starts[profile][day[0]][
                        "night" if diurnal else "day"
                    ]
                    noble_index = BRANCHES.index(expected_start)
                    earth_noble_index = (noble_index - offset) % 12
                    direction = (
                        -1 if BRANCHES[earth_noble_index] in "巳午未申酉戌" else 1
                    )
                    observed = {r["god"]: r for r in board["god_yin"]["rows"]}
                    for i, god in enumerate(GODS):
                        riding_index = (noble_index + direction * i) % 12
                        riding = BRANCHES[riding_index]
                        yin = (
                            expected_other
                            if god == "贵人"
                            else BRANCHES[(riding_index + offset) % 12]
                        )
                        expected = (
                            riding,
                            BRANCHES[(riding_index - offset) % 12],
                            yin,
                            BRANCHES[(BRANCHES.index(yin) - offset) % 12],
                        )
                        row = observed[god]
                        actual = tuple(
                            row[k]
                            for k in [
                                "riding_branch",
                                "riding_earth_branch",
                                "yin_branch",
                                "yin_earth_branch",
                            ]
                        )
                        if actual != expected:
                            failures.append(
                                dict(
                                    day=day,
                                    offset=offset,
                                    profile=profile,
                                    is_diurnal=diurnal,
                                    god=god,
                                    actual=actual,
                                    expected=expected,
                                )
                            )
                        predicate_leaks += row["comprehensive_eligibility"] is not None
                        rows_checked += 1
                    boards += 1
    after = {n: sha(ROOT / n) for n in WATCH}
    return dict(
        audit_id="liuren_god_yin_v1",
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=after,
        implementation_unchanged_during_audit=before == after,
        original_conditional_examples=literal,
        original_example_count=4,
        original_examples_matched=sum(r["matched"] for r in literal),
        synthetic_board_count=boards,
        synthetic_god_rows_checked=rows_checked,
        matrix_dimensions="60 days x12 offsets x2 noble profiles x2 explicit day/night. Month branch cycled with offset, not a full month Cartesian product.",
        matrix_failures=failures,
        comprehensive_verdict_leaks=predicate_leaks,
        independent_historical_events=0,
        new_model_processes=0,
        engineering_checks_passed=before == after
        and all(r["matched"] for r in literal)
        and not failures
        and predicate_leaks == 0,
        full_calendar_acceptance=False,
        full_classical_acceptance=False,
        free_model_interpretation_revalidated=False,
        real_world_validation="deferred_by_user",
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "original_examples_matched",
                    "synthetic_board_count",
                    "synthetic_god_rows_checked",
                    "engineering_checks_passed",
                    "goal_complete",
                ]
            }
        )
    )
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
