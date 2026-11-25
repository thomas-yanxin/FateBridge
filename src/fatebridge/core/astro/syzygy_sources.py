"""Observed native sources for every accepted prenatal-lunation sample."""

from __future__ import annotations

from typing import Any, Dict

from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError


class SyzygySourceTrace:
    """Keep valid model handoffs visible, without relabelling the root's accuracy.

    A search can cross a compressed-file edge and legitimately use Moshier.
    Its latest factor context alone cannot describe all preceding samples.
    Native file slots remain observed contexts, not an atomic read-set proof.
    """

    def __init__(self) -> None:
        self.selected = configured_ephemeris_path()
        self.physical = PhysicalEphemerisTrace()
        self.contexts: Dict[tuple, Dict[str, Any]] = {}
        self.models: Dict[str, set[str]] = {}

    def observe(self, body_id: int, flags: int, epoch_tt: float, stage: str) -> None:
        assert_physical_configuration(self.selected)
        model = runtime.ephemeris_model_from_retflag(flags)
        if model not in {"swieph", "moshier", "jpl"}:
            raise EphemerisSourceError("coordinate_contract_changed")
        body = "Sun" if body_id == runtime.swe.SUN else "Moon"
        context = self.physical.observe(body, model)
        self.models.setdefault(body, set()).add(model)
        key = body, stage, model, context["status"], tuple(context["file_ids"])
        if key not in self.contexts:
            self.contexts[key] = {
                "body": body,
                "stage": stage,
                **context,
                "sample_count": 0,
                "minimum_jd_tt": epoch_tt,
                "maximum_jd_tt": epoch_tt,
            }
        row = self.contexts[key]
        row["sample_count"] += 1
        row["minimum_jd_tt"] = min(row["minimum_jd_tt"], epoch_tt)
        row["maximum_jd_tt"] = max(row["maximum_jd_tt"], epoch_tt)

    def finish(self) -> Dict[str, Any]:
        assert_physical_configuration(self.selected)
        physical = self.physical.finish()
        return {
            "method_id": "prenatal_lunation_observed_sources_v1",
            "models_by_body": {
                key: sorted(value) for key, value in self.models.items()
            },
            "models_stable": all(len(value) == 1 for value in self.models.values()),
            "sample_contexts": list(self.contexts.values()),
            "physical_ephemeris_source": physical,
            "absolute_accuracy_certified": False,
            "scope": (
                "Accepted tropical search and event-longitude calls, plus the native "
                "Lahiri display call when requested. Sample counts are native calls, "
                "not independent observations. Source changes remain visible; no "
                "uniform-model continuity or absolute event accuracy certificate. "
                "Physical by_factor retains the last observed context for each body; "
                "sample_contexts preserves all observed contexts. Native file slots "
                "are not a complete dependency/read-set proof."
            ),
            "note_zh": (
                "出生前朔望已记录实际调用的星历来源；models_stable=false表示搜索或显示"
                "期间发生模型切换，不能把出生历元的星历来源概括为整个朔望搜索来源。"
                "数值残差、调用次数及文件散列均不证明事件的绝对天文精度。"
            ),
        }
