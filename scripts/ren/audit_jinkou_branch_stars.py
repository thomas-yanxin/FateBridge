"""Compare frozen Jingben target tables, factor matrices and old-board values."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_branch_stars_v1"
FREEZE_SHA = "3bf2f27c76410b400391b0dfe71a38dfa6a942e463d1047ea33f6bb50db66bf2"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
POSITIONS = ("贵神", "将神", "地分")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != FREEZE_SHA:
        raise ValueError("Frozen branch-star manifest changed")
    m = json.loads((folder / "freeze.json").read_text())
    names = {"reference.json", "source-pages.pdf"}
    if set(m["files"]) != names or {p.name for p in folder.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen branch-star source inventory changed")
    if any(sha(folder / n) != h for n, h in m["files"].items()):
        raise ValueError("Frozen branch-star source changed")
    value: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    if len(value["synthetic_cases"]) != 5 or len(value["month_order"]) != 12:
        raise ValueError("Frozen branch-star denominators changed")
    return value


def expected(
    ref: dict[str, Any], year: str, month: str, day: str, inputs: dict[str, str]
) -> dict[str, Any]:
    index = ref["month_order"].index(month)
    targets = {k: v[index] for k, v in ref["expanded_month_targets"].items()}
    targets.update(
        {
            k: BRANCHES[(BRANCHES.index(year) + offset) % 12]
            for k, offset in ref["annual_offsets"].items()
        }
    )
    return {
        k: dict(
            target=t,
            matched_day=day == t if k == "tianshe" else None,
            matched_positions=(
                [] if k == "tianshe" else [p for p in POSITIONS if inputs[p] == t]
            ),
        )
        for k, t in targets.items()
    }


def audit() -> dict[str, Any]:
    ref = reference()
    source_paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ] + [Path(__file__).resolve()]
    before = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    from fatebridge.core.metaphysics.jinkou_branch_stars import branch_stars
    from fatebridge.core.output_jinkou_branch_stars import (
        JinkouBranchStars,
    )

    errors = []
    digest = hashlib.sha256()
    counts = dict(monthly_factor_checks=0, annual_factor_checks=0, day_month_checks=0)

    def check(
        year: str, month: str, day: str, inputs: dict[str, str], group: str
    ) -> None:
        got = branch_stars(
            year_branch=year, month_branch=month, day_ganzhi=day, input_branches=inputs
        )
        JinkouBranchStars.model_validate(got)
        wanted = expected(ref, year, month, day, inputs)
        actual = {
            c["id"]: {k: c[k] for k in ["target", "matched_day", "matched_positions"]}
            for c in got["checks"]
        }
        counts[group] += 1
        digest.update(
            json.dumps(
                [group, year, month, day, inputs, actual],
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        )
        if actual != wanted:
            errors.append(
                dict(
                    group=group,
                    inputs=[year, month, day, inputs],
                    actual=actual,
                    expected=wanted,
                )
            )

    for month, branches in itertools.product(
        BRANCHES, itertools.product(BRANCHES, repeat=3)
    ):
        check(
            "子", month, "甲子", dict(zip(POSITIONS, branches)), "monthly_factor_checks"
        )
    for year, branches in itertools.product(
        BRANCHES, itertools.product(BRANCHES, repeat=3)
    ):
        check(
            year, "寅", "甲子", dict(zip(POSITIONS, branches)), "annual_factor_checks"
        )
    days = ["甲乙丙丁戊己庚辛壬癸"[i % 10] + BRANCHES[i % 12] for i in range(60)]
    for month, day in itertools.product(BRANCHES, days):
        check("子", month, day, dict(zip(POSITIONS, "子寅酉")), "day_month_checks")
    synthetic = []
    for c in ref["synthetic_cases"]:
        got = branch_stars(
            year_branch=c["year"],
            month_branch=c["month"],
            day_ganzhi=c["day"],
            input_branches=dict(zip(POSITIONS, c["branches"])),
        )
        actual = {
            v["id"]: (
                v["matched_day"] if v["id"] == "tianshe" else v["matched_positions"]
            )
            for v in got["checks"]
        }
        synthetic.append(
            dict(
                id=c["id"],
                actual=actual,
                expected=c["expected"],
                matched=actual == c["expected"],
            )
        )
    unchanged = before == {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    return dict(
        reference_freeze_sha256=FREEZE_SHA,
        source_manifest=before,
        implementation_unchanged=unchanged,
        factor_checks=counts,
        factor_observation_sha256=digest.hexdigest(),
        failures=errors,
        synthetic_comparisons=synthetic,
        selected_checks_passed=not errors
        and all(c["matched"] for c in synthetic)
        and unchanged,
        reused_factor_combinations_not_independent_charts=True,
        complete_chapter_conformance=False,
        full_classical_conformance=False,
        new_historical_events=0,
        new_empirical_events=0,
        goal_complete=False,
    )
