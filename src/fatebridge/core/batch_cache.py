"""Request-scoped memoization cache for shared primitives inside a batch execution."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
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
                return deepcopy(cached) if copy_result else cached  # type: ignore[return-value]
            result = func(*args, **kwargs)
            cache[key] = deepcopy(result) if copy_result else result
            return result

        return wrapper

    return decorator
