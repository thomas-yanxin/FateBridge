"""Independent Decimal audit over fixed radii, with retained failure examples.

This engineering audit imports the test-only Decimal oracle; it does not fit
thresholds to any production result and does not certify empirical predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro.aspects import _match_cross_aspect
from fatebridge.core.classical_western import _aspect_is_applying, _aspect_phase
from tests.test_western_angular_predicates import (
    ANGLES,
    reference_match,
    reference_phase,
)


def audit():
    cases = []
    for _, angle in ANGLES:
        for radius in (0.0, 1.5, 3.0, 6.0, 8.0):
            for edge in (angle - radius, angle + radius):
                for point in (
                    math.nextafter(edge, -math.inf),
                    edge,
                    math.nextafter(edge, math.inf),
                ):
                    cases.extend(
                        (
                            (point, 0.0, radius),
                            (0.0, point, radius),
                            (point, 360.0, radius),
                            (360.0, point, radius),
                        )
                    )
    tiny = math.ulp(0.0)
    cases.extend(((tiny, -3.0, 3), (-tiny, 3.0, 3), (0.5000000000000001, 352.5, 8)))
    rng = random.Random(20261022)
    cases.extend(
        (rng.uniform(-720, 720), rng.uniform(-720, 720), rng.choice((0, 1.5, 3, 8)))
        for _ in range(1000)
    )
    failures = []
    count = 0
    for a, b, radius in cases:
        for pair in (None, ("Mercury", "Saturn"), ("Sun", "Mars")):
            expected = reference_match(a, b, radius, pair)
            actual = _match_cross_aspect(a, b, radius, *(pair or ()))
            count += 1
            if actual != expected:
                failures.append(
                    {
                        "input": [a, b, radius, pair],
                        "expected": expected,
                        "actual": actual,
                    }
                )
    phases = [
        (0.0, 13.0, 0.1, 0.0, 0.0),
        (0.0, -13.0, 359.9, 0.0, 0.0),
        (0.0, 0.0, 60.0, 1.0, 60.0),
        (0.0, 1.0, 59.0, 1.0, 60.0),
        (0.0, None, 59.0, 1.0, 60.0),
        (tiny, 0, 0, tiny, 0),
        (0, 1e308, 1, -1e308, 0),
    ]
    for _, angle in ANGLES:
        for point in (
            math.nextafter(float(angle), -math.inf),
            float(angle),
            math.nextafter(float(angle), math.inf),
        ):
            phases.extend(
                (0.0, va, point, vb, angle)
                for va, vb in ((13.0, 0.0), (-13.0, 0.0), (1.0, 1.0))
            )
    phases.extend(
        (
            rng.uniform(-720, 720),
            rng.uniform(-15, 15),
            rng.uniform(-720, 720),
            rng.uniform(-15, 15),
            angle,
        )
        for _, angle in ANGLES
        for _ in range(200)
    )
    phase_failures = []
    for a, va, b, vb, angle in phases:
        expected = reference_phase(a, va, b, vb, angle)
        for values in ((a, va, b, vb, angle), (b, vb, a, va, angle)):
            actual = _aspect_phase(*values)
            if actual != expected:
                phase_failures.append(
                    {"input": values, "expected": expected, "actual": actual}
                )
    paths = [
        "tests/fixtures/western-angular-predicates-protocol.json",
        "tests/test_western_angular_predicates.py",
        __file__,
        "src/fatebridge/core/astro/geometry.py",
        "src/fatebridge/core/astro/aspects.py",
        "src/fatebridge/core/astro/relationship_geometry.py",
        "src/fatebridge/core/classical_western.py",
        "src/fatebridge/core/predictive/_common.py",
        "docs/validation/western-modern-aspect-wrap-open.json",
    ]
    root = Path(__file__).resolve().parents[1]
    hashes = {
        str(Path(p).resolve().relative_to(root)): hashlib.sha256(
            Path(p).read_bytes()
        ).hexdigest()
        for p in paths
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "western_angular_predicates_decimal_v1",
        "coordinate_cases": len(cases),
        "aspect_comparisons": count,
        "aspect_failures": failures,
        "phase_cases": len(phases),
        "phase_comparisons_with_swaps": len(phases) * 2,
        "phase_failures": phase_failures,
        "retained_counterexamples": [
            {
                "input_longitudes": [0.5000000000000001, 352.5],
                "orb_limit": 8.0,
                "before": "conjunction orb=8.0",
                "now": _match_cross_aspect(0.5000000000000001, 352.5, 8),
                "historical_failure": "western-modern-aspect-wrap-open.json",
            },
            {
                "input_longitudes_and_speeds": [0, 13, 0.1, 0, 0],
                "before_72_minute_probe": False,
                "now_instantaneous": _aspect_is_applying(0, 13, 0.1, 0, 0),
                "reference_phase": reference_phase(0, 13, 0.1, 0, 0),
                "input_kind": "synthetic",
            },
        ],
        "source_sha256": hashes,
        "classification_tolerance": "No epsilon; existing float policy radii unchanged",
        "acceptance_scope": "Independent arithmetic over supplied doubles only; not observational precision, full Ptolemy I.24, source-specific light transfer or future event validity",
        "passed": not failures and not phase_failures,
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        f"Aspects {report['aspect_comparisons'] - len(report['aspect_failures'])}/{report['aspect_comparisons']}; phases {report['phase_comparisons_with_swaps'] - len(report['phase_failures'])}/{report['phase_comparisons_with_swaps']}"
    )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
