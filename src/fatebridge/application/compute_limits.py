"""One process-wide budget for heavy work on every public transport."""

import logging
import os
from threading import BoundedSemaphore

from fatebridge.utils.runtime import load_runtime_env

load_runtime_env()

DEFAULT_MAX_CONCURRENCY = min(4, max(1, os.cpu_count() or 1))
try:
    MAX_CONCURRENCY = max(
        1,
        int(
            os.getenv(
                "FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY", str(DEFAULT_MAX_CONCURRENCY)
            )
        ),
    )
except ValueError:
    logging.getLogger(__name__).warning(
        "Invalid heavy calculation limit; using %s", DEFAULT_MAX_CONCURRENCY
    )
    MAX_CONCURRENCY = DEFAULT_MAX_CONCURRENCY

HEAVY_CALCULATIONS = BoundedSemaphore(MAX_CONCURRENCY)
