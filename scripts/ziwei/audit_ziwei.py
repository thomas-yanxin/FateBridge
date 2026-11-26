"""Audit frozen calendar, classical-text and software-reference Ziwei cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import (
    LUNAR_SUPPORTED_SOLAR_END,
    LUNAR_SUPPORTED_SOLAR_START,
)
from scripts.ziwei.audit_ziwei_activation import audit_activation
from scripts.ziwei.audit_ziwei_age import audit_age_calendar
from scripts.ziwei.audit_ziwei_auxiliaries import audit_auxiliaries
from scripts.ziwei.audit_ziwei_calendar_coverage import audit_calendar, hko_rows
from scripts.ziwei.audit_ziwei_calendar_sources import audit_calendar_sources
from scripts.ziwei.audit_ziwei_childhood import audit_childhood
from scripts.ziwei.audit_ziwei_civil_fold import audit_civil_fold
from scripts.ziwei.audit_ziwei_classical import (
    audit_additional_classical,
    audit_classical,
    audit_depth_classical,
)
from scripts.ziwei.audit_ziwei_clock import audit_clock_basis
from scripts.ziwei.audit_ziwei_conditions import audit_conditions
from scripts.ziwei.audit_ziwei_cycles import audit_cycles
from scripts.ziwei.audit_ziwei_days import audit_day_tables
from scripts.ziwei.audit_ziwei_independent_readings import audit_independent_readings
from scripts.ziwei.audit_ziwei_limits import audit_limits
from scripts.ziwei.audit_ziwei_ming_placements import audit_ming_anxing, audit_ming_scan
from scripts.ziwei.audit_ziwei_ming_properties import audit_ming_properties
from scripts.ziwei.audit_ziwei_natal import audit_natal
from scripts.ziwei.audit_ziwei_natal_prerequisites import audit_natal_prerequisites
from scripts.ziwei.audit_ziwei_phase import audit_phase_days
from scripts.ziwei.audit_ziwei_prerequisites import audit_prerequisites
from scripts.ziwei.audit_ziwei_review_disclosure import audit_review_disclosure
from scripts.ziwei.audit_ziwei_sihua_selection import audit_sihua_selection
from scripts.ziwei.audit_ziwei_solar_clock import audit_solar_clock
from scripts.ziwei.audit_ziwei_subperiods import audit_subperiods
from scripts.ziwei.audit_ziwei_targeted_rereading import audit_targeted_rereading
from scripts.ziwei.audit_ziwei_time_input import audit_time_input
from scripts.ziwei.ziwei_conditional_inputs import FIXTURES, synthetic_seed

__all__ = [
    "FIXTURES",
    "audit_additional_classical",
    "audit_calendar",
    "audit_classical",
    "audit_depth_classical",
    "audit_ming_scan",
    "hko_rows",
    "report",
    "synthetic_seed",
]


def report() -> dict[str, Any]:
    calendar, classical = audit_calendar(), audit_classical()
    natal, additional = audit_natal(), audit_additional_classical()
    depth = audit_depth_classical()
    phase_days = audit_phase_days()
    ming = audit_ming_scan()
    ming_anxing = audit_ming_anxing()
    ming_days = audit_day_tables()
    ming_prerequisites = audit_prerequisites()
    ming_auxiliaries = audit_auxiliaries()
    ming_limits = audit_limits()
    clock_basis = audit_clock_basis(hko_rows, FIXTURES)
    childhood = audit_childhood()
    cycles = audit_cycles()
    time_input = audit_time_input()
    solar_clock = audit_solar_clock(hko_rows, FIXTURES)
    ming_properties = audit_ming_properties()
    activation = audit_activation()
    sihua_selection = audit_sihua_selection()
    civil_fold = audit_civil_fold()
    conditions = audit_conditions()
    subperiods = audit_subperiods()
    calendar_sources = audit_calendar_sources()
    age_calendar = audit_age_calendar(hko_rows, FIXTURES)
    natal_prerequisites = audit_natal_prerequisites(FIXTURES)
    independent_readings = audit_independent_readings(FIXTURES)
    review_disclosure = audit_review_disclosure()
    targeted_rereading = audit_targeted_rereading()
    return {
        "audit_version": "ziwei_professional_axes_v26",
        "calendar": calendar,
        "calendar_new_moon_extension": phase_days,
        "calendar_clock_basis": clock_basis,
        "calendar_time_input_receipts": time_input,
        "calendar_solar_clock": solar_clock,
        "ming_symbolic_definitions": ming_properties,
        "formal_decade_activation": activation,
        "explicit_ming_sihua_selection": sihua_selection,
        "explicit_civil_offset_resolution": civil_fold,
        "ming_structural_conditions": conditions,
        "ming_limit_subperiods": subperiods,
        "calendar_date_sources": calendar_sources,
        "coherent_nominal_age_calendar": age_calendar,
        "horoscope_natal_prerequisite_evidence": natal_prerequisites,
        "independent_source_readings": independent_readings,
        "independent_review_disclosure": review_disclosure,
        "targeted_source_rereading": targeted_rereading,
        "current_supported_civil_date_label_coverage": {
            "distinct_dates_compared": calendar["full_date_cells"]
            + calendar_sources["distinct_printed_civil_dates"],
            "runtime_supported_date_count": (
                LUNAR_SUPPORTED_SOLAR_END - LUNAR_SUPPORTED_SOLAR_START
            ).days
            + 1,
            "printed_date_labels_only_not_full_clock_acceptance": True,
            "fixed_source_cohort_never_reduced_to_runtime_support": True,
            "source_join": "TAM 1900-12-31 lunar 1900/11/10 to HKO 1901-01-01 lunar 1900/11/11; nineteen missing January month labels carry from the preceding printed table",
        },
        "classical": classical,
        "natal_software_reference": natal,
        "additional_classical_tables": additional,
        "depth_classical_rules": depth,
        "ming_scan_collation": ming,
        "ming_anxing_collation": ming_anxing,
        "ming_day_table_collation": ming_days,
        "ming_prerequisite_collation": ming_prerequisites,
        "ming_auxiliary_collation": ming_auxiliaries,
        "ming_limit_readings": ming_limits,
        "ming_childhood_rows": childhood,
        "ming_cycle_rules": cycles,
        "regression_checks_passed": not calendar["mismatches"]
        and not classical["failed_vectors"]
        and not natal["differences"]
        and not additional["differences"]
        and not depth["mismatches"]
        and not phase_days["mismatches"]
        and not ming["mismatches"]
        and not ming_anxing["mismatches"]
        and not ming_days["mismatches"]
        and not ming_prerequisites["mismatches"]
        and not ming_auxiliaries["mismatches"]
        and not ming_limits["mismatches"]
        and not clock_basis["differences"]
        and not childhood["mismatches"]
        and not cycles["mismatches"]
        and not time_input["differences"]
        and not solar_clock["differences"]
        and not ming_properties["mismatches"]
        and not activation["mismatches"]
        and not sihua_selection["differences"]
        and not civil_fold["differences"]
        and not conditions["differences"]
        and not subperiods["differences"]
        and not calendar_sources["differences"]
        and not age_calendar["differences"]
        and not natal_prerequisites["differences"]
        and not independent_readings["direct_position_differences"]
        and not review_disclosure["mismatches"]
        and not targeted_rereading["mismatches"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = report()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        pass
    print(encoded, end="")
    raise SystemExit(0 if result["regression_checks_passed"] else 1)


if __name__ == "__main__":
    main()
else:
    pass
