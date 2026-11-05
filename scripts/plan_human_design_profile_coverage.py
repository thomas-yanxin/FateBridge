"""Freeze all64 gates x12 profiles before collecting new public chart outputs.

This is an engine-informed selection plan, not independent ephemeris truth or
an observation. No official expected values are generated. Existing cohorts,
failures and acceptance requirements must remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.ephemeris_runtime import configure_ephemeris_path
from fatebridge.core.human_design import chart_at
from fatebridge.core.human_design_mechanics import GATE_ORDER
from fatebridge.core.human_design_time import sun_at_tt

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ORDER = (
    "1/3",
    "1/4",
    "2/4",
    "2/5",
    "3/5",
    "3/6",
    "4/6",
    "4/1",
    "5/1",
    "5/2",
    "6/2",
    "6/3",
)
PRESERVED = (
    "tests/fixtures/human-design-official-charts.json",
    "tests/fixtures/human-design-official-cross-charts.json",
    "tests/fixtures/human-design-cross-coverage-plan.json",
    "tests/fixtures/human-design-cross-coverage-observations.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile_intervals():
    """Rational gate offsets implied by six equal lines and the88degree arc.

    Widths alternate13/16 and1/8 degree. These are angular widths, not
    population frequencies, nor a ruling on the source's29.1/29.2 table.
    """
    start = Fraction(0)
    result = []
    for index, profile in enumerate(PROFILE_ORDER):
        end = start + (Fraction(13, 16) if index % 2 == 0 else Fraction(1, 8))
        midpoint = (start + end) / 2
        # The design position is88 degrees before Personality; modulo a
        # gate's45/8 degree width its offset is2 degrees ahead:
        # (-88) modulo (45/8) =2. The previous comment used the positive88
        # remainder29/8 instead; the calculation below was already correct.
        p_line = int(midpoint // Fraction(15, 16)) + 1
        d_line = int(((midpoint - 88) % Fraction(45, 8)) // Fraction(15, 16)) + 1
        assert profile == f"{p_line}/{d_line}"
        result.append(
            {
                "profile": profile,
                "start_inclusive_degrees": str(start),
                "end_exclusive_degrees": str(end),
                "midpoint_degrees": str(midpoint),
            }
        )
        start = end
    assert start == Fraction(45, 8)
    return result


def plan():
    preserved = {p: sha(ROOT / p) for p in PRESERVED}
    old_inputs = {
        json.dumps(c["birth_input"], sort_keys=True)
        for name in PRESERVED[:2]
        for c in json.loads((ROOT / name).read_text())["cases"]
    }
    configure_ephemeris_path()
    start = ephemeris_time(datetime(1981, 1, 1, tzinfo=timezone.utc)).jd_tt
    assert start is not None
    days = [(start + i, sun_at_tt(start + i, True)) for i in range(368)]
    intervals = profile_intervals()
    cases = []
    for gate in range(1, 65):
        for interval in intervals:
            profile = interval["profile"]
            target = float(
                (
                    Fraction(302)
                    + GATE_ORDER.index(gate) * Fraction(45, 8)
                    + Fraction(interval["midpoint_degrees"])
                )
                % 360
            )
            brackets = [
                (a[0], b[0])
                for a, b in zip(days, days[1:])
                if 0 <= (target - a[1]) % 360 < (b[1] - a[1]) % 360
            ]
            assert brackets, (gate, profile)
            lo, hi = brackets[0]
            for _ in range(35):
                mid = (lo + hi) / 2
                if (sun_at_tt(mid, True) - target + 180) % 360 - 180 < 0:
                    lo = mid
                else:
                    hi = mid
            utc = (datetime_from_tt((lo + hi) / 2) + timedelta(seconds=30)).replace(
                second=0, microsecond=0
            )
            chart = chart_at(utc, require_swiss_files=True)
            assert chart["incarnation_cross"]["gates"][0] == gate, (gate, profile)
            assert chart["profile"] == profile, (gate, profile, chart["profile"])
            local = utc.astimezone(ZoneInfo("Europe/London"))
            birth = {
                "birth_year": local.year,
                "birth_month": local.month,
                "birth_day": local.day,
                "birth_hour": local.hour,
                "birth_minute": local.minute,
                "birth_timezone": "Europe/London",
            }
            assert json.dumps(birth, sort_keys=True) not in old_inputs
            cases.append(
                {
                    "id": f"profile-{gate:02}-{profile.replace('/', '-')}",
                    "birth_input": birth,
                    "engine_utc": utc.isoformat(),
                    "selection_tags_from_engine": [
                        f"gate:{gate}",
                        f"profile:{profile}",
                    ],
                    "engine_diagnostic_not_official_expected_values": {
                        "personality_sun_gate": gate,
                        "profile": chart["profile"],
                        "angle": chart["incarnation_cross"]["angle"],
                    },
                }
            )
    assert len(cases) == len({c["engine_utc"] for c in cases}) == 768
    assert preserved == {p: sha(ROOT / p) for p in PRESERVED}
    return {
        "method_id": "human_design_pre_official_profile_coverage_plan_v1",
        "declared_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": "https://jovianarchive.com/pages/get-your-human-design-chart",
        "city": "London, United Kingdom",
        "selection_scope": "Engine-informed, not blind. All768 synthetic gate/profile inputs are fixed before reading new official results. Select the first annual solar bracket after1981-01-01UTC,35 bisections, then nearest UTC minute. Do not substitute cases after observing failures; missing rows remain missing. This is not a full ephemeris, line-prose, fixing, cycle-origin, source-authentication or prediction acceptance.",
        "profile_intervals_within_gate": intervals,
        "preserved_cohorts_sha256": preserved,
        "old_input_overlap_count": 0,
        "expected_new_official_values": None,
        "case_count": len(cases),
        "cases": cases,
        "source_bindings": {
            p: sha(ROOT / p)
            for p in (
                "scripts/plan_human_design_profile_coverage.py",
                "src/fatebridge/core/human_design.py",
                "src/fatebridge/core/human_design_time.py",
                "src/fatebridge/core/astro/time_scales.py",
                "src/fatebridge/data/human_design/rave-2001-depth.json",
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing plan")
    result = plan()
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "path": str(args.output),
                "cases": result["case_count"],
                "sha256": sha(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
