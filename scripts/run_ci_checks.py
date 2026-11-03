"""Run self-contained CI checks; external-data and golden tests stay local."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    "test_architecture_boundaries.py",
    "test_runtime_contracts.py",
    "test_repository_cleanup.py",
    "test_restore_test_data.py",
    "test_private_files.py",
    "test_result_delivery.py",
    "test_result_delivery_storage.py",
    "test_coordinates.py",
    "test_life_dimensions.py",
    "test_coordinate_and_calendar_transports.py",
    "test_calendar_helper_tools.py",
    "test_fetch_ephe.py",
    "test_ephemeris_integrity.py",
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
