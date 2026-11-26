"""Run self-contained CI checks; external physical reference tests stay local."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    "quality/test_architecture_boundaries.py",
    "integration/test_ci_regressions.py",
    "bazi/test_bazi_structural_priority.py",
    "bazi/test_bazi_source_repairs.py",
    "bazi/test_bazi_zi_mao_entities.py",
    "human_design/test_hd_apparent_models.py",
    "astronomy/test_ephemeris_context.py",
    "numerology/test_canping_projection.py::test_future_lichun_uses_retained_point_and_outside_horizon_is_rejected",
    "numerology/test_canping_projection.py::test_frozen_2001_lichun_query_keeps_original_two_part_point",
    "numerology/test_canping_projection.py::test_real_lichun_and_civil_cut_may_share_display_without_collapsing_interval",
    "numerology/test_canping_projection.py::test_exact_interval_contract_accepts_same_label_and_rejects_nonpositive_points",
    "numerology/test_canping_projection.py::test_projected_interval_cap_is_unknown_until_explicitly_supplied",
    "bazi/test_bazi_dayun_integer.py::test_dayun_resolution_retains_source_point_without_a_json_roundtrip",
    "bazi/test_bazi_dayun_integer.py::test_retained_resolution_keeps_original_float_and_wall_guard_values",
    "bazi/test_bazi_dayun_integer.py::test_actual_wall_quantizes_the_original_span_without_float_ties",
    "bazi/test_bazi_dayun_integer.py::test_actual_wall_half_even_offset_preserves_integer_grid_translation",
    "integration/test_mcp_receipt.py",
    "integration/test_result_delivery.py",
    "integration/test_result_delivery_storage.py",
    "integration/test_result_delivery_publication.py",
    "integration/test_public_output.py",
    "integration/test_verified_result_readers.py",
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
    "integration/test_divination_fractional_offsets.py",
    "liuyao/test_liuyao_hidden_pending_control.py",
    "liuyao/test_liuyao_pending_strength.py",
    "taiyi/test_taiyi_edition_witness.py",
    "qimen/test_qimen_accuracy.py::test_all_1080_boards_preserve_stars_stems_doors_gods_and_leaders",
    "western/test_western_extra_return_order.py",
    "western/test_western_return_station.py",
    "western/test_western_events.py::test_mundane_cast_consumes_the_solved_source_tt",
    "western/test_horary_refranation_order.py",
    "jyotish/test_jyotish_partial_strength.py",
    "guolao/test_guolao_reference_geometry.py::test_reference_targets_keep_civil_TT_while_native_sources_remain_scalar",
    "western/test_western_distribution_partition.py",
    "western/test_ci_regressions.py",
    "western/test_western_method_inputs.py",
    "astronomy/test_source_light_cone.py",
    "compatibility/test_relationship_focus.py",
    "astronomy/test_equal_lunar_sectors.py",
    "western/test_western_antipodes.py",
    "western/test_western_progression_frames.py",
    "astronomy/test_selected_solar_terms.py",
    "astronomy/test_solar_term_runtime.py",
    "astronomy/test_swisseph_runtime_guards.py",
    "astronomy/test_prepare_jpl_kernel.py",
    "astronomy/test_fetch_ephe.py",
    "astronomy/test_ephemeris_integrity.py",
    "astronomy/test_ephemeris_runtime.py",
    "astronomy/test_ephemeris_thread_paths.py",
    "integration/test_cli.py",
    "integration/test_api_alignment.py",
    "integration/test_full_surface_validation.py",
    "integration/test_runtime_and_errors.py",
    "integration/test_schema_cache.py",
    "integration/test_mcp_input_contracts.py",
    "integration/test_mcp_native_contracts.py",
    "integration/test_complete_output_contracts.py",
    "integration/test_chart_variant_contracts.py",
    "bazi/test_bazi_analysis_calendar_transports.py",
    "meihua/test_meihua_summary_fidelity.py",
    "ziwei/test_ziwei_brightness_sources.py",
    "ziwei/test_ziwei_clock_receipt.py",
    "ziwei/test_ziwei_flowing_stars.py",
    "ziwei/test_ziwei_named_patterns.py",
    "ziwei/test_ziwei_natal_leap_month.py",
    "ziwei/test_ziwei_optional_snapshots.py",
    "ziwei/test_ziwei_palace_sihua.py",
    "ziwei/test_ziwei_year_branch_cycles.py",
    "quality/test_ci_runner.py",
)
POSIX_CHECKS = (
    "quality/test_documentation_integrity.py",
    "quality/test_doc_tool_counts.py",
    "quality/test_interpretation_examples.py",
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
else:
    pass
