"""Small, explicitly fictional starter inputs shared by all transports."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from fatebridge.application.tool_spec import ToolSpec


@lru_cache(maxsize=1)
def _examples() -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data/agent_examples.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def example_input(spec: ToolSpec) -> Optional[Dict[str, Any]]:
    bundle = _examples()
    source = bundle["tools"].get(spec.key)
    if source is None:
        return None
    if isinstance(source, str):
        source = bundle["subjects"][source]
    inputs = {
        k: deepcopy(v)
        for k, v in source.items()
        if k in spec.request_model.model_fields
    }
    # Fail loudly on stale published examples; never substitute fabricated input.
    spec.request_model.model_validate(inputs)
    return inputs


def example_context() -> Dict[str, Any]:
    """Example facts are transport fixtures, never missing user information."""
    return {
        "fictional": True,
        "purpose": "schema_and_transport_demo",
        "use_as_user_default": False,
    }


def suggested_fields(
    spec: ToolSpec, *, view: Optional[str] = None
) -> Optional[List[str]]:
    """Small first-response views; callers can expand for a deeper question."""
    if view is not None:
        views = evidence_views(spec) or {}
        if view not in views:
            raise ValueError(f"Unknown evidence view for {spec.key}: {view}")
        return list(views[view]["fields"])
    fields = _examples().get("suggested_fields", {}).get(spec.key)
    return list(fields) if fields is not None else None


def evidence_views(spec: ToolSpec) -> Optional[Dict[str, Any]]:
    """Published task cards, copied into ``fields`` rather than request options.

    These views never alter execution or ``fields=None`` full-result semantics.
    Relationship aliases come from the engine's normalization tables so callers
    cannot silently turn a named mode into another method's evidence view.
    """
    key = "astro_relative_chart" if spec.key == "astro_relative" else spec.key
    views = deepcopy(_examples().get("evidence_views", {}).get(key))
    from fatebridge.core.requests.western_policy import supports_western_policy_model

    if supports_western_policy_model(spec.request_model):
        views = views or {}
        views["data_files"] = {
            "fields": ["ephemeris_data_policy"],
            "scope": "Available when ephemeris_policy=require_data_files. Read the actual observed physical models, file hashes, reference zeros and private-worker reports. Native event-internal reads, fixed-star catalogue formulae and absolute accuracy are not certified. This card does not set the input policy.",
        }
    if key in {"meihua_cast", "meihua_analysis"}:
        views = views or {}
        fields = [
            "meihua.body_trigram",
            "meihua.use_trigram",
            "interpretation.topic_reading.chapter_qualifications.qualitative_motion",
            "summary",
        ]
        if key == "meihua_cast":
            fields.append("interpretation.casting_readings")
        views["chapter_qualitative_motion"] = {
            "fields": fields,
            "scope": "Requires interpretation_topic=travel or traveler. A declared NLC1925 grammatical reading selects the candidate's initial body for travel and initial use for traveler. Preserve 多 as an unquantified qualifier; distinguish it from inner-role motion and field observations. Existing occurrence-count readings remain unresolved. No probability, route, location, safety or return-time certificate.",
        }
    if views is not None and key == "astro_relative_chart":
        from fatebridge.core.astro.reference import (
            RELATIVE_MODE_EXACT_ALIASES,
            RELATIVE_MODE_FALLBACK_ALIASES,
            RELATIVE_MODE_NUMERIC_MAP,
        )

        aliases: Dict[Any, str] = {
            **RELATIVE_MODE_FALLBACK_ALIASES,
            **RELATIVE_MODE_EXACT_ALIASES,
            **RELATIVE_MODE_NUMERIC_MAP,
        }
        for name, card in views.items():
            if "relative_mode" in card:
                card["aliases"] = [a for a, target in aliases.items() if target == name]
    return cast(Optional[Dict[str, Any]], views)


def call_guidance(spec: ToolSpec) -> Optional[Dict[str, Any]]:
    """Frame semantics shared by preloaded contracts and protocol discovery."""
    key = "astro_relative_chart" if spec.key == "astro_relative" else spec.key
    guidance = _examples().get("call_guidance", {}).get(key)
    return cast(Dict[str, Any], deepcopy(guidance)) if guidance is not None else None
