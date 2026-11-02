"""Bind actual worker clock observations to every returned Human Design clock."""

import json
from functools import wraps
from typing import Any, Callable

from fatebridge.core.astro.clock_observation import observer
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import timezone_rules_metadata

METHOD = "human_design_observed_clock_conversions_v1"
SCOPE = "记录本次工作进程实际完成的民用钟到TT/UT1、四次DeltaT逆迭代及TT显示标签，并回放其内部关系；重复记录去重。不认证原生执行真实性、实测UT1、出生记录、物理精度、完整原典或现实预测，也不声称覆盖C库内部调用。"
INPUT_KEYS = (
    "birth_year",
    "birth_month",
    "birth_day",
    "birth_hour",
    "birth_minute",
    "birth_second",
    "birth_timezone",
)


def observe_human_design_clocks(
    function: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    @wraps(function)
    def guarded(*args: Any, **kwargs: Any) -> dict[str, Any]:
        timezone_rules = timezone_rules_metadata(kwargs["birth_timezone"])
        events: dict[str, dict[str, Any]] = {}

        def observe(event: dict[str, Any]) -> None:
            key = json.dumps(
                event, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            events.setdefault(key, event)

        token = observer.set(observe)
        try:
            result = function(*args, **kwargs)
        finally:
            observer.reset(token)
        if timezone_rules_metadata(kwargs["birth_timezone"]) != timezone_rules:
            # Also retain the operation's original identity if another caller
            # explicitly clears or evicts the shared parser cache mid-flight.
            raise EphemerisSourceError("timezone_rules_changed")
        result["clock_evidence"] = {
            "method_id": METHOD,
            "input": {
                key: kwargs.get(key, 0) if key == "birth_second" else kwargs[key]
                for key in INPUT_KEYS
            },
            "cycle_reference_datetime": kwargs.get("cycle_reference_datetime"),
            "timezone_rules": timezone_rules,
            "conversions": list(events.values()),
            "native_execution_authenticated": False,
            "measured_UT1_certified": False,
            "physical_accuracy_certified": False,
            "scope": SCOPE,
        }
        if kwargs.get("compare_cycle_origins", False):
            result["clock_evidence"]["compare_cycle_origins"] = True
        return result

    return guarded
