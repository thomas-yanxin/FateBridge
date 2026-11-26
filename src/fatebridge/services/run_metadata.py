"""Attribute runtime engine and approximation facts to an execution receipt."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import JsonValue

from fatebridge.application.tool_spec import ApproximationDetector, ServiceResult

DEFAULT_ENGINE = "fatebridge-offline"


@dataclass(frozen=True, kw_only=True)
class RuntimeInspection:
    engine: str
    has_downgraded_model: bool


DOWNGRADED_EPHEMERIS_MODELS = frozenset(
    {
        "moshier",
        "mixed",
        "fatebridge_analytic_solar_v1",
        "fatebridge_complete_moshier_solar_v1",
        "fatebridge_complete_moshier_solar_v2",
        # note (ephemeris): Bounded DE441 source coverage keeps the downgraded status.
        "fatebridge_de441_solar_v1",
    }
)


def _inspect_runtime(
    payload: dict[str, JsonValue],
    *,
    should_check_downgrade: bool = True,
    approximate_record: ApproximationDetector | None = None,
) -> RuntimeInspection:
    """Extract runtime engine and detect downgraded ephemeris models in one BFS pass."""
    queue: deque[JsonValue] = deque([payload])
    seen_dictionary_ids: set[int] = set()
    engine: str | None = None
    has_downgraded_model = False

    while queue:
        current = queue.popleft()
        if isinstance(current, dict):
            record_identity = id(current)
            if record_identity in seen_dictionary_ids:
                continue
            seen_dictionary_ids.add(record_identity)

            if engine is None:
                direct_engine = current.get("engine")
                if isinstance(direct_engine, str) and direct_engine:
                    engine = direct_engine
                else:
                    for profile_field in ("relationship_profile", "chart_profile"):
                        profile = current.get(profile_field)
                        if isinstance(profile, dict):
                            engine_backend = profile.get("engine_backend")
                            if isinstance(engine_backend, str) and engine_backend:
                                engine = engine_backend
                                break
                            engine_precision = profile.get("engine_precision")
                            if isinstance(engine_precision, str) and engine_precision:
                                engine = engine_precision
                                break
                if engine is not None and not should_check_downgrade:
                    return RuntimeInspection(engine=engine, has_downgraded_model=False)

            if should_check_downgrade and not has_downgraded_model:
                model = current.get("ephemeris_model")
                has_downgraded_model = (
                    isinstance(model, str)
                    and model.lower() in DOWNGRADED_EPHEMERIS_MODELS
                ) or (approximate_record is not None and approximate_record(current))
            if engine is not None and has_downgraded_model:
                return RuntimeInspection(engine=engine, has_downgraded_model=True)

            queue.extend(
                value
                for value in current.values()
                if isinstance(value, (dict, list, tuple))
            )
            continue

        if isinstance(current, (list, tuple)):
            queue.extend(
                value for value in current if isinstance(value, (dict, list, tuple))
            )

    return RuntimeInspection(
        engine=engine or DEFAULT_ENGINE, has_downgraded_model=has_downgraded_model
    )


def resolve_runtime_engine(payload: dict[str, JsonValue]) -> str:
    return _inspect_runtime(payload, should_check_downgrade=False).engine


def engine_is_approximate(engine: str) -> bool:
    """Identify orbital-approximation and mixed-precision engine labels."""
    lowered = engine.lower()
    return "approximate" in lowered or lowered.startswith("mixed")


def build_run_metadata(
    payload: dict[str, JsonValue],
    *,
    tool_name: str,
    approximate_record: ApproximationDetector | None = None,
) -> dict[str, JsonValue]:
    existing = payload.get("run_metadata")
    if isinstance(existing, dict):
        return existing

    run_id = uuid4().hex
    inspection = _inspect_runtime(payload, approximate_record=approximate_record)
    return {
        "run_id": run_id,
        "tool_name": tool_name,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "engine": inspection.engine,
        "engine_is_approximate": engine_is_approximate(inspection.engine)
        or inspection.has_downgraded_model,
    }


def attach_run_metadata(
    payload: dict[str, JsonValue],
    *,
    tool_name: str,
    approximate_record: ApproximationDetector | None = None,
) -> ServiceResult:
    if isinstance(payload.get("run_metadata"), dict):
        return payload
    return {
        **payload,
        "run_metadata": build_run_metadata(
            payload, tool_name=tool_name, approximate_record=approximate_record
        ),
    }
