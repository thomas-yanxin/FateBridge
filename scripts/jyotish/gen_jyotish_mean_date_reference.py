"""Freeze independent Gregorian anchors and exact binary-input mean-date probes.

Run only in an isolated pyerfa2.0.1.5 reference environment. No FateBridge or
Swiss imports; the normal tests consume the frozen JSON and need no ERFA.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path


def main() -> None:
    import erfa
    import numpy as np

    assert importlib.metadata.version("pyerfa") == "2.0.1.5"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Frozen reference must use a new path")
    d0, dm = erfa.cal2jd(1, 1, 1)
    assert d0 == 2400000.5 and d0 + dm == 1721425.5
    # Exhaust the supported civil date range, in bounded vectors. These are
    # calendar days, never independent births, charts or observed events.
    digest = hashlib.sha256()
    total = date.max.toordinal()
    for first in range(1, total + 1, 8192):
        ordinals = list(range(first, min(first + 8192, total + 1)))
        dates = [date.fromordinal(i) for i in ordinals]
        base, mjd = erfa.cal2jd(
            [d.year for d in dates], [d.month for d in dates], [d.day for d in dates]
        )
        expected = np.asarray(ordinals, dtype=float) + 1721424.5
        actual = base + mjd
        assert np.array_equal(actual, expected), first
        for ordinal, jd in zip(ordinals, actual):
            digest.update(f"{ordinal}:{float(jd).hex()}\n".encode())
    # Input list fixed before any native comparison, including year/month
    # index transitions derived from the declared traditional epoch index.
    epoch = date(1860, 1, 1)
    target = date(2024, 1, 1)
    count = 714404108573 + (target - epoch).days
    year_boundary = target + timedelta(days=(-count) % 360)
    month_boundary = target + timedelta(days=(-count) % 30)
    targets = sorted(
        {
            1,
            2,
            date(1900, 1, 1).toordinal(),
            date(1918, 10, 16).toordinal(),
            date(1984, 6, 1).toordinal(),
            date(2000, 1, 1).toordinal(),
            date(2024, 3, 1).toordinal(),
            month_boundary.toordinal(),
            year_boundary.toordinal(),
            total,
            total + 1,
        }
    )
    longitudes = [
        -179.99,
        -122.4194,
        -77.0369,
        -0.1,
        0.0,
        45.0,
        77.5946,
        121.4737,
        179.99,
    ]
    probes = []
    for ordinal in targets:
        midnight = Fraction(2 * ordinal + 3442849, 2)
        for longitude in longitudes:
            centre = float(midnight - Fraction(longitude) / 360)
            for position, jd in [
                ("before", math.nextafter(centre, -math.inf)),
                ("nearest", centre),
                ("after", math.nextafter(centre, math.inf)),
            ]:
                # Reference classification uses local small residual to this
                # separately ERFA-verified midnight, not production's JD sum.
                residual = Fraction(jd) + Fraction(longitude) / 360 - midnight
                offset = residual.numerator // residual.denominator
                wanted_ordinal = ordinal + offset
                expected_date = (
                    date.fromordinal(wanted_ordinal).isoformat()
                    if 1 <= wanted_ordinal <= total
                    else None
                )
                probes.append(
                    dict(
                        target_midnight_ordinal=ordinal,
                        position=position,
                        jd_ut1=jd,
                        jd_hex=jd.hex(),
                        longitude=longitude,
                        longitude_hex=longitude.hex(),
                        exact_residual_days=str(residual),
                        expected_date=expected_date,
                        expected_ordinal=wanted_ordinal if expected_date else None,
                    )
                )
    assert not any(
        n == "fatebridge"
        or n.startswith("fatebridge.")
        or n in {"swisseph", "pyswisseph"}
        for n in sys.modules
    )
    result = dict(
        provenance=dict(
            software="pyerfa",
            version="2.0.1.5",
            erfa_version=erfa.version.erfa_version,
            erfa_ufunc_sha256=hashlib.sha256(
                Path(erfa.ufunc.__file__).read_bytes()
            ).hexdigest(),
            sources=[
                "https://raw.githubusercontent.com/liberfa/erfa/master/src/cal2jd.c",
                "https://docs.python.org/3.12/library/datetime.html#datetime.date.fromordinal",
            ],
            scope="Independent ERFA Gregorian-midnight anchors plus exact Fraction residual classification on the explicitly given binary floats. No FateBridge/Swiss, UTC inversion, observations or blind outcome data.",
        ),
        complete_supported_calendar_anchor_check=dict(
            days=total,
            first="0001-01-01",
            last="9999-12-31",
            all_midnights_exact=True,
            stream_sha256=digest.hexdigest(),
            julian_midnight_at_ordinal1="1721425.5",
        ),
        protocol=dict(
            longitudes=longitudes,
            midnight_ordinals=targets,
            neighbors=["before", "nearest", "after"],
            traditional_month_boundary=month_boundary.isoformat(),
            traditional_year_boundary=year_boundary.isoformat(),
            no_production_comparison_before_freeze=True,
        ),
        probes=probes,
        probe_count=len(probes),
        real_events=0,
        independent_model_blind_reviews=0,
        whole_goal_complete=False,
    )
    args.output.parent.mkdir(exist_ok=True, parents=True)
    with args.output.open("x") as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                calendar_midnights_checked=total,
                probes=len(probes),
                month_boundary=month_boundary.isoformat(),
                year_boundary=year_boundary.isoformat(),
                fixture_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
            )
        )
    )


if __name__ == "__main__":
    main()
