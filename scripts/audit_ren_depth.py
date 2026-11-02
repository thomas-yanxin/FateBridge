"""Second Ren audit: internal strength, noble profiles, text table and conflicts.

The default exit status covers the explicitly implemented excerpts. The
--require-source-conformance gate includes missing and conflicting source
claims; it cannot pass by treating duplicated rows as additional coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_depth_v2"
SCAN_CORPUS = ROOT / "tests/fixtures/ren_scan_collation_v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reference(corpus: Path = CORPUS) -> dict[str, Any]:
    frozen = json.loads((corpus / "freeze.json").read_text(encoding="utf-8"))
    expected = {"jinkou-internal.json", "tanyuan-rules.json", "tanyuan-table.json"}
    if set(frozen["files"]) != expected or {
        p.name for p in corpus.glob("*.json")
    } != expected | {"freeze.json"}:
        raise ValueError("Reference file set changed")
    for name, checksum in frozen["files"].items():
        if sha(corpus / name) != checksum:
            raise ValueError(f"Reference changed after freeze: {name}")
    return {
        Path(name).stem: json.loads((corpus / name).read_text(encoding="utf-8"))
        for name in expected
    }


def load_scan_reference(corpus: Path = SCAN_CORPUS) -> dict[str, Any]:
    frozen = json.loads((corpus / "freeze.json").read_text(encoding="utf-8"))
    expected = {"collation.json", "selected-pages.pdf"}
    if set(frozen["files"]) != expected or {
        p.name for p in corpus.iterdir() if p.is_file()
    } != expected | {"freeze.json"}:
        raise ValueError("Reference scan file set changed")
    for name, checksum in frozen["files"].items():
        if sha(corpus / name) != checksum:
            raise ValueError(f"Reference scan changed after freeze: {name}")
    data = json.loads((corpus / "collation.json").read_text(encoding="utf-8"))
    if len(data["missing_table_rows"]) != 8 or len(data["fuyin_table_rows"]) != 3:
        raise ValueError("Reference scan coverage changed")
    return data


def audit() -> dict[str, Any]:
    data = load_reference()
    scan = load_scan_reference()
    # Load production only after checking source labels. Reuse the symbolic
    # seed builder; no civil date is inferred from a book's symbolic example.
    spec = importlib.util.spec_from_file_location(
        "ren_v1", ROOT / "scripts/audit_ren_classical.py"
    )
    assert spec and spec.loader
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    from fatebridge.core.metaphysics.jinkou_strength import internal_strength
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.ren_gods import noble_start

    checks: list[dict[str, Any]] = []

    def check(key, actual, expected):
        checks.append(
            dict(id=key, actual=actual, expected=expected, matched=actual == expected)
        )

    for case in data["jinkou-internal"]["cases"]:
        rows = [
            dict(label=label, element=element)
            for label, element in zip(
                data["jinkou-internal"]["positions"], case["elements"]
            )
        ]
        strength = internal_strength(rows)
        check(
            f"internal.{case['god']}",
            [strength["anchor_element"], strength["powers"]["贵神"]],
            [case["anchor"], case["god_power"]],
        )

    rules = data["tanyuan-rules"]
    for case in rules["noble_starts"]:
        for scope in ("day", "night"):
            check(
                f"noble.{case['stem']}.{scope}",
                noble_start(case["stem"], scope == "day", "tanyuan_xieji_v1"),
                case[scope],
            )
    for case in rules["noble_examples"]:
        board = build_liureng_board(
            prior.make_seed(case),
            month_general_override=case["general"],
            guiren_profile="tanyuan_xieji_v1",
        )
        noble = next(row for row in board["twelve_board"] if row["god"] == "贵人")
        check(
            f"noble.example.{case['day']}",
            [noble["sky_branch"], noble["earth_branch"], board["guiren_order"]],
            [case["start"], case["earth"], case["order"]],
        )

    branches = "子丑寅卯辰巳午未申酉戌亥"
    # 十干寄宫 transcribed coordinates; do not import the production table
    # to construct expected transmission labels or source keys.
    houses = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅辰巳未巳未申戌亥丑"))

    def observe(case):
        offset = (
            branches.index(case["gan_upper"]) - branches.index(houses[case["day"][0]])
        ) % 12
        board = build_liureng_board(
            prior.make_seed({"day": case["day"], "hour": "子"}),
            month_general_override=branches[offset],
        )
        return board, [
            board["three_transmissions"][key]["branch"]
            for key in ("initial", "middle", "final")
        ]

    for case in rules["equal_harm_cases"]:
        board, actual = observe(case)
        check(
            f"harm_tie.{case['day']}.{case['gan_upper']}",
            [actual, board["board_style_detail"]],
            [case["transmissions"], case["detail"]],
        )

    table = data["tanyuan-table"]
    rows = table["cases"]
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    counts = Counter((c["day"], c["gan_upper"]) for c in rows)
    duplicate_conflicts = []
    for row in rows:
        key = row["day"], row["gan_upper"]
        if key in unique and unique[key]["transmissions"] != row["transmissions"]:
            duplicate_conflicts.append(
                dict(key=list(key), first=unique[key], other=row)
            )
        unique.setdefault(key, row)
    failures = []
    for row in unique.values():
        _, actual = observe(row)
        if actual != row["transmissions"]:
            failures.append({**row, "actual": actual})
    # Full sixty-day space from arithmetic, independent of source coverage.
    days = ["甲乙丙丁戊己庚辛壬癸"[i % 10] + branches[i % 12] for i in range(60)]
    missing = [
        dict(day=day, gan_upper=branch)
        for day in days
        for branch in branches
        if (day, branch) not in unique
    ]
    if missing != table["known_missing"]:
        raise ValueError("Reference missing-board inventory changed")
    combined = dict(unique)
    scan_checks = []
    for row in scan["missing_table_rows"]:
        key = row["day"], row["gan_upper"]
        if key in combined:
            raise ValueError(
                "Reference scan supplements must not replace existing rows"
            )
        combined[key] = row
        _, actual = observe(row)
        scan_checks.append(
            {**row, "actual": actual, "matched": actual == row["transmissions"]}
        )
    for row in scan["fuyin_table_rows"]:
        _, actual = observe(row)
        scan_checks.append(
            {**row, "actual": actual, "matched": actual == row["transmissions"]}
        )
        if (
            row["transmissions"]
            != combined[(row["day"], row["gan_upper"])]["transmissions"]
        ):
            raise ValueError("Reference scan and retained text-table labels conflict")
    combined_failures = []
    for row in combined.values():
        _, actual = observe(row)
        if actual != row["transmissions"]:
            combined_failures.append({**row, "actual": actual})
    preamble = []
    for row in rules["conflicting_preamble"]:
        _, actual = observe(row)
        tabular = unique.get((row["day"], row["gan_upper"]))
        preamble.append(
            {
                **row,
                "actual": actual,
                "table_value": tabular["transmissions"] if tabular else None,
                "scan_table_value": next(
                    c["transmissions"]
                    for c in scan["fuyin_table_rows"]
                    if c["day"] == row["day"]
                ),
                "scan_preamble_value": scan["preamble"]["transmissions"],
                "matched": actual == row["transmissions"],
            }
        )
    passed = (
        len(checks) == 39
        and all(c["matched"] for c in checks)
        and len(rows) == 720
        and len(unique) == 712
        and not failures
        and not duplicate_conflicts
        and len(combined) == 720
        and not combined_failures
        and all(c["matched"] for c in scan_checks)
    )
    return {
        "implemented_excerpt_checks_passed": passed,
        "checks": checks,
        "transcribed_table": {
            "source": table["source"],
            "printed_rows": len(rows),
            "unique_compared": len(unique),
            "matched": len(unique) - len(failures),
            "missing_count": len(missing),
            "missing": missing,
            "duplicate_keys": [list(k) for k, count in counts.items() if count > 1],
            "duplicate_conflicts": duplicate_conflicts,
            "failures": failures,
            "coverage_scope": "三传支序；不含完整课名、底本认证或全书论断",
            "second_host_is_independent_edition": False,
        },
        "unresolved_preamble_comparisons": preamble,
        "combined_table": {
            "unique_compared": len(combined),
            "matched": len(combined) - len(combined_failures),
            "failures": combined_failures,
            "text_transcribed": len(unique),
            "scan_supplements": len(scan["missing_table_rows"]),
            "missing_count": 720 - len(combined),
            "all_720_rows_visually_collated": False,
            "scope": "712 retained transcription labels plus 8 directly transcribed scan rows; branch sequence only",
        },
        "selected_scan_checks": scan_checks,
        "scan_source": {
            k: scan[k]
            for k in (
                "source_url",
                "original_sha256",
                "original_page_count",
                "selected_original_pages_1based",
                "scope",
            )
        },
        "retained_transcription_issues": rules["issues"],
        "resolved_source_issues": [
            "Eight missing transcription labels supplemented by separately frozen visual scan evidence; original defective rows preserved."
        ],
        "unresolved_source_issues": rules["issues"][1:],
        "all_source_assertions_matched": len(combined) == 720
        and not combined_failures
        and not duplicate_conflicts
        and all(c["matched"] for c in preamble),
        "classical_acceptance_passed": False,
        "authority_certified": False,
        "real_world_prediction": "not_tested",
        "interpretation_scope": "structured derivation; unrestricted free text not validated",
        "provenance": {
            "reference_freeze_sha256": sha(CORPUS / "freeze.json"),
            "scan_reference_freeze_sha256": sha(SCAN_CORPUS / "freeze.json"),
            "implementation_files": {
                name: sha(ROOT / name)
                for name in (
                    "src/fatebridge/core/metaphysics/jinkou.py",
                    "src/fatebridge/core/metaphysics/jinkou_strength.py",
                    "src/fatebridge/core/metaphysics/ren_gods.py",
                    "src/fatebridge/core/metaphysics/ren_evidence.py",
                    "src/fatebridge/core/metaphysics/liureng.py",
                    "src/fatebridge/core/metaphysics/liureng_transmissions.py",
                    "src/fatebridge/core/output_chinese.py",
                    "src/fatebridge/core/requests/metaphysics.py",
                    "src/fatebridge/services/metaphysics.py",
                )
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-source-conformance", action="store_true")
    args = parser.parse_args()
    report = audit()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "implemented_excerpt_checks_passed": report[
                    "implemented_excerpt_checks_passed"
                ],
                "unique_table_comparisons": report["transcribed_table"][
                    "unique_compared"
                ],
                "transcription_missing": report["transcribed_table"]["missing_count"],
                "combined_missing": report["combined_table"]["missing_count"],
                "combined_unique_table_comparisons": report["combined_table"][
                    "unique_compared"
                ],
                "all_source_assertions_matched": report[
                    "all_source_assertions_matched"
                ],
                "real_world_prediction": report["real_world_prediction"],
            },
            ensure_ascii=False,
        )
    )
    return (
        0
        if report["implemented_excerpt_checks_passed"]
        and (
            not args.require_source_conformance
            or report["all_source_assertions_matched"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
