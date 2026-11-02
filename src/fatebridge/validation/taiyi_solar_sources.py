"""Pinned official-minute references and explicit solar-source comparisons.

This is an audit component, not a calendar provider or a source of forecasts.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from fatebridge.core.almanac import (
    get_solar_terms_for_year,
    is_calculated_solar_term,
)
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.taiyi_periods import period_frame
from fatebridge.services.metaphysics import _build_analysis_seed

FREEZE_SHA256 = "f2ca0a76be813ae4c0e38c788dc2fb8231507acb9b1b07c878f837555c0f2724"
PROVIDERS = {"native": "swisseph", "de440": "jpl_de440"}


def load_references(corpus: Path) -> dict[str, Any]:
    frozen = corpus / "freeze.json"
    if hashlib.sha256(frozen.read_bytes()).hexdigest() != FREEZE_SHA256:
        raise ValueError("太乙节气来源冻结清单指纹不符")
    manifest = json.loads(frozen.read_text())
    for name, expected in manifest["files"].items():
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"太乙节气来源指纹不符：{name}")
    reference = json.loads((corpus / "cases.json").read_text())
    if len(reference["cases"]) != 84:
        raise ValueError("必须保留全部84项机构刊载记录")
    return reference  # type: ignore[no-any-return]


@contextmanager
def solar_source(mode: str) -> Iterator[None]:
    """Single-process audit only; restore the caller's policy on every exit."""
    if mode not in {*PROVIDERS, "auto"}:
        raise ValueError("审计仅选择native、de440或auto")
    key = "FATEBRIDGE_SOLAR_TERM_MODEL"
    previous = os.environ.get(key)
    os.environ[key] = mode
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def seed_at(instant: datetime, *, solar: bool = False) -> MetaphysicsSeed:
    utc = instant.astimezone(timezone.utc)
    return _build_analysis_seed(
        analysis_year=utc.year,
        analysis_month=utc.month,
        analysis_day=utc.day,
        analysis_hour=utc.hour,
        analysis_minute=utc.minute,
        analysis_second=utc.second,
        analysis_timezone="UTC",
        analysis_longitude=0.0 if solar else None,
        use_true_solar_time=solar,
    )


def month_bracket(case: dict[str, Any], profile: str | None) -> dict[str, Any]:
    published = datetime.fromisoformat(case["at_utc"])
    before = period_frame(
        seed_at(published - timedelta(seconds=120)), "month", month_profile=profile
    )
    after = period_frame(
        seed_at(published + timedelta(seconds=120)), "month", month_profile=profile
    )
    expected_delta = int(case["kind"] == "jie")
    return {
        "before_anchor": before["anchor"].name,
        "after_anchor": after["anchor"].name,
        "before_counter": before["accumulation"],
        "after_counter": after["accumulation"],
        "expected_delta": expected_delta,
        "passed": (
            after["accumulation"] - before["accumulation"] == expected_delta
            and (
                after["anchor"].name == case["term"]
                if expected_delta
                else before["anchor"].moment == after["anchor"].moment
            )
        ),
    }


def solstice_bracket(
    case: dict[str, Any], profile: str | None, *, solar: bool
) -> dict[str, Any]:
    published = datetime.fromisoformat(case["at_utc"])
    before = period_frame(
        seed_at(published - timedelta(seconds=120), solar=solar),
        "hour",
        hour_profile=profile,
    )
    after = period_frame(
        seed_at(published + timedelta(seconds=120), solar=solar),
        "hour",
        hour_profile=profile,
    )
    yin = case["term"] == "夏至"
    return {
        "before_yin": before["yin"],
        "after_yin": after["yin"],
        "before_anchor": before["anchor"].name,
        "after_anchor": after["anchor"].name,
        "after_counter": after["accumulation"],
        "passed": (
            before["yin"] is not yin
            and after["yin"] is yin
            and after["anchor"].name == case["term"]
            and (after["accumulation"] == 1 if profile is None else True)
        ),
    }


def audit(corpus: Path) -> dict[str, Any]:
    reference = load_references(corpus)
    cases = reference["cases"]
    rows, months, hours = [], [], []
    for mode in [*PROVIDERS, "auto"]:
        with solar_source(mode):
            terms = {
                year: {t.name: t for t in get_solar_terms_for_year(year, "UTC")}
                for year in reference["years"]
            }
            for case in cases:
                term = terms[case["year"]][case["term"]]
                error = (
                    term.moment - datetime.fromisoformat(case["at_utc"])
                ).total_seconds()
                identity = (
                    term.resolution_provider == PROVIDERS[mode]
                    if mode in PROVIDERS
                    else is_calculated_solar_term(term)
                )
                rows.append(
                    {
                        "id": case["id"],
                        "mode": mode,
                        "actual_utc": term.moment.isoformat(),
                        "provider": term.resolution_provider,
                        "model": term.ephemeris_model,
                        "source_details": term.solar_model_details,
                        "error_seconds": error,
                        "passed": identity
                        and is_calculated_solar_term(term)
                        and abs(error) <= reference["tolerance_seconds"],
                    }
                )
            if mode == "auto":
                continue
            for case in cases[:72]:
                for profile in [None, "key_month_tianzheng_jie_v1"]:
                    months.append(
                        {
                            "id": case["id"],
                            "mode": mode,
                            "profile": profile,
                            **month_bracket(case, profile),
                        }
                    )
                if case["term"] not in {"冬至", "夏至"}:
                    continue
                for profile in [None, "key_hour_winter_jiazi_v1"]:
                    for solar in [False, True]:
                        hours.append(
                            {
                                "id": case["id"],
                                "mode": mode,
                                "profile": profile,
                                "solar": solar,
                                **solstice_bracket(case, profile, solar=solar),
                            }
                        )
    return {
        "scope": "Three official years at published-minute resolution; physical second-level accuracy and ancient-calendar conformance not certified",
        "source_rows": len(cases),
        "unique_events": len({(c["year"], c["term"]) for c in cases}),
        "solar_sources_are_independent_observatories": False,
        "differences_are_from_printed_minutes_not_physical_error_bounds": True,
        "tolerance_seconds": reference["tolerance_seconds"],
        "boundary_margin_seconds": reference["boundary_margin_seconds"],
        "timing_comparisons": rows,
        "month_brackets": months,
        "solstice_brackets": hours,
        "scoped_controls_passed": all(r["passed"] for r in rows + months + hours),
        "whole_calendar_acceptance_passed": False,
        "classical_acceptance_passed": False,
        "new_complete_dated_classical_cases": 0,
        "real_world_efficacy": "not_tested",
    }
