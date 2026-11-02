"""Replay frozen Jiaoche conditions and retain all original acceptance gates."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import runpy
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_cross_harmony_v1"
PIN = "17b3f0a7a1afe32dfeaac5d37e1d024b5db71de4230a156a0ca750ee6ae20f14"
BASELINE_SHA = "d497a0f73259096df385e254e1739550b38621524985ca7c16ae284e3f09aaa9"
BUSINESS_SHA = "3a17929b72440d0d64f541eaa130b9915eab5821739c62b0df838a2dc99e6455"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen cross-harmony identity changed")
    files = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(files) | {"freeze.json"} or any(
        sha(folder / n) != h for n, h in files.items()
    ):
        raise ValueError("Frozen cross-harmony inventory or content changed")
    reading = json.loads((folder / "readings.json").read_text())
    if sha(ROOT / reading["tanyuan_source_path"]) != reading["tanyuan_sha256"]:
        raise ValueError("Original Tanyuan primary witness changed")
    with tempfile.TemporaryDirectory(prefix="ren-cross-reference-") as name:
        temp = Path(name)
        for item in ("readings.json", "generate_reference.py.txt"):
            (temp / item).write_bytes((folder / item).read_bytes())
        runpy.run_path(str(temp / "generate_reference.py.txt"))
        if (temp / "reference.json").read_bytes() != (
            folder / "reference.json"
        ).read_bytes():
            raise ValueError("Independent cross-harmony reconstruction differs")
    return dict(
        reading=reading,
        reference=json.loads((folder / "reference.json").read_text()),
        protocol=json.loads((folder / "protocol.json").read_text()),
    )


def expected_facts(row: dict[str, Any]) -> dict[str, Any]:
    return {
        k: row[k]
        for k in (
            "day_ganzhi",
            "day_stem_house",
            "day_branch",
            "stem_upper",
            "branch_upper",
            "sky_by_earth",
            "distinct_anchors",
            "both_cross_pairs",
            "matched",
        )
    } | dict(
        cross_pairs=[
            dict(
                id="stem_upper_to_day_branch",
                left_role="干上神",
                right_role="日支",
                left_branch=row["stem_upper"],
                right_branch=row["day_branch"],
                liuhe=row["stem_upper_with_day_branch"],
            ),
            dict(
                id="branch_upper_to_stem_house",
                left_role="支上神",
                right_role="日干寄宫支",
                left_branch=row["branch_upper"],
                right_branch=row["day_stem_house"],
                liuhe=row["branch_upper_with_stem_house"],
            ),
        ],
        exclusion_reason=None if row["distinct_anchors"] else "干支同宫（八专五日）",
    )


def audit(before_dir: Path | None = None) -> dict[str, Any]:
    data = reference()
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.liureng_cross_harmony import (
        cross_harmony,
        cross_harmony_trace,
    )
    from fatebridge.core.output_liuren_cross_harmony import LiurenCrossHarmony
    from scripts.audit_ren_classical import make_seed
    from scripts.liuren_cross_harmony_archive import (
        historical_cross_harmony,
        strip_board,
    )

    watched = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
    ]
    source_before = {str(p.relative_to(ROOT)): sha(p) for p in watched}
    baselines = None
    if before_dir is not None:
        if (
            sha(before_dir / "boards-before.jsonl.gz") != BASELINE_SHA
            or sha(before_dir / "business-before.json") != BUSINESS_SHA
        ):
            raise ValueError("Pre-edit output identity changed")
        baselines = gzip.open(before_dir / "boards-before.jsonl.gz", "rt")
    literals, boards, failures = [], [], []
    try:
        for case in data["reference"]["contexts"]:
            actual = cross_harmony(case["day_ganzhi"], case["sky_by_earth"])
            expected = expected_facts(case)
            LiurenCrossHarmony.model_validate(actual)
            matched = {k: actual[k] for k in expected} == expected
            source_identity = (
                actual["source_sha256"] == sha(CORPUS / "daquan-siku-v9.html")
                and actual["source_url"] == data["reading"]["daquan_revision_url"]
                and actual["witness_source_sha256"] == data["reading"]["tanyuan_sha256"]
            )
            literal = dict(
                day=case["day_ganzhi"],
                rotation=case["rotation"],
                expected=expected,
                actual={k: actual[k] for k in expected},
                source_identity=source_identity,
                passed=matched and source_identity,
            )
            literals.append(literal)
            if not literal["passed"]:
                failures.append(dict(kind="literal", **literal))
            for profile in ("liuren_common_v1", "tanyuan_xieji_v1"):
                for daytime in (True, False):
                    board = build_liureng_board(
                        make_seed(dict(day=case["day_ganzhi"], hour="子")),
                        month_general_override="子丑寅卯辰巳午未申酉戌亥"[
                            case["rotation"]
                        ],
                        is_diurnal_override=daytime,
                        guiren_profile=profile,
                    )
                    own = board["cross_harmony"]
                    traces = [
                        t
                        for t in board["rule_trace"]
                        if t.get("rule_id") == "liuren.cross_harmony"
                    ]
                    ok = own == actual and traces == [cross_harmony_trace(actual)]
                    old_ok = None
                    if baselines is not None:
                        old = json.loads(next(baselines))
                        if (
                            old["day_ganzhi"],
                            old["rotation"],
                            old["guiren_profile"],
                            old["is_diurnal"],
                        ) != (case["day_ganzhi"], case["rotation"], profile, daytime):
                            raise ValueError("Pre-edit input identity differs")
                        old_ok = strip_board(board, case["day_ganzhi"]) == old["board"]
                    row = dict(
                        day=case["day_ganzhi"],
                        rotation=case["rotation"],
                        profile=profile,
                        is_diurnal=daytime,
                        matched=own["matched"],
                        passed=ok,
                        old_complete_board_unchanged=old_ok,
                    )
                    boards.append(row)
                    if not ok or old_ok is False:
                        failures.append(dict(kind="board", **row))
        if baselines is not None and next(baselines, None) is not None:
            raise ValueError("Pre-edit cohort contains unexpected rows")
    finally:
        if baselines is not None:
            baselines.close()
    businesses = []
    if before_dir is not None:
        from fatebridge.services.tool_catalog import CATALOG

        specs = {s.key: s for s in CATALOG}
        payloads = json.loads(
            (ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text()
        )["payloads"]
        for key, old in json.loads(
            (before_dir / "business-before.json").read_text()
        ).items():
            spec = specs[key]
            fn, args, kwargs = spec.bind(
                spec.request_model.model_validate(payloads[key])
            )
            value = fn(*args, **kwargs)
            stripped, receipt = historical_cross_harmony(value, mode="strip")
            row = dict(
                key=key,
                old_complete_business_unchanged=stripped == old,
                reversible=receipt["original_restored_exactly"],
            )
            businesses.append(row)
            if not row["old_complete_business_unchanged"]:
                failures.append(dict(kind="business", **row))
    reference()
    stable = source_before == {str(p.relative_to(ROOT)): sha(p) for p in watched}
    return dict(
        source_pin=PIN,
        implementation_sha256=source_before,
        implementation_unchanged=stable,
        literal_contexts=len(literals),
        literal_rows=literals,
        symbolic_contexts=len(boards),
        symbolic_rows=boards,
        business_comparisons=businesses,
        failures=failures,
        engineering_checks_passed=stable and not failures,
        legacy_comparison=(
            "passed"
            if before_dir is not None and not failures
            else "not_assessed" if before_dir is None else "failed"
        ),
        naive_two_pair_matches=60,
        source_named_matches=55,
        explicit_same_anchor_exclusions=data["reference"][
            "shared_anchor_excluded_days"
        ],
        new_empirical_events=0,
        new_llm_processes=0,
        D11_D12_adjudicated=False,
        full_classical_conformance=False,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before-dir", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing audit")
    result = audit(args.before_dir)
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "literal_contexts",
                    "symbolic_contexts",
                    "legacy_comparison",
                    "engineering_checks_passed",
                    "goal_complete",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
