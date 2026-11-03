"""Balance CI nodes by measured cost; every eligible node still runs once."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pytest
from xdist import get_xdist_worker_id  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]


class CIShard:
    def __init__(
        self,
        index: int,
        count: int,
        report: Path | None = None,
        environment: str = "local",
        weights: Mapping[str, float] | None = None,
    ) -> None:
        self.index = index
        self.count = count
        self.report = report
        self.environment = environment
        self.weights = weights or {}

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(
        self, session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
    ) -> None:
        collected = [item.nodeid for item in items]
        loads = [0.0] * self.count
        assignments = [0] * len(items)
        costs = [
            (i, self.weights.get(item.nodeid, 1.0)) for i, item in enumerate(items)
        ]
        for position, cost in sorted(costs, key=lambda row: row[1], reverse=True):
            destination = min(range(self.count), key=loads.__getitem__)
            assignments[position] = destination
            loads[destination] += cost
        selected = [
            item for i, item in enumerate(items) if assignments[i] == self.index
        ]
        deselected = [
            item for i, item in enumerate(items) if assignments[i] != self.index
        ]
        items[:] = selected
        config.hook.pytest_deselected(items=deselected)
        # xdist workers collect the same nodes. One designated worker writes
        # the report; normal pytest/collect-only uses the master process.
        if self.report is not None and get_xdist_worker_id(session) in {
            "master",
            "gw0",
        }:
            self.report.write_text(
                json.dumps(
                    {
                        "environment": self.environment,
                        "shard_index": self.index,
                        "shard_count": self.count,
                        "estimated_loads": loads,
                        "collected": collected,
                        "selected": [item.nodeid for item in selected],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("ci sharding")
    group.addoption("--shard-index", type=int, default=0)
    group.addoption("--shard-count", type=int, default=1)
    group.addoption("--selection-report", type=Path)
    group.addoption("--environment-id", default="local")


def pytest_configure(config: pytest.Config) -> None:
    index: int = config.getoption("shard_index")
    count: int = config.getoption("shard_count")
    if not 0 <= index < count:
        raise pytest.UsageError("shard-index must be in [0, shard-count)")
    weights: dict[str, float] = json.loads(
        (ROOT / ".github/ci-test-costs.json").read_text(encoding="utf-8")
    )
    config.pluginmanager.register(
        CIShard(
            index,
            count,
            config.getoption("selection_report"),
            config.getoption("environment_id"),
            weights,
        ),
        "ci shard selection",
    )
