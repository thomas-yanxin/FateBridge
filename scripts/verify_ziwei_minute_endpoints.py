"""Post-build endpoint probes against adjacent, already frozen JPL instants.

These are subsets of the 449-point corpus, not additional independent data.
The later JPL reference is one microsecond after the hypothetical endpoint;
the original five-second comparison threshold is retained explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--wheel-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, installed = args.source_root.resolve(), args.wheel_root.resolve()
    sys.path.insert(0, str(source))
    sys.path.insert(0, str(installed))
    import fatebridge
    from fatebridge.services.metaphysics import calculate_ziwei_birth
    from fatebridge.utils.birth_input import create_person_info
    from scripts.audit_ziwei_solar_clock import load_reference

    if not Path(fatebridge.__file__).resolve().is_relative_to(installed):
        raise ValueError("Probe did not import the selected wheel")
    protocol, rows = load_reference(source / "tests/fixtures/ziwei_solar_jpl_v1")
    refs = {(r["site"]["id"], r["instant"]): r for r in rows}
    probes: list[dict[str, Any]] = []
    cases: tuple[tuple[str, str, dict[str, Any]], ...] = (
        (
            "zero",
            "2024-12-06T00:51:00+00:00",
            dict(
                birth_year=2024,
                birth_month=12,
                birth_day=6,
                birth_hour=0,
                birth_minute=51,
                birth_timezone="UTC",
                birth_longitude=0,
            ),
        ),
        (
            "cny_east150",
            "1984-02-01T14:13:00+00:00",
            dict(
                birth_year=1984,
                birth_month=2,
                birth_day=1,
                birth_hour=22,
                birth_minute=13,
                birth_timezone="Asia/Shanghai",
                birth_longitude=150,
            ),
        ),
    )
    for site, moment, inputs in cases:
        instant = datetime.fromisoformat(moment).astimezone(timezone.utc)
        first, later = [
            refs[(site, instant + timedelta(seconds=offset))] for offset in (0, 60)
        ]
        expected = [r["reference_label"] for r in (first, later)]
        branches = [
            "子丑寅卯辰巳午未申酉戌亥"[((d.hour + 1) // 2) % 12] for d in expected
        ]
        for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
            result = calculate_ziwei_birth(
                create_person_info(**inputs, gender="男", use_true_solar_time=True),
                rule_profile=profile,
            )
            sensitivity = result["ziwei_birth"]["calendar_basis"]["time_input"][
                "minute_sensitivity"
            ]
            actual = [
                datetime.fromisoformat(d)
                for d in sensitivity["endpoint_placement_datetimes"]
            ]
            errors = [(a - b).total_seconds() for a, b in zip(actual, expected)]
            checks = dict(
                clocks_within_original_tolerance=all(
                    abs(v) <= protocol["tolerance_seconds"] for v in errors
                ),
                hour_branches_match_adjacent_references=sensitivity[
                    "endpoint_hour_branches"
                ]
                == branches,
                dates_match_adjacent_references=[d.date() for d in actual]
                == [d.date() for d in expected],
                base_chart_kept=result["ziwei_birth"]["hour_branch"] == branches[0],
                hypothetical_not_birth_facts=sensitivity[
                    "endpoints_are_alternative_birth_facts"
                ]
                is False,
            )
            probes.append(
                dict(
                    site=site,
                    instant=moment,
                    profile=profile,
                    expected_adjacent_solar_labels=[d.isoformat() for d in expected],
                    actual_endpoint_labels=[d.isoformat() for d in actual],
                    endpoint_minus_reference_seconds=errors,
                    checks=checks,
                )
            )
    result = dict(
        method_id="ziwei_minute_endpoint_adjacent_jpl_probes_v1",
        actual_import=str(Path(fatebridge.__file__).resolve()),
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        source_is_subset_of_existing_449=True,
        additional_independent_observations=0,
        later_reference_is_after_endpoint_seconds=0.000001,
        tolerance_seconds=protocol["tolerance_seconds"],
        probes=probes,
        checks_passed=all(all(p["checks"].values()) for p in probes),
        scope="Post-build conditional probes, not a blind assessment, a subsecond accuracy certificate, or a global birth-time uncertainty interval",
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "probes"}))
    return 0 if result["checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
