"""Request-scoped admission of observed physical ephemeris sources.

This is a file-source policy, not a positional-accuracy certificate. Published
solar-event consumers observe every evaluation of their physical domain solver.
Raw native SDK event solvers retain separate endpoint probes; these probes
cannot certify the native solver's unobservable internal evaluations.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from fatebridge.core.physical_source_observation import (
    _POLICY,
    DataFilePolicy,
    current_policy,
)


@contextmanager
def data_file_policy(mode: str) -> Iterator[DataFilePolicy | None]:
    if mode not in {"auto", "require_data_files"}:
        raise ValueError("ephemeris_policy must be auto or require_data_files")
    active = current_policy()
    if active is not None or mode == "auto":
        yield active
        return
    from fatebridge.core.ephemeris_runtime import lock_ephemeris_configuration, swe

    state = DataFilePolicy()
    token = _POLICY.set(state)
    try:
        if swe is None:
            state.fail("required_data_files_unavailable")
        with lock_ephemeris_configuration():
            yield state
            state.finish()
    finally:
        _POLICY.reset(token)
