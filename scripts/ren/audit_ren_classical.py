"""Audit frozen Liu Ren / Jin Kou excerpts, keeping unresolved readings visible.

The default exit status checks the selected engineering/reference comparisons.
--require-full-conformance also requires the entire classical and efficacy claim;
that gate intentionally remains closed. The selected manifest is pinned;
that local identity check cannot certify an ancient edition or authenticate
a replacement of both this script and its declared reference identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/ren_classical_v1"
REFERENCE_FREEZE_SHA256 = (
    "43b09232c0f7ed717a59daf25a632e2d3510778104b9df08e19d10da4c026d11"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_corpus(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != REFERENCE_FREEZE_SHA256:
        raise ValueError("Reference manifest identity changed")
    frozen = json.loads((corpus / "freeze.json").read_text(encoding="utf-8"))
    expected = {"cases.json", "rules.json", "calendar.json"}
    if set(frozen["files"]) != expected or {
        p.name for p in corpus.glob("*.json")
    } != expected | {"freeze.json"}:
        raise ValueError("Reference file set changed")
    for name, checksum in frozen["files"].items():
        if sha(corpus / name) != checksum:
            raise ValueError(f"Reference changed after freeze: {name}")
    if (
        sha(ROOT / "tests/fixtures/liureng_transmissions_reference.json")
        != frozen["software_oracle_sha256"]
    ):
        raise ValueError("Reference software oracle changed after freeze")
    data = {
        Path(name).stem: json.loads((corpus / name).read_text(encoding="utf-8"))
        for name in expected
    }
    if (
        len(data["cases"]["cases"]) != 5
        or len(data["cases"]["unresolved"]) != 2
        or len(data["calendar"]["cases"]) != 12
    ):
        raise ValueError("Reference coverage changed")
    return data


def make_seed(case: dict[str, Any]):
    from fatebridge.core.metaphysics.common import MetaphysicsSeed

    # Explicit symbolic inputs from a book; this is not an invented civil date.
    instant = datetime(2026, 1, 1, 12)
    return MetaphysicsSeed(
        input_datetime=instant,
        corrected_datetime=instant,
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={
            "year": ("丙", "午"),
            "month": ("甲", case.get("month", "寅")),
            "day": tuple(case["day"]),
            "hour": ("甲", case["hour"]),
        },
        calendar_context={"current_solar_term": {"name": "冬至"}},
    )


def observe_jinkou(case: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board

    return build_jinkou_board(
        make_seed(case),
        {"month_general": {"branch": case["general"]}},
        di_fen=case["ground"],
    )


def audit() -> dict[str, Any]:
    data = load_frozen_corpus()
    # Import production only after verifying the independent labels.
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.metaphysics.common import status_against_anchor
    from fatebridge.core.metaphysics.jinkou import (
        GUISHEN_IDENTITIES,
        _build_guishen_mapping,
        _jinkou_pick_use_position,
    )
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.services.metaphysics import _build_analysis_seed

    checks = []

    def check(key, actual, expected):
        checks.append(
            {
                "id": key,
                "actual": actual,
                "expected": expected,
                "matched": actual == expected,
            }
        )

    for case in data["cases"]["cases"]:
        board = observe_jinkou(case)
        actual = {
            "positions": [r["content"] for r in board["rows"]],
            "elements": [r["element"] for r in board["rows"]],
            "god": board["overview"]["guishen"]["name"],
        }
        check(case["id"], actual, case["expected"])
    rules = data["rules"]
    check("inherent_gods", GUISHEN_IDENTITIES, rules["inherent"])
    for row in rules["guiren"]:
        for scope, hour in (("day", "午"), ("night", "子")):
            check(
                f"guiren.{row['stem']}.{scope}",
                _build_guishen_mapping(row["stem"], hour)[0],
                row[scope],
            )
    for anchor, targets in rules["power"].items():
        for target, value in targets.items():
            check(
                f"power.{anchor}.{target}", status_against_anchor(anchor, target), value
            )
    for index, row in enumerate(rules["polarity_use"]):
        rows = [
            {"label": label, "polarity": polarity}
            for label, polarity in zip(("人元", "贵神", "将神", "地分"), row["mask"])
        ]
        check(f"polarity.{index}", _jinkou_pick_use_position(rows)[0], row["use"])
    for day, value in rules["empty"].items():
        board = observe_jinkou(
            {"day": day, "hour": "午", "general": "戌", "ground": "申"}
        )
        check(f"empty.{day}", board["overview"]["si_da_kong"], value)

    oracle = json.loads(
        (ROOT / "tests/fixtures/liureng_transmissions_reference.json").read_text(
            encoding="utf-8"
        )
    )
    failures = []
    branches = "子丑寅卯辰巳午未申酉戌亥"
    for row in oracle["cases"]:
        seed = make_seed({"day": row["day"], "hour": "子"})
        board = build_liureng_board(
            seed, month_general_override=branches[row["offset"]]
        )
        actual = [
            board["three_transmissions"][k]["branch"]
            for k in ("initial", "middle", "final")
        ]
        if actual != row["transmissions"]:
            failures.append(
                {
                    "day": row["day"],
                    "offset": row["offset"],
                    "actual": actual,
                    "expected": row["transmissions"],
                }
            )

    terms = {t.name: t for t in get_solar_terms_for_year(2026, "Asia/Shanghai")}
    calendar = []
    for row in data["calendar"]["cases"]:
        published = datetime.fromisoformat(row["at"])
        actual = terms[row["term"]]
        error = abs((actual.moment - published).total_seconds())
        # Published instants are rounded minutes; use +/-2m to avoid rounding
        # ambiguity and choose a far-east longitude that shifts the solar clock.
        generals = []
        for shift in (-2, 2):
            dt = published + timedelta(minutes=shift)
            seed = _build_analysis_seed(
                analysis_year=dt.year,
                analysis_month=dt.month,
                analysis_day=dt.day,
                analysis_hour=dt.hour,
                analysis_minute=dt.minute,
                analysis_timezone="Asia/Shanghai",
                analysis_longitude=135,
                use_true_solar_time=True,
            )
            generals.append(build_liureng_board(seed)["month_general"]["branch"])
        new_index = branches.index(row["general"])
        expected = [branches[(new_index + 1) % 12], row["general"]]
        calendar.append(
            {
                "term": row["term"],
                "error_seconds": round(error, 3),
                "provider": actual.resolution_provider,
                "generals": generals,
                "expected": expected,
                "matched": error <= data["calendar"]["tolerance_seconds"]
                and generals == expected,
            }
        )

    unresolved = list(data["cases"]["unresolved"])
    unresolved[0] = {
        **unresolved[0],
        "observed_god": observe_jinkou(unresolved[0])["overview"]["guishen"]["name"],
    }
    selected_passed = (
        all(c["matched"] for c in checks + calendar)
        and len(oracle["cases"]) == 720
        and not failures
    )
    return {
        "scope": "frozen selected excerpts, calendar instants and a versioned software oracle; no whole-book or efficacy certification",
        "provenance": {
            "reference_freeze_sha256": sha(CORPUS / "freeze.json"),
            "implementation_files": {
                name: sha(ROOT / name)
                for name in (
                    "src/fatebridge/core/metaphysics/common.py",
                    "src/fatebridge/core/metaphysics/jinkou.py",
                    "src/fatebridge/core/metaphysics/liureng.py",
                    "src/fatebridge/core/metaphysics/liureng_transmissions.py",
                    "src/fatebridge/core/metaphysics/ren_evidence.py",
                    "src/fatebridge/services/metaphysics.py",
                    "src/fatebridge/core/almanac.py",
                    "src/fatebridge/core/calendar.py",
                )
            },
        },
        "selected_checks_passed": selected_passed,
        "source_cases": {"compared": 5, "unresolved_readings": len(unresolved)},
        "checks": checks,
        "calendar": calendar,
        "software_oracle": {
            "case_count": len(oracle["cases"]),
            "failures": failures,
            "scope": "三传，不是原典全文认证",
        },
        "unresolved": unresolved,
        "four_axes": {
            "calendar": "selected_2026_major_terms_only",
            "classical": "partial_excerpt_with_unresolved_readings",
            "interpretation": "structured_rule_trace_only; free_text_not_validated",
            "real_world_prediction": "not_tested",
        },
        "classical_acceptance_passed": False,
        "authority_certified": False,
        "universal_perfect_prediction_established": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-conformance", action="store_true")
    args = parser.parse_args()
    report = audit()
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "selected_checks_passed",
                    "source_cases",
                    "four_axes",
                    "classical_acceptance_passed",
                    "authority_certified",
                )
            },
            ensure_ascii=False,
        )
    )
    return (
        0
        if report["selected_checks_passed"] and not args.require_full_conformance
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
