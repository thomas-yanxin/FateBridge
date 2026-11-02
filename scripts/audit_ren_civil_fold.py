"""Primary minute/clock probes for explicit Ren fold resolution.

Printed minute anchors, timezone bytes and expected symbolic boundaries are
frozen before production changes. Aliases/probes are not new event samples.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_civil_fold_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/calendar.py",
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/utils/civil_clock.py",
    "src/fatebridge/utils/timezones.py",
    "src/fatebridge/core/metaphysics/ren_calendar.py",
    "src/fatebridge/core/requests/metaphysics.py",
    "src/fatebridge/core/output_ren_clock.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/audit_ren_civil_fold.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(manifest["files"]) | {"freeze.json"}:
        raise ValueError("Frozen fold inventory changed")
    for name, expected in manifest["files"].items():
        if sha(corpus / name) != expected:
            raise ValueError(f"Frozen fold reference changed: {name}")
    ref: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    for name, expected in ref["references"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Referenced primary source changed: {name}")
    return ref


def payload(case: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    wall = datetime.fromisoformat(case["wall"])
    return dict(
        analysis_year=wall.year,
        analysis_month=wall.month,
        analysis_day=wall.day,
        analysis_hour=wall.hour,
        analysis_minute=wall.minute,
        analysis_second=wall.second,
        analysis_timezone=case["zone"],
        analysis_utc_offset=probe["offset"],
        use_true_solar_time=False,
    )


def audit() -> dict[str, Any]:
    ref = reference()
    calendar_policy = json.loads(
        (ROOT / "tests/fixtures/ren_calendar_v1/reference.json").read_text()
    )
    havana_general = calendar_policy["general_starts"]["霜降"]
    before = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    from fatebridge.core.calendar import BaZiCalendar
    from fatebridge.services.metaphysics import (
        calculate_jinkou_analysis,
        calculate_liureng_gods,
        calculate_liureng_runyear,
    )
    from fatebridge.utils.birth_input import create_person_info

    # Fictional integration subject; birth/age accuracy is outside this audit.
    person = create_person_info(
        birth_year=1910,
        birth_month=1,
        birth_day=15,
        birth_hour=10,
        birth_timezone="Asia/Shanghai",
        gender="女",
        use_true_solar_time=False,
    )
    functions = {
        "liureng_gods": calculate_liureng_gods,
        "liureng_runyear": lambda **kw: calculate_liureng_runyear(person, **kw),
        "jinkou": lambda **kw: calculate_jinkou_analysis(di_fen="子", **kw),
    }
    comparisons = []
    cases = [ref["havana_cache_case"], *ref["middle_term_fold_cases"]]
    for tool, function in functions.items():
        for case in cases:
            orders = ((0, 1), (1, 0)) if case["id"] == "H01" else ((0, 1),)
            for order in orders:
                BaZiCalendar._get_four_pillars_cached.cache_clear()
                for index in order:
                    probe = case["probes"][index]
                    result = function(**payload(case, probe))
                    base = dict(
                        case=case["id"],
                        tool=tool,
                        order=list(order),
                        offset=probe["offset"],
                    )
                    if "error" in result:
                        comparisons.append(
                            dict(
                                **base,
                                status="calculation_error",
                                matched=None,
                                error=result,
                            )
                        )
                        continue
                    board = result["jinkou" if tool == "jinkou" else "liureng"]
                    resolution = board["calendar_policy"]["civil_clock_resolution"]
                    expected_tzif = sha(
                        CORPUS / (case["zone"].replace("/", "_") + ".tzif")
                    )
                    matched = (
                        resolution["instant_utc"] == probe["instant_utc"]
                        and resolution["fold"] == probe["fold"]
                        and resolution["resolved_utc_offset"] == probe["offset"]
                        and resolution["was_ambiguous"] is True
                        and resolution["timezone_rules"]["tzif_sha256"] == expected_tzif
                    )
                    general = (
                        board["overview"]["month_general"]
                        if tool == "jinkou"
                        else board["month_general"]
                    )
                    if case["id"] == "H01":
                        month = result["four_pillars"]["month"]
                        actual = [month["stem"], month["branch"]]
                        matched = (
                            matched
                            and actual == probe["month_pillar"]
                            and general["branch"] == havana_general
                        )
                        target = probe["month_pillar"]
                    else:
                        actual = general["branch"]
                        target = probe["month_general"]
                        matched = matched and actual == target
                    comparisons.append(
                        dict(
                            **base,
                            status="compared",
                            expected=target,
                            actual=actual,
                            actual_month_general=general["branch"],
                            clock_resolution=resolution,
                            matched=matched,
                        )
                    )
    unchanged = before == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    return {
        "audit_id": "ren_civil_fold_v1",
        "comparisons": comparisons,
        "comparison_count": len(comparisons),
        "matched_count": sum(c["matched"] is True for c in comparisons),
        "failures": [c for c in comparisons if c["matched"] is not True],
        "unique_astronomical_minute_count": 5,
        "new_independent_astronomical_observations": 0,
        "middle_term_zone_projection_count": 7,
        "source_minute_edge_uncertainty": ["F04"],
        "implementation_sha256": before,
        "implementation_unchanged_during_audit": unchanged,
        "reference_sha256": sha(CORPUS / "freeze.json"),
        "selected_clock_checks_passed": unchanged
        and all(c["matched"] is True for c in comparisons),
        "full_supported_calendar_domain_certified": False,
        "classical_acceptance_passed": False,
        "goal_complete": False,
        "scope": ref["enumeration_scope"],
        "limits": ref["limits"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "comparison_count",
                    "matched_count",
                    "selected_clock_checks_passed",
                )
            }
        )
    )
    return 0 if report["selected_clock_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
