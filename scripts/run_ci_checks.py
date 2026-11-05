"""Run self-contained CI checks; external physical reference tests stay local."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    "test_architecture_boundaries.py",
    "test_runtime_contracts.py",
    "test_calculation_evidence.py",
    "test_verified_outputs.py",
    "test_bazi_structural_priority.py",
    "test_bazi_source_repairs.py",
    "test_hd_apparent_models.py",
    "test_acceptance_population.py",
    "test_output_facts.py",
    "test_ephemeris_context.py",
    "test_repository_cleanup.py",
    "test_private_files.py",
    "test_result_delivery.py",
    "test_result_delivery_storage.py",
    "test_coordinates.py",
    "test_life_dimensions.py",
    "test_algorithm_review_repairs.py",
    "test_compute_limits.py",
    "test_coordinate_and_calendar_transports.py",
    "test_fengshui_rotation_invariance.py",
    "test_fengshui_attached_permissions.py",
    "test_bazi_seasonal_phase_accuracy.py",
    "test_element_primitive.py",
    "test_solar_term_published_reference.py",
    "test_bazi_candidate_revelation.py",
    "test_bazi_timing_strength.py",
    "test_bazi_timing_stem_binding.py",
    "test_bazi_timing_strength_transports.py",
    "test_bazi_review_consistency.py",
    "test_divination_clock_inputs.py",
    "test_divination_fractional_offsets.py",
    "test_liuyao_hidden_pending_control.py",
    "test_liuyao_pending_strength.py",
    "test_tongshefa_inputs.py",
    "test_taiyi_edition_witness.py",
    "test_western_extra_return_order.py",
    "test_western_return_station.py",
    "test_western_return_residual.py",
    "test_western_solar_arc_precision.py",
    "test_astrodice_apparent_source_audit.py",
    "test_astrodice_sampler_paths.py",
    "test_horary_refranation_order.py",
    "test_jyotish_partial_strength.py",
    "test_western_distribution_partition.py",
    "test_western_derived_ordering.py",
    "test_western_method_inputs.py",
    "test_relationship_focus.py",
    "test_equal_lunar_sectors.py",
    "test_western_antipodes.py",
    "test_western_antipode_houses.py",
    "test_western_progression_frames.py",
    "test_profection_intervals.py",
    "test_western_return_lahiri.py",
    "test_calendar_helper_tools.py",
    "test_native_solar_crossing_side.py",
    "test_complete_moshier_solar.py",
    "test_prepare_jpl_kernel.py",
    "test_western_opaque_solar.py",
    "test_fetch_ephe.py",
    "test_ephemeris_integrity.py",
    "test_ephemeris_runtime.py",
    "test_ephemeris_thread_paths.py",
    "test_scenario_dependency_closure.py",
    "test_cli.py",
    "test_api_alignment.py",
    "test_full_surface_validation.py",
    "test_runtime_and_errors.py",
    "test_run_metadata.py",
    "test_schema_cache.py",
    "test_mcp_input_contracts.py",
    "test_mcp_native_contracts.py",
    "test_response_budget_contract.py",
    "test_request_catalog_isolation.py",
    "test_complete_output_contracts.py",
    "test_ci_runner.py",
)
POSIX_CHECKS = (
    "test_documentation_integrity.py",
    "test_doc_tool_counts.py",
    "test_skills_interface_contract.py",
    "test_skills_engine_contract.py",
    "test_codex_call_contracts.py",
    "test_codex_experience.py",
    "test_ci_workflow.py",
)


def main() -> int:
    selected = CHECKS if sys.platform == "win32" else (*CHECKS, *POSIX_CHECKS)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "scripts.ci_sharding",
            "-q",
            "-m",
            "not local_data",
            *(str(ROOT / "tests" / name) for name in selected),
            *sys.argv[1:],
        ],
        cwd=ROOT,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
