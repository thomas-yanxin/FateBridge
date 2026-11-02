"""
Lightweight runtime metadata helpers for REST and MCP responses.

``tool_name`` is supplied authoritatively by the transport from the central
``ToolSpec`` (``spec.run_metadata_name``), so it is never inferred from payload
shape. This module only stamps the metadata envelope and detects the runtime
engine that produced a result.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Iterable, Set
from uuid import uuid4

DEFAULT_ENGINE = "fatebridge-offline"


def _enqueue_children(queue: Deque[Any], values: Iterable[Any]) -> None:
    for value in values:
        if isinstance(value, (dict, list, tuple)):
            queue.append(value)


def resolve_runtime_engine(payload: Dict[str, Any]) -> str:
    queue: Deque[Any] = deque([payload])
    seen_dict_ids: Set[int] = set()

    while queue:
        current = queue.popleft()
        if isinstance(current, dict):
            current_id = id(current)
            if current_id in seen_dict_ids:
                continue
            seen_dict_ids.add(current_id)

            direct_engine = current.get("engine")
            if isinstance(direct_engine, str) and direct_engine:
                return direct_engine

            for profile_key in ("relationship_profile", "chart_profile"):
                profile = current.get(profile_key)
                if isinstance(profile, dict):
                    engine_backend = profile.get("engine_backend")
                    if isinstance(engine_backend, str) and engine_backend:
                        return engine_backend
                    engine_precision = profile.get("engine_precision")
                    if isinstance(engine_precision, str) and engine_precision:
                        return engine_precision

            _enqueue_children(queue, current.values())
            continue

        if isinstance(current, (list, tuple)):
            _enqueue_children(queue, current)

    return DEFAULT_ENGINE


def engine_is_approximate(engine: str) -> bool:
    """Whether the engine name itself declares an approximation.

    Lets an agent branch on degraded precision without string-matching the
    backend name or the Chinese precision label. Non-astro tools report
    ``DEFAULT_ENGINE`` and are deterministic in their own domain, so they are
    not "approximate"; only the orbital-approximation and mixed-precision astro
    backends are flagged here. Actual ephemeris and Feng Shui calendar
    resolution records are checked separately in ``attach_run_metadata``.
    """
    lowered = engine.lower()
    return "approximate" in lowered or lowered.startswith("mixed")


_DOWNGRADED_EPHEMERIS_MODELS = frozenset(
    {"moshier", "mixed", "fatebridge_analytic_solar_v1"}
)


def _ephemeris_is_downgraded(payload: Dict[str, Any]) -> bool:
    """Whether any chart in the payload was served by a degraded ephemeris model.

    The model actually used per run lives in ``chart_profile.ephemeris_model``
    (derived from swisseph's ``retflag``). ``engine_backend`` /
    ``engine_precision`` stay constant whether or not Swiss Ephemeris data files
    were present, so a silent downgrade to the built-in Moshier model (no ``.se1``
    files) is *only* visible here. Without consulting it, a chart computed from
    Moshier would falsely report full precision via ``engine_is_approximate``.
    """
    queue: Deque[Any] = deque([payload])
    seen_dict_ids: Set[int] = set()

    while queue:
        current = queue.popleft()
        if isinstance(current, dict):
            current_id = id(current)
            if current_id in seen_dict_ids:
                continue
            seen_dict_ids.add(current_id)

            model = current.get("ephemeris_model")
            if isinstance(model, str) and model.lower() in _DOWNGRADED_EPHEMERIS_MODELS:
                return True

            _enqueue_children(queue, current.values())
            continue

        if isinstance(current, (list, tuple)):
            _enqueue_children(queue, current)

    return False


def _fengshui_calendar_is_approximate(payload: Dict[str, Any]) -> bool:
    """Use actual solar-term resolution records, not dependency availability.

    Only called for Feng Shui tools. Statistical WMM uncertainty and caller
    evidence are not a degraded calendar provider. This also covers birth-date
    boundaries and historical house-period endpoints, not just annual layers.
    """
    queue: Deque[Any] = deque([payload])
    seen: Set[int] = set()
    while queue:
        current = queue.popleft()
        if isinstance(current, dict):
            if id(current) in seen:
                continue
            seen.add(id(current))
            if (
                current.get("approximate") is True
                and isinstance(current.get("provider"), str)
                and isinstance(current.get("moment"), str)
                and "precision_scope" in current
            ):
                return True
            _enqueue_children(queue, current.values())
        elif isinstance(current, (list, tuple)):
            _enqueue_children(queue, current)
    return False


def attach_run_metadata(
    payload: Dict[str, Any],
    *,
    tool_name: str,
) -> Dict[str, Any]:
    existing = payload.get("run_metadata")
    if isinstance(existing, dict):
        return payload

    run_id = uuid4().hex
    trace_id = uuid4().hex
    engine = resolve_runtime_engine(payload)
    approximate = (
        engine_is_approximate(engine)
        or _ephemeris_is_downgraded(payload)
        or (
            tool_name.startswith("fengshui_")
            and _fengshui_calendar_is_approximate(payload)
        )
    )
    enriched = dict(payload)
    enriched["run_metadata"] = {
        "run_id": run_id,
        "trace_id": trace_id,
        "tool_name": tool_name,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "engine": engine,
        "engine_is_approximate": approximate,
    }
    return enriched
