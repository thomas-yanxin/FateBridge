"""Audit frozen source-position observations, not whole-chart acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.bazi_evidence import build_natal_evidence

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/bazi_classical_routes_v1/reference.json"


def audit() -> dict[str, Any]:
    raw = REFERENCE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != REFERENCE.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen source-position reference changed")
    reference = json.loads(raw)
    rows = []
    for case in reference["cases"]:
        chart = dict(zip(("year", "month", "day", "hour"), map(tuple, case["pillars"])))
        graph = build_natal_evidence(chart)["classical_routes"]
        expected = case["expected"]
        checks = {
            "selected_month_god": graph["selected_month_role"]["ten_god"]
            == expected["month_god"]
        }
        if "edge" in expected:
            e = expected["edge"]
            route = next(r for r in graph["routes"] if r["id"] == e["route"])
            checks["required_edge"] = route["status"] == "observed_route" and any(
                (r["from_star"], r["to_star"], r["relation"])
                == (e["from"], e["to"], e["relation"])
                for r in route["edges"]
            )
            if "rooted_helper" in expected:
                checks["rooted_helper"] = (
                    expected["rooted_helper"]
                    in route["helper_root_context"]["with_hidden_root"]
                )
        for key, actual in (
            ("shared_root", "output_wealth_shared_roots"),
            ("separation", "wealth_seal_positions"),
        ):
            if key in expected:
                checks[key] = any(
                    all(row.get(k) == v for k, v in expected[key].items())
                    for row in graph[actual]
                )
        rows.append(
            {
                "id": case["id"],
                "source_pdf_pages": case["pages"],
                "checks": checks,
                "matched": all(checks.values()),
            }
        )
    return {
        "method_id": "ziping_position_observation_audit_v1",
        "reference_sha256": digest,
        "source_sha256": reference["source_sha256"],
        "annotation_origin": reference["annotation_origin"],
        "matched_cases": sum(r["matched"] for r in rows),
        "case_count": len(rows),
        "all_observations_matched": all(r["matched"] for r in rows),
        "cases": rows,
        "scope": reference["scope"],
        "whole_chart_strength_evaluated": False,
        "whole_chart_formation_evaluated": False,
        "source_fingerprints": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "src/fatebridge/core/classical_routes.py",
                "src/fatebridge/core/bazi_evidence.py",
            )
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Source observations: {result['matched_cases']}/{result['case_count']}")
    return 0 if result["all_observations_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
