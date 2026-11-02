"""Audit literal seasonal cells and their complete symbolic board propagation."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from fatebridge.core.metaphysics.common import MetaphysicsSeed

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_seasonal_v1"
FREEZE_SHA = "bf5ba9b6fc53a6200a1b8948e605913823282df5f0be4091516064556ba7b010"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
DAYS = ["甲乙丙丁戊己庚辛壬癸"[i % 10] + BRANCHES[i % 12] for i in range(60)]
MONTHS = dict(
    zip(
        "寅卯辰巳午未申酉戌亥子丑",
        [
            "庚寅",
            "辛卯",
            "壬辰",
            "癸巳",
            "甲午",
            "乙未",
            "丙申",
            "丁酉",
            "戊戌",
            "己亥",
            "庚子",
            "辛丑",
        ],
    )
)
PROFILES: list[Literal["liuren_common_v1", "tanyuan_xieji_v1"]] = [
    "liuren_common_v1",
    "tanyuan_xieji_v1",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != FREEZE_SHA:
        raise ValueError("Frozen seasonal manifest changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    names = {"source-pages.pdf", "reference.json", "protocol.json"}
    if set(manifest["files"]) != names or {
        p.name for p in folder.iterdir()
    } != names | {"freeze.json"}:
        raise ValueError("Frozen seasonal source inventory changed")
    if any(sha(folder / n) != h for n, h in manifest["files"].items()):
        raise ValueError("Frozen seasonal source changed")
    ref: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    if (
        len(ref["literal_phase_table"]) != 5
        or any(len(row) != 5 for row in ref["literal_phase_table"].values())
        or len(ref["synthetic_cases"]) != 16
        or len(ref["literal_god_elements"]) != 12
        or set(ref["declared_month_partition"]) != set(BRANCHES)
    ):
        raise ValueError("Complete original seasonal denominators required")
    return ref


def seed_for(day: str, month: str) -> MetaphysicsSeed:
    from scripts.audit_ren_classical import make_seed

    s = cast("MetaphysicsSeed", make_seed(dict(day=day, hour="子", month=month)))
    return replace(
        s, pillars={**s.pillars, "month": (MONTHS[month][0], MONTHS[month][1])}
    )


def expected_row(
    ref: dict[str, Any], day: str, month: str, earth: str, sky: str, god: str
) -> dict[str, Any]:
    powers = ref["literal_phase_table"][ref["declared_month_partition"][month]]
    sky_phase = ref["branch_elements"][sky]
    god_phase = ref["literal_god_elements"][god]
    earth_phase = ref["branch_elements"][earth]
    empty = sky in ref["empty_pairs"][DAYS.index(day) // 10]
    power = powers[sky_phase]
    condition = None
    if empty:
        condition = "真空条件" if power in ref["true_empty_powers"] else "半空条件"
    return dict(
        earth_branch=earth,
        sky_branch=sky,
        sky_element=sky_phase,
        sky_seasonal_power=power,
        god=god,
        god_element=god_phase,
        god_seasonal_power=powers[god_phase],
        earth_element=earth_phase,
        earth_seasonal_power=powers[earth_phase],
        sky_xun_kong=empty,
        sky_empty_seasonal_condition=condition,
        effective_empty_class=None,
    )


def prior_hash(
    board: dict[str, Any], profile: str, old_metadata: dict[str, Any]
) -> str:
    # Copy the changed containers only; all original domain values still hash.
    value = {k: v for k, v in board.items() if k != "seasonal_evidence"}
    value["rule_trace"] = [
        r for r in board["rule_trace"] if r["rule_id"] != "liuren.seasonal_conditions"
    ]
    rules = {**value["ruleset"], "conventions": dict(value["ruleset"]["conventions"])}
    if (
        rules["version"] != "1.9.0"
        or rules["source_title"]
        != old_metadata["source_title"] + "、季节五态与本空条件"
    ):
        raise ValueError("Unapproved ruleset metadata delta")
    rules["version"] = old_metadata["version"]
    rules["source_title"] = old_metadata["source_title"]
    rules["conventions"].pop("seasonal_evidence")
    value["ruleset"] = rules
    return hashlib.sha256(canonical(value)).hexdigest()


def audit(baseline: Path) -> dict[str, Any]:
    ref = reference()
    with gzip.open(baseline, "rt", encoding="utf-8") as f:
        before = json.load(f)
    expected_keys = set(
        itertools.product(DAYS, BRANCHES, BRANCHES, PROFILES, [False, True])
    )
    old = {tuple(r["key"]): r["sha256"] for r in before["rows"]}
    if len(before["rows"]) != 34560 or set(old) != expected_keys:
        raise ValueError("Complete34560 old-board preservation ledger required")
    paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ] + [Path(__file__).resolve()]
    source_before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.liureng_seasonal import POWERS, seasonal_evidence
    from fatebridge.core.output_chinese import Liuren
    from fatebridge.core.output_liuren_seasonal import require_complete_seasonal

    literal_matches = POWERS == ref["literal_phase_table"]
    synthetic = []
    failures = []
    matrix = hashlib.sha256()
    counts: Counter[str] = Counter()
    gods = list(ref["literal_god_elements"])
    component_rows = 0
    for day, month, rotation in itertools.product(DAYS, BRANCHES, range(12)):
        god_map = {b: gods[(i + rotation) % 12] for i, b in enumerate(BRANCHES)}
        got = seasonal_evidence(
            day_ganzhi=day,
            month_branch=month,
            sky_by_earth=dict(zip(BRANCHES, BRANCHES)),
            god_by_sky=god_map,
        )
        for row in got["rows"]:
            exp = expected_row(
                ref, day, month, row["earth_branch"], row["sky_branch"], row["god"]
            )
            component_rows += 1
            counts[row["sky_empty_seasonal_condition"] or "not_raw_empty"] += 1
            matrix.update(canonical([day, month, row]))
            if row != exp:
                failures.append(
                    dict(
                        kind="component", day=day, month=month, actual=row, expected=exp
                    )
                )
    for c in ref["synthetic_cases"]:
        rotation = (gods.index(c["god"]) - BRANCHES.index(c["sky"])) % 12
        got = seasonal_evidence(
            day_ganzhi=c["day"],
            month_branch=c["month"],
            sky_by_earth=dict(zip(BRANCHES, BRANCHES)),
            god_by_sky={b: gods[(i + rotation) % 12] for i, b in enumerate(BRANCHES)},
        )
        row = next(r for r in got["rows"] if r["sky_branch"] == c["sky"])
        synthetic.append(
            dict(
                **c,
                matched=(row["sky_seasonal_power"], row["sky_empty_seasonal_condition"])
                == (c["expected_sky_power"], c["expected_raw_condition"]),
            )
        )
    preservation = []
    boards = []
    board_digest = hashlib.sha256()
    row_comparisons = 0
    for day, month, general, profile, diurnal in itertools.product(
        DAYS, BRANCHES, BRANCHES, PROFILES, [False, True]
    ):
        b = build_liureng_board(
            seed_for(day, month),
            month_general_override=general,
            guiren_profile=profile,
            is_diurnal_override=diurnal,
        )
        Liuren.model_validate(b)
        require_complete_seasonal(b)
        key = (day, month, general, profile, diurnal)
        ev = b["seasonal_evidence"]
        errors = []
        for row in ev["rows"]:
            exp = expected_row(
                ref, day, month, row["earth_branch"], row["sky_branch"], row["god"]
            )
            row_comparisons += 1
            if row != exp:
                errors.append(dict(actual=row, expected=exp))
        if errors:
            failures.append(dict(kind="board", key=key, errors=errors))
        if prior_hash(b, profile, before["rulesets"][profile]) != old[key]:
            preservation.append(list(key))
        record = dict(
            key=key,
            season_partition=ev["season_partition"],
            raw_true=ev["raw_true_condition_branches"],
            raw_half=ev["raw_half_condition_branches"],
            matched=not errors,
        )
        boards.append(record)
        board_digest.update(canonical(record))
    unchanged = source_before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    passed = (
        literal_matches
        and all(c["matched"] for c in synthetic)
        and not failures
        and not preservation
        and unchanged
    )
    return dict(
        literal_phase_cells=25,
        literal_table_matched=literal_matches,
        synthetic_cases=synthetic,
        component_cases=component_rows,
        component_condition_counts=dict(counts),
        component_observation_sha256=matrix.hexdigest(),
        symbolic_board_count=len(boards),
        symbolic_row_comparisons=row_comparisons,
        symbolic_board_observation_sha256=board_digest.hexdigest(),
        symbolic_boards=boards,
        failures=failures,
        preservation_differences=preservation,
        baseline_sha256=sha(baseline),
        source_manifest=source_before,
        implementation_unchanged=unchanged,
        engineering_checks_passed=passed,
        new_historical_events=0,
        new_empirical_events=0,
        month_partition_alternatives_adjudicated=False,
        full_classical_conformance=False,
        goal_complete=False,
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Refusing to overwrite seasonal audit")
    r = audit(a.baseline)
    a.output.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in r.items()
                if k not in ["source_manifest", "symbolic_boards", "synthetic_cases"]
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if r["engineering_checks_passed"] else 1)


if __name__ == "__main__":
    main()
