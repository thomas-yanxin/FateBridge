"""Request-scoped memoization cache for shared primitives inside a batch execution."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from decimal import Decimal
from fractions import Fraction
from functools import wraps
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

_BATCH_CACHE: ContextVar[dict[tuple[object, ...], object] | None] = ContextVar(
    "fatebridge_batch_cache",
    default=None,
)


def freeze_cache_value(value: object) -> object:
    """Convert nested mappings and sequences into hashable canonical cache keys."""
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return value
    if isinstance(value, Mapping):
        return tuple(
            (str(k), freeze_cache_value(v))
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        )
    if isinstance(value, (tuple, list)):
        return tuple(freeze_cache_value(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((freeze_cache_value(item) for item in value), key=repr))
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return freeze_cache_value(value.model_dump(mode="json"))
    return repr(value)


def metaphysics_seed_key(seed: Any) -> tuple[object, ...]:
    """Canonical hashable key for a MetaphysicsSeed across separate builders."""
    return (
        seed.input_datetime.isoformat(),
        seed.clock.ordinal,
        seed.clock.microseconds_of_day,
        seed.timezone,
        seed.longitude,
        seed.applied_true_solar,
        seed.total_correction_minutes,
        seed.input_offset_visible,
        freeze_cache_value(seed.pillars),
    )


@contextmanager
def batch_cache_scope() -> Iterator[dict[tuple[object, ...], object]]:
    """Open an isolated per-batch memoization cache scoped to the current context."""
    cache: dict[tuple[object, ...], object] = {}
    token = _BATCH_CACHE.set(cache)
    try:
        yield cache
    finally:
        _BATCH_CACHE.reset(token)


_IMMUTABLE_CACHE_TYPES = (
    type(None),
    bool,
    int,
    float,
    str,
    bytes,
    Fraction,
    Decimal,
    datetime,
    date,
    time,
    timedelta,
    tzinfo,
)


def _clone_cached_value(value: Any) -> Any:
    """Clone cached values without pickling ZoneInfo file-stream tzinfo objects."""
    if isinstance(value, _IMMUTABLE_CACHE_TYPES):
        return value
    if type(value) is dict:
        return {k: _clone_cached_value(v) for k, v in value.items()}
    if type(value) is list:
        return [_clone_cached_value(item) for item in value]
    if type(value) is set:
        return {_clone_cached_value(item) for item in value}
    if type(value) is frozenset:
        return frozenset(_clone_cached_value(item) for item in value)
    if isinstance(value, tuple):
        if hasattr(type(value), "_fields"):
            return type(value)(*(_clone_cached_value(item) for item in value))
        return tuple(_clone_cached_value(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        clone = object.__new__(type(value))
        for dc_field in fields(value):
            object.__setattr__(
                clone,
                dc_field.name,
                _clone_cached_value(getattr(value, dc_field.name)),
            )
        return clone
    if hasattr(type(value), "model_fields") and hasattr(value, "model_copy"):
        updates = {
            name: _clone_cached_value(getattr(value, name))
            for name in type(value).model_fields
        }
        return value.model_copy(update=updates)
    return deepcopy(value)


def batch_cached(
    namespace: str,
    key_fn: Callable[..., object],
    *,
    copy_result: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Memoize a deterministic helper while a batch_cache_scope is active."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            cache = _BATCH_CACHE.get()
            if cache is None:
                return func(*args, **kwargs)
            key = (namespace, key_fn(*args, **kwargs))
            if key in cache:
                cached = cache[key]
                return _clone_cached_value(cached) if copy_result else cached  # type: ignore[return-value]
            result = func(*args, **kwargs)
            cache[key] = _clone_cached_value(result) if copy_result else result
            return result

        return wrapper

    return decorator
