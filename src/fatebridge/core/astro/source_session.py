"""One managed configuration and endpoint-verified trace per calculation.

Clock inversions and physical positions can share the trace without hashing a
large JPL kernel for each iteration. Native contexts are not atomic read sets.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, Iterator, ParamSpec, TypeVar

from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.ephemeris_runtime import (
    configured_ephemeris_path,
    lock_ephemeris_configuration,
)
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError

_P = ParamSpec("_P")
_R = TypeVar("_R")


class EphemerisSourceSession:
    def __init__(self) -> None:
        self.path = configured_ephemeris_path()
        self.jpl = configured_jpl_file()
        self.trace = PhysicalEphemerisTrace()
        self.memo: dict[tuple[Any, ...], Any] = {}

    def check(self) -> None:
        if (
            configured_ephemeris_path() != self.path
            or configured_jpl_file() != self.jpl
        ):
            raise EphemerisSourceError("physical_configuration_changed")


_SESSION: ContextVar[EphemerisSourceSession | None] = ContextVar(
    "physical_source_session", default=None
)


def current_source_session() -> EphemerisSourceSession | None:
    return _SESSION.get()


@contextmanager
def source_session(
    *, restore_native_path: bool = True
) -> Iterator[EphemerisSourceSession]:
    active = current_source_session()
    if active is not None:
        active.check()
        yield active
        active.check()
        return
    with (
        runtime.preserve_ephemeris_path()
        if restore_native_path
        else lock_ephemeris_configuration()
    ):
        session = EphemerisSourceSession()
        token = _SESSION.set(session)
        try:
            yield session
            session.check()
            session.trace.finish()
        except Exception:
            # A native damaged-file exception may precede normal verification.
            # Prefer a verified change diagnosis; otherwise preserve the error.
            session.check()
            session.trace.finish()
            raise
        finally:
            _SESSION.reset(token)


def coherent_ephemeris_sources(function: Callable[_P, _R]) -> Callable[_P, _R]:
    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with source_session():
            return function(*args, **kwargs)

    return wrapped
