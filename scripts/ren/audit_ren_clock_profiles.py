"""Reload counterfactual clock profiles without inventing historical events."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fatebridge.core import almanac
from fatebridge.core.astro import historical_utc as historical
from fatebridge.core.astro import time_scales, utc_policy
from fatebridge.core.metaphysics import ren_calendar
from fatebridge.core.solar_term_runtime import solar_term_cache_context
from fatebridge.services.metaphysics import (
    calculate_liureng_gods,
)

R = Path(__file__).resolve().parents[2]
F = R / "tests/fixtures/ren_clock_profiles_v1"


def reference(corpus: Path = F) -> dict[str, Any]:
    frozen = json.loads((corpus / "freeze.json").read_text())
    names = {"protocol.json", "source-links.json"}
    if set(frozen["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen clock-profile inventory changed")
    for name in names:
        if (
            hashlib.sha256((corpus / name).read_bytes()).hexdigest()
            != frozen["files"][name]
        ):
            raise ValueError("Frozen clock-profile protocol changed")
    for row in json.loads((corpus / "source-links.json").read_text())["sources"]:
        if hashlib.sha256((R / row["path"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Frozen clock-profile coefficient source changed")
    value = json.loads((corpus / "protocol.json").read_text())
    if not isinstance(value, dict):
        raise ValueError("Frozen clock-profile protocol must be an object")
    if len(value["historical_cases"]) != 2 or len(value["receipt_cases"]) != 2:
        raise ValueError("All four clock-profile faults are required")
    return value


PROTOCOL = reference()
WATCH = (
    "src/fatebridge/core/solar_term_runtime.py",
    "src/fatebridge/core/metaphysics/ren_calendar.py",
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/astro/time_scales.py",
    "src/fatebridge/core/astro/historical_utc.py",
    "src/fatebridge/core/calendar.py",
    "src/fatebridge/core/ephemeris_runtime.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/ren/audit_ren_clock_profiles.py",
    "uv.lock",
    "pyproject.toml",
)


def hashes() -> dict[str, str]:
    return {p: hashlib.sha256((R / p).read_bytes()).hexdigest() for p in WATCH}


def reset() -> None:
    getattr(almanac.get_solar_terms_for_year, "cache_clear")()
    getattr(ren_calendar._term_time_scale, "cache_clear")()


def payload(moment: datetime) -> dict[str, Any]:
    return dict(
        analysis_year=moment.year,
        analysis_month=moment.month,
        analysis_day=moment.day,
        analysis_hour=moment.hour,
        analysis_minute=moment.minute,
        analysis_second=moment.second,
        analysis_timezone="UTC",
        use_true_solar_time=False,
        selected_sections=["起盘信息", "三传"],
    )


def signature(terms: Any) -> list[tuple[str, str]]:
    return [(t.name, t.moment.isoformat()) for t in terms]


def dynamical_jd(moment: datetime) -> float:
    value = time_scales.ephemeris_time(moment).jd_tt
    if value is None:
        raise RuntimeError("Clock-profile experiment requires TT conversion")
    return value


def run() -> dict[str, Any]:
    before_hashes = hashes()
    rows = []
    for case in PROTOCOL["historical_cases"]:
        reset()
        name = "utc1960_table" if case["table"] == "utc1960" else "historical_utc_table"
        table = copy.deepcopy(getattr(historical, name)())
        with patch.object(historical, name, return_value=table):
            before = almanac.get_solar_terms_for_year(case["year"], "UTC")
            tt = [dynamical_jd(t.moment) for t in before]
            term = next(t for t in before if t.name == "雨水")
            instant = (term.moment - timedelta(seconds=1)).replace(microsecond=0)
            args = payload(instant)
            orig = calculate_liureng_gods(**args)
            key = solar_term_cache_context(almanac.swe)
            entry = next(
                e
                for e in table["entries"]
                if e["effective_date"] == case["entry_effective"]
            )
            entry["offset_seconds"] += case["offset_increment_seconds"]
            changed_key = solar_term_cache_context(almanac.swe)
            cached = almanac.get_solar_terms_for_year(case["year"], "UTC")
            cached_board = calculate_liureng_gods(**args)
            reset()
            fresh = almanac.get_solar_terms_for_year(case["year"], "UTC")
            fresh_board = calculate_liureng_gods(**args)
            wanted = -case["offset_increment_seconds"] / (
                1 + case["rate_seconds_per_day"] / 86400
            )
            shifts = [
                (b.moment - a.moment).total_seconds() for a, b in zip(before, fresh)
            ]
            tt_errors = [
                abs((dynamical_jd(t.moment) - old) * 86400) for t, old in zip(fresh, tt)
            ]
            row = dict(
                id=case["id"],
                context_changed=key != changed_key,
                cached_equals_fresh=signature(cached) == signature(fresh),
                required_terms=24,
                cached_terms=len(cached),
                fresh_terms=len(fresh),
                expected_utc_shift_seconds=wanted,
                max_utc_shift_error_seconds=max(abs(v - wanted) for v in shifts),
                max_tt_roundtrip_error_seconds=max(tt_errors),
                api_payload=args,
                boundary_input=instant.isoformat(),
                old_boundary=term.moment.isoformat(),
                new_boundary=next(
                    t for t in fresh if t.name == "雨水"
                ).moment.isoformat(),
                old_month_general=orig["liureng"]["month_general"]["branch"],
                cached_month_general=cached_board["liureng"]["month_general"]["branch"],
                fresh_month_general=fresh_board["liureng"]["month_general"]["branch"],
                cached_api_matches_fresh=cached_board["liureng"]["month_general"]
                == fresh_board["liureng"]["month_general"],
                actual_models=sorted({t.ephemeris_model for t in fresh}),
            )
            rows.append(row)
        reset()
    receipts = []
    for case in PROTOCOL["receipt_cases"]:
        reset()
        table = copy.deepcopy(utc_policy.leap_table())
        moment = datetime.fromisoformat(case["moment"])
        with patch.object(utc_policy, "leap_table", return_value=table):
            before_receipt = ren_calendar._term_time_scale(moment)
            table[case["field"]] = case["value"]
            cached_receipt = ren_calendar._term_time_scale(moment)
            getattr(ren_calendar._term_time_scale, "cache_clear")()
            fresh_receipt = ren_calendar._term_time_scale(moment)
            receipts.append(
                dict(
                    id=case["id"],
                    before=before_receipt,
                    cached=cached_receipt,
                    fresh=fresh_receipt,
                    cached_equals_fresh=cached_receipt == fresh_receipt,
                    expected_future_assumption=case["expected_future_assumption"],
                    fresh_future_matches=fresh_receipt[
                        "future_leap_seconds_assumed_unchanged"
                    ]
                    == case["expected_future_assumption"],
                )
            )
        reset()
    after_hashes = hashes()
    reference()
    criterion = PROTOCOL["criteria"]
    passed = all(
        r["context_changed"]
        and r["cached_equals_fresh"]
        and r["cached_api_matches_fresh"]
        and r["cached_terms"] == r["fresh_terms"] == 24
        and r["max_utc_shift_error_seconds"]
        <= criterion["utc_shift_absolute_error_seconds"]
        and r["max_tt_roundtrip_error_seconds"]
        <= criterion["tt_roundtrip_absolute_error_seconds"]
        for r in rows
    ) and all(r["cached_equals_fresh"] and r["fresh_future_matches"] for r in receipts)
    return dict(
        implementation_sha256=after_hashes,
        implementation_unchanged_during_audit=before_hashes == after_hashes,
        reference_freeze_sha256=hashlib.sha256(
            (F / "freeze.json").read_bytes()
        ).hexdigest(),
        engineering_checks_passed=passed and before_hashes == after_hashes,
        historical=rows,
        receipts=receipts,
        historical_faults_fixed=sum(
            r["context_changed"]
            and r["cached_equals_fresh"]
            and r["cached_api_matches_fresh"]
            for r in rows
        ),
        receipt_faults_fixed=sum(r["cached_equals_fresh"] for r in receipts),
        source_tables_modified=False,
        new_reference_events=0,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(text)
    print(text)
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
