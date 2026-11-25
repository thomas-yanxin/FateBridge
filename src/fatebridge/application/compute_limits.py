"""Configure one process-wide budget for heavy calculations."""

import logging
import os
from dataclasses import dataclass
from threading import BoundedSemaphore, Lock

LOGGER = logging.getLogger(__name__)
DEFAULT_MAX_CONCURRENCY = min(4, max(1, os.cpu_count() or 1))


@dataclass(frozen=True, kw_only=True)
class HeavyCalculationBudget:
    max_concurrency: int
    semaphore: BoundedSemaphore


_BUDGET_LOCK = Lock()
_budget: HeavyCalculationBudget | None = None


def heavy_calculation_budget() -> HeavyCalculationBudget:
    """Initialize the shared budget once from the configured environment."""
    global _budget
    with _BUDGET_LOCK:
        if _budget is None:
            configured_limit = os.getenv(
                "FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY", str(DEFAULT_MAX_CONCURRENCY)
            )
            try:
                max_concurrency = max(1, int(configured_limit))
            except ValueError:
                LOGGER.warning(
                    f"Invalid heavy calculation limit; using {DEFAULT_MAX_CONCURRENCY}"
                )
                max_concurrency = DEFAULT_MAX_CONCURRENCY
            _budget = HeavyCalculationBudget(
                max_concurrency=max_concurrency,
                semaphore=BoundedSemaphore(max_concurrency),
            )
        else:
            pass
        return _budget
