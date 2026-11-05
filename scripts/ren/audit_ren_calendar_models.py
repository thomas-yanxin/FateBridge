"""Provider-aware Ren date audit, preserving the frozen Swiss-only auditor.

The original source and its provider gate remain byte-identical. This version
reuses its independently sourced parser and expectations, then separates civil
date equality, actual model identity, and the original Swiss-only gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.ren import audit_ren_calendar as legacy
from scripts.ren.audit_ren_calendar import (
    BRANCHES,
    CORPUS,
    MONTH_BRANCHES,
    ROOT,
    annual_rows,
    expected_day,
    reference,
    sha,
    table_stem,
    year_pair,
)

IMPLEMENTATION = (*legacy.IMPLEMENTATION, "scripts/ren/audit_ren_calendar_models.py")


def audit(years: list[int] | None = None, *, progress: bool = True) -> dict[str, Any]:
    ref = reference()
    requested = set(years or range(1901, 2101))
    if not requested or not requested <= set(range(1901, 2101)):
        raise ValueError("HKO years must be 1901..2100")
    manifest = json.loads(
        (ROOT / "tests/data/ziwei_independent/calendar_manifest.json").read_text()
    )
    if [s["year"] for s in manifest["sources"]] != list(range(1901, 2101)):
        raise ValueError("The source cohort must retain all 200 HKO years")
    implementation = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    # Only now import the production chain.
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.ren_calendar import (
        require_ren_calendar,
        require_ren_solar_term,
    )
    from fatebridge.services.metaphysics import _build_analysis_seed

    annual = []
    failures = []
    errors = []
    term_failures = []
    term_source_failures = []
    legacy_provider_failures = []
    term_providers: dict[str, int] = {}
    state = (1900, 11, False)
    source_root = ROOT / "tests/data/ziwei_independent"
    totals = dict(
        civil_dates=0,
        day_checks=0,
        hour_checks=0,
        year_month_date_brackets=0,
        year_month_underdetermined=0,
        month_general_date_brackets=0,
        month_general_underdetermined=0,
        lunar_checks=0,
        lunar_unavailable=0,
        term_dates=0,
        calendar_policies=0,
    )
    for source in manifest["sources"]:
        file = source_root / source["path"]
        if sha(file) != source["sha256"]:
            raise ValueError(f"Frozen HKO text changed: {source['path']}")
        rows, state = annual_rows(
            file.read_text(encoding="utf-8-sig"), source["year"], state
        )
        if source["year"] not in requested:
            continue
        year = source["year"]
        before = dict(totals)
        terms = {t.name: t for t in get_solar_terms_for_year(year, "+08:00")}
        prior_month = "子"
        prior_general = "丑"
        prior_year = year - 1
        for row in rows:
            solar = row["date"]
            term = row["term"]
            totals["civil_dates"] += 1
            if term:
                totals["term_dates"] += 1
                actual_term = terms[term]
                term_providers[actual_term.resolution_provider] = (
                    term_providers.get(actual_term.resolution_provider, 0) + 1
                )
                item = dict(
                    year=year,
                    term=term,
                    expected_date=solar.isoformat(),
                    actual=actual_term.moment.isoformat(),
                    provider=actual_term.resolution_provider,
                )
                if actual_term.resolution_provider != "swisseph":
                    legacy_provider_failures.append(item)
                try:
                    require_ren_solar_term(actual_term)
                except Exception as exc:
                    term_source_failures.append(
                        {**item, "error_type": type(exc).__name__, "error": str(exc)}
                    )
                if actual_term.moment.date() != solar:
                    term_failures.append(item)
            new_month = ref["month_starts"].get(term, prior_month)
            new_general = ref["general_starts"].get(term, prior_general)
            new_year = year if term == "立春" else prior_year
            # A term date bounds a physical crossing but does not say whether
            # noon is before or after it. The two correlated year/month states
            # are retained, never a permissive Cartesian product.
            ym_states = {(prior_year, prior_month), (new_year, new_month)}
            expected_ym = {
                (
                    year_pair(y),
                    table_stem(
                        ref["month_stems"], year_pair(y)[0], MONTH_BRANCHES.index(m)
                    )
                    + m,
                )
                for y, m in ym_states
            }
            allowed_generals = {prior_general, new_general}
            for hour in (12, 23):
                try:
                    seed = _build_analysis_seed(
                        analysis_year=year,
                        analysis_month=solar.month,
                        analysis_day=solar.day,
                        analysis_hour=hour,
                        analysis_timezone="+08:00",
                        use_true_solar_time=False,
                    )
                    policy = require_ren_calendar(seed)
                    seed.calendar_context["ren_calendar_policy"] = policy
                    board = build_liureng_board(seed)
                    jinkou = build_jinkou_board(seed, board, di_fen="子")
                except Exception as error:
                    errors.append(
                        dict(
                            date=solar.isoformat(),
                            hour=hour,
                            error_type=type(error).__name__,
                            message=str(error),
                        )
                    )
                    continue
                day = expected_day(solar, ref, hour == 23)
                hour_index = 6 if hour == 12 else 0
                expected_hour = (
                    table_stem(ref["hour_stems"], day[0], hour_index)
                    + BRANCHES[hour_index]
                )
                actual_day = "".join(seed.pillars["day"])
                actual_hour = "".join(seed.pillars["hour"])
                actual_ym = (
                    "".join(seed.pillars["year"]),
                    "".join(seed.pillars["month"]),
                )
                checks = {
                    "day": (actual_day, day),
                    "hour": (actual_hour, expected_hour),
                }
                totals["day_checks"] += 1
                totals["hour_checks"] += 1
                for layer, (actual, expected) in checks.items():
                    if actual != expected:
                        failures.append(
                            dict(
                                date=solar.isoformat(),
                                hour=hour,
                                layer=layer,
                                actual=actual,
                                expected=expected,
                            )
                        )
                totals["year_month_date_brackets"] += 1
                totals["year_month_underdetermined"] += int(len(expected_ym) > 1)
                if actual_ym not in expected_ym:
                    failures.append(
                        dict(
                            date=solar.isoformat(),
                            hour=hour,
                            layer="year_month",
                            actual=actual_ym,
                            expected_date_bracket=sorted(expected_ym),
                        )
                    )
                totals["month_general_date_brackets"] += 1
                totals["month_general_underdetermined"] += int(
                    len(allowed_generals) > 1
                )
                general = board["month_general"]["branch"]
                if (
                    general not in allowed_generals
                    or jinkou["overview"]["month_general"]["branch"] != general
                ):
                    failures.append(
                        dict(
                            date=solar.isoformat(),
                            hour=hour,
                            layer="month_general",
                            actual=general,
                            expected_date_bracket=sorted(allowed_generals),
                        )
                    )
                totals["calendar_policies"] += 1
                if (
                    board["calendar_policy"] != policy
                    or jinkou["calendar_policy"] != policy
                ):
                    failures.append(
                        dict(
                            date=solar.isoformat(),
                            hour=hour,
                            layer="calendar_policy_propagation",
                        )
                    )
                if hour == 12:
                    lunar = seed.calendar_context.get("lunar_calendar")
                    if lunar is None:
                        totals["lunar_unavailable"] += 1
                    else:
                        totals["lunar_checks"] += 1
                        keys = ("year", "month", "day", "is_leap_month")
                        expected_lunar = {key: row[key] for key in keys}
                        actual_lunar = {key: lunar[key] for key in keys}
                        if expected_lunar != actual_lunar:
                            failures.append(
                                dict(
                                    date=solar.isoformat(),
                                    layer="lunar",
                                    actual=actual_lunar,
                                    expected=expected_lunar,
                                )
                            )
            prior_year, prior_month, prior_general = new_year, new_month, new_general
        annual.append(
            dict(year=year, **{key: totals[key] - before[key] for key in totals})
        )
        if progress and len(annual) % 10 == 0:
            print(
                f"Ren calendar: {len(annual)} years, {totals['civil_dates']} dates, {len(failures)} calculation differences, {len(term_failures)} term-date differences",
                flush=True,
            )
    unchanged = implementation == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    return dict(
        audit_id="ren_calendar_models_v2",
        years=sorted(requested),
        full_hko_cohort=requested == set(range(1901, 2101)),
        clock="fixed +08:00 noon and 23:00 with declared late-Zi rollover",
        totals=totals,
        calculation_mismatch_count=len(failures),
        calculation_mismatches=failures,
        calculation_errors=errors,
        term_date_mismatch_count=len(term_failures),
        term_date_mismatches=term_failures,
        term_source_failure_count=len(term_source_failures),
        term_source_failures=term_source_failures,
        term_providers=term_providers,
        legacy_swiss_only_provider_failure_count=len(legacy_provider_failures),
        legacy_swiss_only_provider_failures=legacy_provider_failures,
        legacy_swiss_only_comparison_passed=not failures
        and not errors
        and not term_failures
        and not legacy_provider_failures
        and unchanged,
        annual_reports=annual,
        implementation_sha256=implementation,
        implementation_unchanged_during_audit=unchanged,
        all_performed_comparisons_passed=not failures
        and not errors
        and not term_failures
        and not term_source_failures
        and unchanged,
        full_supported_calendar_domain_certified=False,
        goal_complete=False,
        source_sha256=sha(CORPUS / "reference.json"),
        limits=ref["limits"]
        + [
            ref["source_precision"],
            "No production errors or unavailable lunar dates are removed from counts. Unknown years and clocks remain unverified; source-day brackets cannot substitute for exact-minute boundary checks.",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--year", action="append", type=int)
    args = parser.parse_args()
    report = audit(args.year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "totals": report["totals"],
                "calculation_mismatches": report["calculation_mismatch_count"],
                "term_date_mismatches": report["term_date_mismatch_count"],
                "errors": len(report["calculation_errors"]),
                "implementation_unchanged": report[
                    "implementation_unchanged_during_audit"
                ],
            }
        ),
        flush=True,
    )
    return 0 if report["all_performed_comparisons_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
