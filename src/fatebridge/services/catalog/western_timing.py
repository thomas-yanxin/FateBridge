"""Western timing tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.tool_spec import CompactView, ServiceResult, ToolSpec

_REQ_MODULE = "fatebridge.core.requests.western_timing"

calculate_western_timing_analysis = service_ref(
    "fatebridge.services.western_timing", "calculate_western_timing_analysis"
)


calculate_timing_tool = service_ref(
    "fatebridge.services.western_timing_tools", "calculate_timing_tool"
)


_DECENNIAL_PERIOD_FIELDS = frozenset(
    {
        "key",
        "level",
        "planet",
        "planet_label",
        "date",
        "nominal",
        "start",
        "end",
        "active",
    }
)


def _compact_decennial_period(period: ServiceResult | None) -> ServiceResult | None:
    if period is None:
        return None
    return {
        key: value for key, value in period.items() if key in _DECENNIAL_PERIOD_FIELDS
    }


def _compact_decennials(result: ServiceResult) -> ServiceResult:
    decennials = result["decennials"]
    return {
        **result,
        "decennials": {
            **decennials,
            "current_level_1": _compact_decennial_period(decennials["current_level_1"]),
            "current_level_2": _compact_decennial_period(decennials["current_level_2"]),
            "current_level_3": _compact_decennial_period(decennials["current_level_3"]),
        },
    }


def _compact_primary_directions(result: ServiceResult) -> ServiceResult:
    pd = result.get("primary_directions")
    if not isinstance(pd, dict):
        return result
    compact_pd = {
        k: v
        for k, v in pd.items()
        if k
        in {
            "method",
            "canonical_method",
            "time_key",
            "time_key_rate",
            "pd_type",
            "direction_mode",
            "pd_direction_mode",
            "current_age_years",
            "current_arc_degrees",
            "current_window",
            "past_window",
            "future_window",
            "exact_window",
            "skipped_circumpolar_count",
        }
    }
    compact_pd["timeline_preview"] = (pd.get("timeline") or [])[:15]
    return {**result, "primary_directions": compact_pd}


def _compact_zr(result: ServiceResult) -> ServiceResult:
    zr = result.get("zodiacal_releasing")
    if not isinstance(zr, dict):
        return result
    compact_zr = {"calculation_basis": zr.get("calculation_basis")}
    for track in ("spirit", "fortune", "eros"):
        t = zr.get(track)
        if not isinstance(t, dict):
            compact_zr[track] = t
            continue
        compact_zr[track] = {
            k: v
            for k, v in t.items()
            if k
            in {
                "lot",
                "release_start_sign",
                "angular_reference_sign",
                "current_level_1",
                "current_level_2",
                "current_level_3",
                "current_level_4",
                "status",
            }
        }
    return {**result, "zodiacal_releasing": compact_zr}


_COMPACT_CALCULATION_BASIS_FIELDS = frozenset(
    {
        "engine_backend",
        "ephemeris_model",
        "time_scale",
        "future_leap_seconds_assumed_unchanged",
    }
)


def _compact_return_chart(chart: ServiceResult) -> ServiceResult:
    compact = {
        k: v
        for k, v in chart.items()
        if k
        in {
            "return_datetime",
            "return_datetime_utc",
            "sun",
            "moon",
            "ascendant",
            "medium_coeli",
            "solver",
            "hits",
        }
    }
    cb = chart.get("calculation_basis")
    if isinstance(cb, dict):
        compact["calculation_basis"] = {
            k: v for k, v in cb.items() if k in _COMPACT_CALCULATION_BASIS_FIELDS
        }
    return compact


def _compact_western_timing(result: ServiceResult) -> ServiceResult:
    compact: ServiceResult = {
        k: v
        for k, v in result.items()
        if k in {"analysis_type", "analysis_context", "summary", "run_metadata"}
    }
    natal_ref = result.get("natal_reference")
    if isinstance(natal_ref, dict):
        compact["natal_reference"] = {
            k: v
            for k, v in natal_ref.items()
            if k in {"sect", "sun", "moon", "ascendant", "medium_coeli"}
        }
    returns = result.get("returns")
    if isinstance(returns, dict):
        compact["returns"] = {
            k: (_compact_return_chart(v) if isinstance(v, dict) else v)
            for k, v in returns.items()
        }
    transits = result.get("transits")
    if isinstance(transits, dict):
        ct = transits.get("current_transit")
        if isinstance(ct, dict):
            compact["transits"] = {
                "current_transit": {
                    k: (v[:12] if k == "hits" and isinstance(v, list) else v)
                    for k, v in ct.items()
                    if k
                    in {
                        "analysis_datetime",
                        "orb_limit",
                        "exact_orb_limit",
                        "house_emphasis",
                        "hits",
                        "exact_hits",
                    }
                }
            }
        else:
            compact["transits"] = transits
    directions = result.get("directions")
    if isinstance(directions, dict):
        compact_dirs: ServiceResult = {}
        if "secondary_progression" in directions:
            sp = directions["secondary_progression"]
            compact_dirs["secondary_progression"] = (
                {k: v for k, v in sp.items() if k != "calculation_basis"}
                if isinstance(sp, dict)
                else sp
            )
        if "solar_arc" in directions:
            compact_dirs["solar_arc"] = directions["solar_arc"]
        if "given_year" in directions:
            gy = directions["given_year"]
            compact_dirs["given_year"] = (
                {k: v for k, v in gy.items() if k != "monthly_profections"}
                if isinstance(gy, dict)
                else gy
            )
        if "primary_directions" in directions:
            compact_dirs["primary_directions"] = _compact_primary_directions(
                {"primary_directions": directions["primary_directions"]}
            )["primary_directions"]
            if isinstance(compact_dirs["primary_directions"], dict):
                compact_dirs["primary_directions"].pop("timeline_preview", None)
        if "primary_direction_chart" in directions:
            pdc = directions["primary_direction_chart"]
            compact_dirs["primary_direction_chart"] = (
                {
                    k: v
                    for k, v in pdc.items()
                    if k
                    in {
                        "method",
                        "time_key",
                        "direction_mode",
                        "current_arc_degrees",
                        "directed_ascendant",
                        "directed_medium_coeli",
                        "exact_hits",
                        "sign_changes",
                    }
                }
                if isinstance(pdc, dict)
                else pdc
            )
        compact["directions"] = compact_dirs
    time_lords = result.get("time_lords")
    if isinstance(time_lords, dict):
        compact_tl: ServiceResult = {}
        if "annual_profection" in time_lords:
            compact_tl["annual_profection"] = time_lords["annual_profection"]
        if "firdaria" in time_lords:
            fird = time_lords["firdaria"]
            compact_tl["firdaria"] = (
                {k: v for k, v in fird.items() if k != "timeline"}
                if isinstance(fird, dict)
                else fird
            )
        if "decennials" in time_lords:
            compact_tl["decennials"] = _compact_decennials(
                {"decennials": time_lords["decennials"]}
            )["decennials"]
            if isinstance(compact_tl["decennials"], dict):
                compact_tl["decennials"].pop("timeline", None)
        if "zodiacal_releasing" in time_lords:
            compact_tl["zodiacal_releasing"] = _compact_zr(
                {"zodiacal_releasing": time_lords["zodiacal_releasing"]}
            )["zodiacal_releasing"]
        compact["time_lords"] = compact_tl
    return compact


def _western_module_spec(
    name: str,
    label: str,
    *,
    request_model_name: str = "WesternTimingBaseRequest",
    compact_view: CompactView | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        bind=bind_kwargs(calculate_timing_tool, fixed={"tool_name": name}),
        request_model_loader=request_model_ref(_REQ_MODULE, request_model_name),
        summary=f"{label}：单项西占行运（整合用 western_timing）。",
        operation_label_zh=label,
        family="western_timing",
        cpu_bound=True,
        rest_path="/api/astrology/timing/" + name.replace("_", "-"),
        compact_view=compact_view,
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="western_timing",
        bind=bind_kwargs(calculate_western_timing_analysis),
        request_model_loader=request_model_ref(_REQ_MODULE, "WesternTimingRequest"),
        summary="西占时运聚合分析：整合返照/行运/太阳弧/小限/法达；单项用对应工具。",
        operation_label_zh="西占时运",
        family="western_timing",
        cpu_bound=True,
        rest_path="/api/astrology/timing",
        compact_view=_compact_western_timing,
    ),
    _western_module_spec(
        "solar_return", "西占太阳返照", request_model_name="WesternReturnTimingRequest"
    ),
    _western_module_spec(
        "lunar_return", "西占月亮返照", request_model_name="WesternReturnTimingRequest"
    ),
    _western_module_spec(
        "transit_chart", "西占行运盘", request_model_name="WesternTransitRequest"
    ),
    _western_module_spec("solar_arc", "西占太阳弧"),
    _western_module_spec("chart_for_year", "西占指定年盘"),
    _western_module_spec("profection", "西占年小限"),
    _western_module_spec(
        "primary_directions",
        "西占主限",
        request_model_name="WesternPrimaryDirectionsRequest",
        compact_view=_compact_primary_directions,
    ),
    _western_module_spec(
        "primary_directions_chart",
        "西占主限法盘",
        request_model_name="WesternPrimaryDirectionsChartRequest",
    ),
    _western_module_spec(
        "zodiacal_releasing",
        "西占黄道释放",
        compact_view=_compact_zr,
    ),
    _western_module_spec(
        "firdaria", "西占法达星限", request_model_name="WesternFirdariaRequest"
    ),
    _western_module_spec(
        "decennials", "西占十年星限", compact_view=_compact_decennials
    ),
]
