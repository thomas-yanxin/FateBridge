"""Offline, evidence-bounded Ziwei audit. Unknowns never become full marks.

Calendar expectations come directly from frozen HKO cells; classical
expectations are literal excerpts/hand-derived vectors, not engine snapshots.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
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
from scripts.ziwei.ziwei_conditional_inputs import FIXTURES, ROOT, synthetic_seed

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
    def implementation_hashes() -> dict[str, str]:
        return {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "pyproject.toml",
                "uv.lock",
                "src/fatebridge/core/almanac.py",
                "src/fatebridge/core/metaphysics/ziwei.py",
                "src/fatebridge/core/ziwei/ziwei_horoscope.py",
                "src/fatebridge/core/ziwei/ziwei_stars.py",
                "src/fatebridge/core/ziwei/ziwei_rulesets.py",
                "src/fatebridge/core/ziwei/ziwei_calendar.py",
                "src/fatebridge/core/ziwei/ziwei_date_sources.py",
                "src/fatebridge/core/lunar_1900_prefix.py",
                "src/fatebridge/core/lunar_supplement.py",
                "src/fatebridge/core/ziwei/ziwei_time_input.py",
                "src/fatebridge/core/metaphysics/common.py",
                "src/fatebridge/core/metaphysics/seed.py",
                "src/fatebridge/core/requests/birth.py",
                "src/fatebridge/core/ziwei/ziwei_childhood.py",
                "src/fatebridge/core/ziwei/ziwei_cycle_sources.py",
                "src/fatebridge/utils/solar_time.py",
                "src/fatebridge/utils/timezones.py",
                "src/fatebridge/utils/civil_clock.py",
                "src/fatebridge/utils/civil_time.py",
                "src/fatebridge/core/ziwei/ziwei_evidence.py",
                "src/fatebridge/core/ziwei/ziwei_auxiliary.py",
                "src/fatebridge/core/ziwei/ziwei_classical.py",
                "src/fatebridge/core/ziwei/ziwei_ming_properties.py",
                "src/fatebridge/core/ziwei/ziwei_conditions.py",
                "src/fatebridge/core/ziwei/ziwei_subperiods.py",
                "src/fatebridge/core/ziwei/ziwei_sources.py",
                "src/fatebridge/core/ziwei/ziwei_aux_sources.py",
                "src/fatebridge/core/ziwei/ziwei_limit_sources.py",
                "src/fatebridge/core/ziwei/ziwei_tables.py",
                "src/fatebridge/utils/data.py",
                "src/fatebridge/core/contracts/output_chinese.py",
                "src/fatebridge/core/response_models.py",
                "src/fatebridge/core/requests/metaphysics.py",
                "src/fatebridge/data/agent_examples.json",
                "docs/interpretation/shared/ziwei-topic-evidence.md",
                "src/fatebridge/data/classical/ziwei-quanshu-v2-table.json",
                "src/fatebridge/data/classical/ziwei-quanshu-v2-stars.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-symbolism.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-conditions.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-subperiods.json",
                "src/fatebridge/data/classical/ziwei-calendar-references.json",
                "src/fatebridge/data/lunar_calendar_pmo_1900_prefix.json",
                "src/fatebridge/data/lunar_calendar_hko_2100.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-sihua.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-days.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-prerequisites.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-auxiliaries.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-limits.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-childhood.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-cycles.json",
                "src/fatebridge/services/metaphysics.py",
                "src/fatebridge/services/catalog/metaphysics.py",
                "src/fatebridge/application/result_delivery.py",
                "src/fatebridge/application/result_budget.py",
                "src/fatebridge/services/replay_metadata.py",
                "tests/fixtures/mcp_receipt.py",
                "tests/integration/test_result_delivery.py",
                "tests/ziwei/test_ziwei_eleventh_iteration.py",
                "tests/ziwei/test_ziwei_twelfth_iteration.py",
                "scripts/ziwei/audit_ziwei.py",
                "scripts/ziwei/audit_ziwei_calendar_coverage.py",
                "scripts/ziwei/audit_ziwei_classical.py",
                "scripts/ziwei/audit_ziwei_ming_placements.py",
                "scripts/ziwei/ziwei_conditional_inputs.py",
                "scripts/ziwei/audit_ziwei_clock.py",
                "scripts/ziwei/audit_ziwei_age.py",
                "src/fatebridge/core/ziwei/ziwei_age.py",
                "src/fatebridge/data/classical/ziwei-age-source-scope.json",
                "tests/ziwei/test_ziwei_twenty_first_iteration.py",
                "scripts/ziwei/audit_ziwei_independent_readings.py",
                "scripts/ziwei/audit_ziwei_review_disclosure.py",
                "scripts/ziwei/build_ziwei_review_disclosure.py",
                "tests/ziwei/test_ziwei_twenty_third_iteration.py",
                "validation/agent_capture.py",
                "src/fatebridge/data/classical/ziwei-naj-ming-targeted-review-r24.json",
                "scripts/ziwei/build_ziwei_targeted_rereading.py",
                "scripts/ziwei/audit_ziwei_targeted_rereading.py",
                "tests/ziwei/test_ziwei_twenty_fourth_iteration.py",
                "tests/ziwei/test_ziwei_twenty_fifth_iteration.py",
                "tests/ziwei/test_ziwei_twenty_sixth_iteration.py",
                "scripts/ziwei/audit_ziwei_natal_prerequisites.py",
                "src/fatebridge/data/classical/ziwei-naj-ming-days-review-r22.json",
                "src/fatebridge/api.py",
                "src/fatebridge/cli.py",
                "src/fatebridge/mcp_transport.py",
                "tests/ziwei/test_ziwei_twenty_second_iteration.py",
                "scripts/ziwei/audit_ziwei_time_input.py",
                "scripts/ziwei/audit_ziwei_solar_clock.py",
                "scripts/ziwei/collect_ziwei_solar_reference.py",
                "tests/ziwei/test_ziwei_thirteenth_iteration.py",
                "tests/ziwei/test_ziwei_fourteenth_iteration.py",
                "scripts/ziwei/audit_ziwei_ming_properties.py",
                "scripts/ziwei/audit_ziwei_childhood.py",
                "scripts/ziwei/audit_ziwei_cycles.py",
                "scripts/ziwei/audit_ziwei_natal.py",
                "scripts/ziwei/audit_ziwei_phase.py",
                "scripts/ziwei/audit_ziwei_days.py",
                "scripts/ziwei/audit_ziwei_prerequisites.py",
                "scripts/ziwei/audit_ziwei_auxiliaries.py",
                "scripts/ziwei/audit_ziwei_limits.py",
                "scripts/ziwei/audit_ziwei_activation.py",
                "tests/ziwei/test_ziwei_fifteenth_iteration.py",
                "tests/ziwei/test_ziwei_eighth_iteration.py",
                "tests/ziwei/test_ziwei_horoscope.py",
                "tests/ziwei/test_ziwei_depth.py",
                "tests/ziwei/test_ziwei_horoscope_crosscheck.py",
                "tests/ziwei/test_ziwei_depth_transports.py",
                "tests/integration/test_mcp_receipt.py",
                "tests/ziwei/test_ziwei_sixteenth_iteration.py",
                "scripts/ziwei/audit_ziwei_sihua_selection.py",
                "scripts/ziwei/audit_ziwei_civil_fold.py",
                "tests/ziwei/test_ziwei_seventeenth_iteration.py",
                "scripts/ziwei/audit_ziwei_conditions.py",
                "tests/ziwei/test_ziwei_eighteenth_iteration.py",
                "scripts/ziwei/audit_ziwei_subperiods.py",
                "tests/ziwei/test_ziwei_nineteenth_iteration.py",
                "scripts/ziwei/audit_ziwei_calendar_sources.py",
                "tests/ziwei/test_ziwei_twentieth_iteration.py",
                "tests/ziwei/test_ziwei_depth.py",
            )
        }

    def source_hashes() -> dict[str, str]:
        return {
            name: hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
            for name in (
                "calendar_manifest.json",
                "age_calendar_scope_v1/manifest.json",
                "age_calendar_scope_v2/manifest.json",
                "independent_readings_r22_v1/manifest.json",
                "targeted_rereading_r24_v1/manifest.json",
                "clock_manifest.json",
                "time_input_manifest.json",
                "pre_decade_policy_manifest.json",
                "sihua_selection_vectors.json",
                "ziwei_civil_fold_v1/manifest.json",
                "naj_ming_conditions_v1/checksums.json",
                "naj_ming_conditions_r25_v1/manifest.json",
                "naj_ming_conditions_r25_v2/manifest.json",
                "naj_ming_conditions_v1/coverage_extension.json",
                "naj_ming_subperiods_v1/checksums.json",
                "naj_ming_subperiods_v1/coverage_extension.json",
                "calendar_1900_sources_v1/checksums.json",
                "calendar_implementation_coverage_extension.json",
                "../ziwei_solar_jpl_v1/protocol.json",
                "../ziwei_solar_jpl_v1/manifest.json",
                "classical_manifest.json",
                "additional_manifest.json",
                "natal_manifest.json",
                "depth_manifest.json",
                "phase_manifest.json",
                "naj_ming/checksums.json",
                "naj_ming_anxing_v1/checksums.json",
                "naj_ming_day_tables_v1/checksums.json",
                "naj_ming_prerequisites_v1/checksums.json",
                "naj_ming_auxiliaries_v1/checksums.json",
                "naj_ming_limits_v1/checksums.json",
                "naj_ming_childhood_v1/checksums.json",
                "naj_ming_cycles_v1/checksums.json",
                "naj_ming_symbolism_v1/checksums.json",
            )
        }

    implementation, sources = implementation_hashes(), source_hashes()
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
    if implementation_hashes() != implementation or source_hashes() != sources:
        raise RuntimeError(
            "Source changed during Ziwei audit; rerun against a stable snapshot"
        )
    else:
        pass
    return {
        "audit_version": "ziwei_professional_axes_v26",
        "audit_root": str(ROOT),
        "runtime_environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "environment_prefix": str(Path(sys.prefix).resolve()),
            "dependency_versions": dict(
                sorted(
                    (distribution.metadata["Name"], distribution.version)
                    for distribution in importlib.metadata.distributions()
                    if distribution.metadata["Name"]
                )
            ),
        },
        "implementation_sha256": implementation,
        "source_manifest_sha256": sources,
        "source_stability_verified": True,
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
        "active_objective_axes": ["calendar", "classical", "interpretation_fidelity"],
        "interpretation_fidelity": {
            "status": "partial",
            "engine_evidence": "Versioned rules, natal geometry, scope palace map and transformation joins",
            "live_model_blind_evaluation": "not_run",
            "structured_fact_verifier": "same_run_calculation_claims_v1; not a free-text semantic certification",
            "symbolic_source_records_checked": depth["symbolic_source_records_checked"],
            "symbolic_calculation_joins_checked": depth[
                "symbolic_calculation_joins_checked"
            ],
            "score": None,
        },
        "real_world_prediction": {
            "required_for_current_objective": False,
            "status": "not_tested",
            "prospective_locked_cases": 0,
            "independent_outcomes": 0,
            "score": None,
            "required": [
                "Preregistered outcomes and time windows",
                "Predictions locked before outcomes",
                "Blind outcome adjudication and held-out sample",
                "Compare with base rates and non-chart baselines; retain failures/abstentions",
            ],
        },
        "full_acceptance_passed": False,
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
    parser.add_argument(
        "--require-full",
        action="store_true",
        help="Exit nonzero unless calendar, classical and interpretation fidelity have actually been established",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = report()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        pass
    print(encoded, end="")
    raise SystemExit(
        0 if result["regression_checks_passed"] and not args.require_full else 1
    )


if __name__ == "__main__":
    main()
else:
    pass
