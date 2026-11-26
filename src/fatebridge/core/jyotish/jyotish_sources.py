"""Minimal in-process stub for untouched services/astrology.py until Wave 3 deletion."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def coherent_sources(function: F) -> F:
    return function


def coherent_india_call(function: F) -> F:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        return function(*args, **kwargs)

    return wrapped  # type: ignore[return-value]
