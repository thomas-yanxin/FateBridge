"""Full-result clock binding, before any optional transport projection."""

from typing import Any

from fatebridge.core.requests.divination import SuZhanRequest


def require_clock_input_binding(
    result: dict[str, Any], *, request: object = None
) -> None:
    inputs = result.get("analysis_context")
    if not isinstance(inputs, dict) or "time" not in inputs:
        raise ValueError("缺少钟时输入事实")
    clock_known = inputs["time"] is not None
    has_coordinates = any(
        inputs.get(key) is not None for key in ("latitude", "longitude")
    )
    if isinstance(request, SuZhanRequest) and (
        clock_known != (request.time is not None)
        or has_coordinates
        != any(value is not None for value in (request.latitude, request.longitude))
    ):
        raise ValueError("钟时或坐标状态与请求不符")
    if "chart" not in result or "astronomy" not in result:
        raise ValueError("缺少星图或天文计算层")
    params = result.get("params") or {}
    calendar = (result.get("sukuyo") or {}).get("calendar") or {}
    layers = (result.get("validation") or {}).get("calculation_layers")
    if calendar.get("birth_time_known") is not clock_known:
        raise ValueError("历日钟时状态与输入不符")
    if clock_known and has_coordinates:
        if not isinstance(result["chart"], dict) or not result["chart"]:
            raise ValueError("已知钟时和坐标缺少星图")
        if params.get("calculationMode") in (
            "calendar_date_only",
            "calendar_with_clock",
        ) or params.get("su28Method") in (
            "not_computed_birth_time_unknown",
            "not_computed_missing_coordinates",
        ):
            raise ValueError("星图不得声明为只计算历日")
        for key in ("birthTimeKnown", "chartComputed"):
            if key in params and params[key] is not True:
                raise ValueError("星图的计算声明相反")
        if "birthTimeImputed" in params and params["birthTimeImputed"] is not False:
            raise ValueError("已知钟时不得声明补造钟时")
        astronomy_computed = result["astronomy"] is not None
        if (
            "astronomyComputed" in params
            and params["astronomyComputed"] is not astronomy_computed
        ):
            raise ValueError("天文层与计算声明不符")
        if (
            not isinstance(layers, dict)
            or layers.get("calendar") != calendar.get("status")
            or layers.get("chart") != "computed"
            or layers.get("astronomy")
            != ("computed" if astronomy_computed else "not_computed")
        ):
            raise ValueError("星图与计算层状态不符")
        return
    if result["chart"] is not None or result["astronomy"] is not None:
        raise ValueError("历日模式不得输出星图或瞬时天文坐标")
    layer_status = (
        "not_computed_missing_coordinates"
        if clock_known
        else "not_computed_birth_time_unknown"
    )
    expected = {
        "calculationMode": (
            "calendar_with_clock" if clock_known else "calendar_date_only"
        ),
        "birthTimeKnown": clock_known,
        "birthTimeImputed": False,
        "coordinatesApplied": False,
        "chartComputed": False,
        "astronomyComputed": False,
        "su28Method": layer_status,
        "su28AstronomicalAccuracy": "not_computed",
    }
    if any(
        k not in params or type(params[k]) is not type(v) or params[k] != v
        for k, v in expected.items()
    ):
        raise ValueError("历日模式的计算声明不符")
    if layers != {
        "calendar": calendar.get("status"),
        "chart": layer_status,
        "astronomy": layer_status,
    }:
        raise ValueError("历日和天文层的验证状态不符")
