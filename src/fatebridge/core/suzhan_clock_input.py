"""Full-result clock binding, before any optional transport projection."""

from typing import Any, Optional

from pydantic import BaseModel


def require_clock_input_binding(
    result: dict[str, Any], *, request: Optional[BaseModel] = None
) -> None:
    inputs = result.get("input_normalized")
    if not isinstance(inputs, dict) or "time" not in inputs:
        raise ValueError("缺少钟时输入事实")
    unknown = inputs["time"] is None
    if request is not None and unknown != (getattr(request, "time") is None):
        raise ValueError("未知钟时状态与请求不符")
    if "chart" not in result or "astronomy" not in result:
        raise ValueError("缺少星图或天文计算层")
    params = result.get("params") or {}
    calendar = (result.get("sukuyo") or {}).get("calendar") or {}
    if not unknown:
        if not isinstance(result["chart"], dict) or not result["chart"]:
            raise ValueError("已知钟时缺少星图")
        if calendar.get("birth_time_known") is not True:
            raise ValueError("已知钟时与历日钟时状态不符")
        if (
            params.get("calculationMode") == "calendar_date_only"
            or params.get("su28Method") == "not_computed_birth_time_unknown"
        ):
            raise ValueError("已知钟时不得声明为未知钟时模式")
        for key in ("birthTimeKnown", "chartComputed"):
            if key in params and params[key] is not True:
                raise ValueError("已知钟时的计算声明相反")
        if "birthTimeImputed" in params and params["birthTimeImputed"] is not False:
            raise ValueError("已知钟时不得声明补造钟时")
        if "astronomyComputed" in params and params["astronomyComputed"] is not (
            result["astronomy"] is not None
        ):
            raise ValueError("天文层与计算声明不符")
        layers = (result.get("validation") or {}).get("calculation_layers")
        if layers is not None and (
            not isinstance(layers, dict)
            or layers.get("calendar") != calendar.get("status")
            or layers.get("chart") != "computed"
            or layers.get("astronomy")
            != ("computed" if result["astronomy"] is not None else "not_computed")
        ):
            raise ValueError("已知钟时的计算层状态相反")
        return
    if result["chart"] is not None or result["astronomy"] is not None:
        raise ValueError("未知钟时不得输出瞬时星图或天文坐标")
    expected = {
        "calculationMode": "calendar_date_only",
        "birthTimeKnown": False,
        "birthTimeImputed": False,
        "coordinatesApplied": False,
        "chartComputed": False,
        "astronomyComputed": False,
        "su28Method": "not_computed_birth_time_unknown",
        "su28AstronomicalAccuracy": "not_computed",
    }
    if any(
        k not in params or type(params[k]) is not type(v) or params[k] != v
        for k, v in expected.items()
    ):
        raise ValueError("未知钟时的计算声明不符")
    if calendar.get("birth_time_known") is not False:
        raise ValueError("历日候选未保留未知钟时")
    layers = (result.get("validation") or {}).get("calculation_layers")
    if layers != {
        "calendar": calendar.get("status"),
        "chart": "not_computed_birth_time_unknown",
        "astronomy": "not_computed_birth_time_unknown",
    }:
        raise ValueError("历日和天文层的验证状态不符")
