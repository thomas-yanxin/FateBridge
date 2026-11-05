"""Freeze engine-informed inputs before reading new official chart outputs.

This selects all64 Personality Sun gates at each of three cross angles, plus
the first quadruple definition in a declared daily scan. It supplies no expected
official values and cannot authenticate charts or estimate population frequency.
"""

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.ephemeris_runtime import configure_ephemeris_path
from fatebridge.core.human_design import chart_at
from fatebridge.core.human_design_mechanics import GATE_ORDER
from fatebridge.core.human_design_time import sun_at_tt

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def freeze_case(identifier, utc, chart, tags):
    local = utc.astimezone(ZoneInfo("Europe/London"))
    return {
        "id": identifier,
        "birth_input": {
            "birth_year": local.year,
            "birth_month": local.month,
            "birth_day": local.day,
            "birth_hour": local.hour,
            "birth_minute": local.minute,
            "birth_timezone": "Europe/London",
        },
        "engine_utc": utc.isoformat(),
        "selection_tags_from_engine": tags,
        "engine_diagnostic_not_official_expected_values": {
            "cross": chart["incarnation_cross"],
            "profile": chart["profile"],
            "definition": chart["bodygraph"]["definition"]["kind"],
        },
    }


def plan():
    configure_ephemeris_path()
    start = ephemeris_time(datetime(1980, 1, 1, tzinfo=timezone.utc)).jd_tt
    assert start is not None
    days = [(start + i, sun_at_tt(start + i, True)) for i in range(368)]
    cases = []
    # Fixed interior offsets. The narrow4/1 interval is not found by searching
    # official output or moved after seeing a failed official chart.
    for angle, offset in (("right", 1.5), ("juxtaposition", 3.6875), ("left", 4.5)):
        for gate in range(1, 65):
            target = (302 + GATE_ORDER.index(gate) * 5.625 + offset) % 360
            brackets = [
                (a[0], b[0])
                for a, b in zip(days, days[1:])
                if 0 <= (target - a[1]) % 360 < (b[1] - a[1]) % 360
            ]
            assert brackets, (gate, angle)
            lo, hi = brackets[0]
            for _ in range(35):
                mid = (lo + hi) / 2
                if (sun_at_tt(mid, True) - target + 180) % 360 - 180 < 0:
                    lo = mid
                else:
                    hi = mid
            utc = datetime_from_tt((lo + hi) / 2)
            utc = (utc + timedelta(seconds=30)).replace(second=0, microsecond=0)
            chart = chart_at(utc, require_swiss_files=True)
            assert chart["incarnation_cross"]["gates"][0] == gate
            assert chart["incarnation_cross"]["angle"] == angle
            cases.append(
                freeze_case(
                    f"cross-{angle}-{gate:02}", utc, chart, [f"cross:{angle}:{gate}"]
                )
            )
    scan = []
    first_quadruple = None
    for day in range(14610):
        utc = datetime(1980, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=day)
        chart = chart_at(utc, require_swiss_files=True)
        kind = chart["bodygraph"]["definition"]["kind"]
        scan.append([utc.isoformat(), kind])
        if kind == "quadruple_split":
            first_quadruple = freeze_case(
                "first-quadruple-" + utc.date().isoformat(),
                utc,
                chart,
                ["definition:quadruple_split"],
            )
            cases.append(first_quadruple)
            break
    return {
        "method_id": "human_design_pre_official_cross_coverage_plan_v1",
        "declared_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": "https://jovianarchive.com/pages/get-your-human-design-chart",
        "city": "London, United Kingdom",
        "selection_scope": "Engine-informed, not blind. All192 gate/angle inputs fixed before any new official outputs; earlier19 observations remain separate unchanged cohorts. First quadruple case is selected by the retained ordered daily scan. Preserve failures and missing strata; do not substitute easier cases.",
        "ordered_angle_offsets_degrees": [
            ["right", 1.5],
            ["juxtaposition", 3.6875],
            ["left", 4.5],
        ],
        "quadruple_scan": {
            "start_utc": "1980-01-01T12:00:00+00:00",
            "step_days": 1,
            "maximum_samples": 14610,
            "samples_checked": len(scan),
            "ordered_kind_observations": scan,
            "observations_sha256": digest(scan),
            "first_case_found": first_quadruple is not None,
        },
        "targets": [
            f"cross:{a}:{g}"
            for a in ("right", "juxtaposition", "left")
            for g in range(1, 65)
        ]
        + ["definition:quadruple_split"],
        "cases": cases,
        "source_bindings": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in (
                "src/fatebridge/core/human_design.py",
                "src/fatebridge/core/human_design_time.py",
                "src/fatebridge/data/human_design/rave-2001-depth.json",
                "scripts/plan_human_design_cross_coverage.py",
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing observation plan")
    value = plan()
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cases": len(value["cases"]),
                "quadruple_samples_checked": value["quadruple_scan"]["samples_checked"],
                "quadruple_found": value["quadruple_scan"]["first_case_found"],
                "path": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
