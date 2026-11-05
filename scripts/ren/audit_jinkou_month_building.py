"""Primary 神将建旺 scope, independent branch contrasts and complete reporting."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_month_building_v1"
PIN = "351103d5244364bb5cff6895f3525566a9a7a8beb04c042462e31afd59cdbf71"


def reference() -> dict[str, Any]:
    if hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() != PIN:
        raise ValueError("Frozen month-building manifest changed")
    manifest = json.loads((CORPUS / "freeze.json").read_text())
    if {p.name for p in CORPUS.iterdir()} != set(manifest) | {"freeze.json"}:
        raise ValueError("Frozen month-building inventory changed")
    for name, digest in manifest.items():
        if hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen month-building source changed")
    return json.loads((CORPUS / "reference.json").read_text())


def synthetic_rows(god: str, general: str) -> list[dict[str, str]]:
    from fatebridge.core.metaphysics.common import branch_element_text

    return [
        dict(label="人元", content="甲", element="木"),
        dict(label="贵神", content=god, element=branch_element_text(god)),
        dict(label="将神", content=general, element=branch_element_text(general)),
        dict(label="地分", content="子", element="水"),
    ]


def corrupt(body: dict[str, Any], fault: str, annual: bool = False) -> dict[str, Any]:
    result = copy.deepcopy(body)
    board = result["jinkou"]
    if annual:
        board = board["year_fate"]["course"]
    qi = board["qi_evidence"]
    checks = qi["month_building_checks"]
    if fault in ("wrong_god_result", "wrong_general_result"):
        row = checks[0 if fault == "wrong_god_result" else 1]
        row["matched"] = not row["matched"]
    elif fault in ("substitute_ground", "substitute_month_general"):
        target = board["overview"][
            "di_fen" if fault == "substitute_ground" else "month_general"
        ]
        if isinstance(target, dict):
            target = target["branch"]
        checks[0]["branch"] = target
        # Force a distinct wrong anchor even if this particular board coincides.
        if target == board["rows"][1]["content"]:
            checks[0]["branch"] = "丑" if target != "丑" else "寅"
        checks[0]["matched"] = checks[0]["branch"] == qi["month_building_branch"]
    elif fault == "duplicate_position":
        checks[1] = copy.deepcopy(checks[0])
    elif fault == "drop_god":
        checks.pop(0)
    elif fault == "missing_layer":
        del qi["month_building_checks"]
    elif fault == "null_layer":
        qi["month_building_checks"] = None
    elif fault == "wrong_source":
        qi["month_building_scan_sha256"] = "0" * 64
    elif fault == "wrong_basis":
        qi["month_building_basis"] = "以落地位置当作贵神固有支；建旺就是全部用神已确定"
    elif fault == "trace_only_wrong_result":
        trace = next(
            t for t in board["rule_trace"] if t["rule_id"] == "jinkou.month_day_qi"
        )
        trace["result"] = copy.deepcopy(trace["result"])
        trace["result"]["month_building_checks"][0]["matched"] = not checks[0][
            "matched"
        ]
    else:
        raise ValueError(fault)
    return result


def audit() -> dict[str, Any]:
    ref = reference()
    from fatebridge.core.metaphysics.jinkou import GUISHEN_IDENTITIES
    from fatebridge.core.metaphysics.jinkou_qi import build_jinkou_qi
    from scripts.ren.audit_ren_classical import observe_jinkou

    observed = []
    for case in ref["symbolic_cases"]:
        board = observe_jinkou(case)
        checks = board["qi_evidence"].get("month_building_checks")
        matches = [c["matched"] for c in checks] if isinstance(checks, list) else None
        branches = [board["rows"][i]["content"] for i in (1, 2)]
        observed.append(
            dict(
                id=case["id"],
                actual_branches=branches,
                expected_branches=[case["expected_god"], case["expected_general"]],
                actual_matched=matches,
                expected_matched=case["expected_matched"],
                matched=matches == case["expected_matched"]
                and branches == [case["expected_god"], case["expected_general"]],
            )
        )
    failures = []
    evaluated = 0
    for month, god, general in itertools.product(ref["month_order"], repeat=3):
        qi = build_jinkou_qi(
            synthetic_rows(god, general), month_branch=month, day_branch="子"
        )
        expected = [god == month, general == month]
        checks = qi.get("month_building_checks")
        actual = [c["matched"] for c in checks] if isinstance(checks, list) else None
        evaluated += 1
        if actual != expected:
            failures.append(
                dict(
                    month=month,
                    god=god,
                    general=general,
                    expected=expected,
                    actual=actual,
                )
            )
    return dict(
        source_url=ref["source_url"],
        source_sha256=ref["source_sha256"],
        source_pages=ref["pdf_pages"],
        identities_match=GUISHEN_IDENTITIES == ref["god_identities"],
        symbolic_cases=observed,
        symbolic_case_count=len(observed),
        symbolic_matched_count=sum(c["matched"] for c in observed),
        triple_count=evaluated,
        position_comparison_count=evaluated * 2,
        failures=failures,
        failure_count=len(failures),
        god_advance_or_retreat_adjudicated=False,
        daily_five_states_adjudicated=False,
        comprehensive_use_adjudicated=False,
        independent_historical_or_reality_events=0,
        goal_complete=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
    raise SystemExit(
        0
        if report["identities_match"]
        and report["symbolic_matched_count"] == 4
        and not report["failures"]
        else 1
    )
