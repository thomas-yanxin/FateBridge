"""Run self-contained CI checks; external-data and golden tests stay local."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    "test_architecture_boundaries.py",
    "test_retired_entries.py",
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


class CIShard:
    """Partition the already marker-filtered collection and record coverage."""

    def __init__(
        self,
        index: int,
        count: int,
        report: Path | None = None,
        environment: str = "local",
    ) -> None:
        self.index = index
        self.count = count
        self.report = report
        self.environment = environment

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(
        self, config: pytest.Config, items: list[pytest.Item]
    ) -> None:
        collected = [item.nodeid for item in items]
        selected = items[self.index :: self.count]
        deselected = [
            item for i, item in enumerate(items) if i % self.count != self.index
        ]
        items[:] = selected
        config.hook.pytest_deselected(items=deselected)
        if self.report is not None:
            self.report.write_text(
                json.dumps(
                    {
                        "environment": self.environment,
                        "shard_index": self.index,
                        "shard_count": self.count,
                        "collected": collected,
                        "selected": [item.nodeid for item in selected],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--selection-report", type=Path)
    parser.add_argument("--environment-id", default="local")
    options, pytest_args = parser.parse_known_args()
    if not 0 <= options.shard_index < options.shard_count:
        parser.error("shard-index must be in [0, shard-count)")
    selected = CHECKS if sys.platform == "win32" else (*CHECKS, *POSIX_CHECKS)
    return int(
        pytest.main(
            [
                "-q",
                "-m",
                "not local_data",
                *(str(ROOT / "tests" / name) for name in selected),
                *pytest_args,
            ],
            plugins=[
                CIShard(
                    options.shard_index,
                    options.shard_count,
                    options.selection_report,
                    options.environment_id,
                )
            ],
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
