"""Shared Swiss Ephemeris availability and one-time failure diagnostics."""

from __future__ import annotations

import logging

from fatebridge.core.ephemeris_runtime import ephemeris_call as ephemeris_call
from fatebridge.core.ephemeris_runtime import (
    ephemeris_model_from_retflag as ephemeris_model_from_retflag,
)
from fatebridge.core.ephemeris_runtime import (
    preserve_ephemeris_path as preserve_ephemeris_path,
)
from fatebridge.core.ephemeris_runtime import swe as swe

logger = logging.getLogger(__name__)


# Log the first swisseph runtime failure so operators notice a broken ephemeris
# install instead of silently degrading to the approximation engine. Further
# failures are suppressed to avoid flooding the logs.
_SWE_RUNTIME_FAILURE_LOGGED = False


def _log_swe_runtime_failure(call: str, error: BaseException) -> None:
    global _SWE_RUNTIME_FAILURE_LOGGED
    if _SWE_RUNTIME_FAILURE_LOGGED:
        return
    _SWE_RUNTIME_FAILURE_LOGGED = True
    logger.warning(
        "Swiss Ephemeris %s raised %s (%s); inspect calculation provenance "
        "or error for the outcome. Subsequent failures will be suppressed.",
        call,
        type(error).__name__,
        error,
    )
