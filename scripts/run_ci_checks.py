"""Run self-contained CI checks; external physical reference tests stay local."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    "quality/test_architecture_boundaries.py",
    "integration/test_ci_regressions.py",
    "integration/test_calculation_evidence.py",
    "integration/test_verified_outputs.py",
    "bazi/test_bazi_structural_priority.py",
    "bazi/test_bazi_source_repairs.py",
    "human_design/test_hd_apparent_models.py",
    "integration/test_acceptance_population.py",
    "astronomy/test_ephemeris_context.py",
    "quality/test_repository_cleanup.py",
    "integration/test_result_delivery.py",
    "integration/test_result_delivery_storage.py",
    "integration/test_life_dimensions.py",
    "integration/test_algorithm_review_repairs.py",
    "integration/test_compute_limits.py",
    "integration/test_coordinate_and_calendar_transports.py",
    "fengshui/test_fengshui_rotation_invariance.py",
    "fengshui/test_fengshui_attached_permissions.py",
    "bazi/test_ci_regressions.py",
    "astronomy/test_solar_term_published_reference.py",
    "bazi/test_bazi_candidate_revelation.py",
    "bazi/test_bazi_timing_strength.py",
    "bazi/test_bazi_timing_stem_binding.py",
    "bazi/test_bazi_timing_strength_transports.py",
    "integration/test_divination_fractional_offsets.py",
    "liuyao/test_liuyao_hidden_pending_control.py",
    "liuyao/test_liuyao_pending_strength.py",
    "taiyi/test_taiyi_edition_witness.py",
    "western/test_western_extra_return_order.py",
    "western/test_western_return_station.py",
    "western/test_western_return_residual.py",
    "western/test_western_solar_arc_precision.py",
    "astrodice/test_astrodice_apparent_source_audit.py",
    "astrodice/test_astrodice_sampler_paths.py",
    "western/test_horary_refranation_order.py",
    "jyotish/test_jyotish_partial_strength.py",
    "western/test_western_distribution_partition.py",
    "western/test_ci_regressions.py",
    "western/test_western_method_inputs.py",
    "compatibility/test_relationship_focus.py",
    "astronomy/test_equal_lunar_sectors.py",
    "western/test_western_antipodes.py",
    "western/test_western_antipode_houses.py",
    "western/test_western_progression_frames.py",
    "astronomy/test_calendar_helper_tools.py",
    "integration/test_complete_moshier_solar.py",
    "astronomy/test_prepare_jpl_kernel.py",
    "western/test_western_opaque_solar.py",
    "astronomy/test_fetch_ephe.py",
    "astronomy/test_ephemeris_integrity.py",
    "astronomy/test_ephemeris_runtime.py",
    "astronomy/test_ephemeris_thread_paths.py",
    "integration/test_scenario_dependency_closure.py",
    "integration/test_cli.py",
    "integration/test_api_alignment.py",
    "integration/test_full_surface_validation.py",
    "integration/test_runtime_and_errors.py",
    "integration/test_schema_cache.py",
    "integration/test_mcp_input_contracts.py",
    "integration/test_mcp_native_contracts.py",
    "integration/test_complete_output_contracts.py",
    "quality/test_ci_runner.py",
)
POSIX_CHECKS = (
    "quality/test_documentation_integrity.py",
    "quality/test_doc_tool_counts.py",
    "quality/test_skills_interface_contract.py",
    "quality/test_skills_engine_contract.py",
    "quality/test_codex_call_contracts.py",
    "quality/test_codex_experience.py",
    "quality/test_ci_workflow.py",
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
