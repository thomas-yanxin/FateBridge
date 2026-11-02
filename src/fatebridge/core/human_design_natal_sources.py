"""Observed file identities for natal, solar-root and interval native calls.

These are post-call library contexts, not an atomic read set or a certificate
that supplied coordinates or speed are physically accurate.
"""

from __future__ import annotations

import math
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from fatebridge.core.astro import runtime
from fatebridge.core.human_design_cycle_sources import (
    CycleSourceTrace,
    cycle_source_summary,
)
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.utils.errors import EphemerisSourceError

BODIES = {
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "NorthNode",
}
ROLES = {"activation", "solar_root", "node_reference", "root_bracket_activation"}
METHOD = "human_design_natal_native_file_contexts_v1"
SOURCE = "https://www.astro.com/swisseph/swephprg.htm"
SCOPE = "逐次本命、设计根、生时范围、交点及整盘后端对照的原生位置求值后观察文件上下文；周期搜索另读cycle_context.source_evidence，历法与DeltaT调用不在此计数。固定路径策略、文件身份、同天体同后端同slot的DE版本，并在结束重核已识别文件哈希。未能识别的辅助slot单列，整体身份不完整；解析平交点与Moshier内置算法不伪造文件依赖；观察次数不是独立样本、覆盖率或概率。不是完整原子读取集合、原生执行真实性、星历物理精度或连续区间认证。"


class NatalSourceTrace(CycleSourceTrace):
    """Keep the existing file identity checks across all natal computation roles."""

    def __init__(self, *, require_swiss_files: bool = False) -> None:
        super().__init__()
        self._require_files = require_swiss_files

    def observe_native(
        self, body: str, tt: float, flags: int, role: str, analytical: bool
    ) -> None:
        self.check_configuration()
        model = position_flag_model(flags)
        if (
            body not in BODIES
            or role not in ROLES
            or (role == "solar_root" and body != "Sun")
            or (role == "node_reference" and body != "NorthNode")
            or (analytical and body != "NorthNode")
            or not math.isfinite(tt)
        ):
            raise ValueError("Invalid Human Design native source observation")
        getter = getattr(runtime.swe, "get_current_file_data", None)
        ids = []
        unresolved = []
        if analytical:
            status = "analytical_mean_node"
        elif model == "moshier":
            status = "library_builtin"
        elif getter is None:
            status = "identity_unavailable"
            unresolved = [0, 1] if model == "swieph" else [0]
        else:
            for slot in [0, 1] if model == "swieph" else [0]:
                metadata = getter(slot)
                # Failed auxiliary lookups may retain a filename and zero range.
                # Preserve this as unresolved, never invent its file identity.
                unusable = not metadata[0] or (
                    model == "swieph"
                    and (
                        not metadata[1] < metadata[2]
                        or not metadata[3] > 0
                        or not Path(metadata[0]).is_file()
                    )
                )
                if unusable:
                    unresolved.append(slot)
                    continue
                identity = self._file(slot, metadata, jpl=model == "jpl" and slot == 0)
                edition = self._files[identity]["de_number"]
                key = body, model, slot
                if key in self._editions and self._editions[key] != edition:
                    raise EphemerisSourceError("edition_changed")
                self._editions[key] = edition
                ids.append(identity)
            status = "file_contexts_observed" if ids else "identity_unavailable"
        if self._require_files and unresolved:
            raise EphemerisSourceError("unavailable_during")
        key_context = body, role, model, status, tuple(sorted(ids)), tuple(unresolved)
        if key_context not in self._context_indices:
            self._context_indices[key_context] = len(self._contexts)
            self._contexts.append(
                {
                    "body": body,
                    "role": role,
                    "native_return_flag_model": model,
                    "status": status,
                    "file_ids": sorted(ids),
                    "unresolved_slots": unresolved,
                    "observed_evaluation_count": 0,
                    "minimum_jd_tt": tt,
                    "maximum_jd_tt": tt,
                }
            )
        context = self._contexts[self._context_indices[key_context]]
        context["observed_evaluation_count"] += 1
        context["minimum_jd_tt"] = min(context["minimum_jd_tt"], tt)
        context["maximum_jd_tt"] = max(context["maximum_jd_tt"], tt)

    def finish(self) -> dict[str, Any]:
        result = super().finish()
        unidentified = any(
            c["status"] == "identity_unavailable" or c["unresolved_slots"]
            for c in self._contexts
        )
        return {
            **result,
            "method_id": METHOD,
            "status": (
                "identity_incomplete"
                if unidentified
                else "observed_contexts_endpoint_verified"
            ),
            "has_unidentified_sources": unidentified,
            "source_url": SOURCE,
            "observed_native_position_evaluations": sum(
                c["observed_evaluation_count"] for c in self._contexts
            ),
            "native_execution_authenticated": False,
            "scope": SCOPE,
        }


def natal_source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {
        **cycle_source_summary(source),
        "source_url": SOURCE,
        "scope": SCOPE,
        "context_count": len(source["contexts"]),
        "unidentified_context_count": sum(
            bool(c["status"] == "identity_unavailable" or c["unresolved_slots"])
            for c in source["contexts"]
        ),
        "observed_native_position_evaluations": source[
            "observed_native_position_evaluations"
        ],
        "native_execution_authenticated": False,
    }


_ACTIVE: ContextVar[NatalSourceTrace | None] = ContextVar(
    "human_design_natal_source_trace", default=None
)


def observe_native_source(
    body: str, tt: float, flags: int, *, role: str, analytical: bool = False
) -> None:
    trace = _ACTIVE.get()
    if trace is not None:
        trace.observe_native(body, tt, flags, role, analytical)


def guard_natal_sources(
    function: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    @wraps(function)
    def guarded(*args: Any, **kwargs: Any) -> dict[str, Any]:
        trace = NatalSourceTrace(
            require_swiss_files=kwargs.get("require_swiss_files", False)
        )
        token = _ACTIVE.set(trace)
        try:
            result = function(*args, **kwargs)
            result["ephemeris_source_evidence"] = trace.finish()
            result["ephemeris_source_summary"] = natal_source_summary(
                result["ephemeris_source_evidence"]
            )
            return result
        finally:
            _ACTIVE.reset(token)

    return guarded
