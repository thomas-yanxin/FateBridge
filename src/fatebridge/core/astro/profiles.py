"""House/zodiac selection and precision provenance profiles."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from fatebridge.core.astro import runtime
from fatebridge.core.astro.reference import (
    CORE_CHART_DEFAULT_HOUSE_LABELS_ZH,
    CORE_CHART_DEFAULT_HOUSE_SYSTEMS,
    CORE_CHART_DEFAULT_ZODIACAL,
    NODE_BODIES,
    RELATIVE_HOUSE_SYSTEM_SPECS,
    RELATIVE_ZODIACAL_LABELS_ZH,
)
from fatebridge.utils.house_systems import InvalidHouseSystemError, house_system_fields

ANALYTICAL_MEAN_NODE_MODEL = "swisseph_analytical_mean_node"
APPROXIMATE_ORBIT_MODEL = "fatebridge_approximate_orbital_model"


def native_factor_model(body_id: int, returned_flags: int) -> str:
    """Mean-node flags echo the request, not a loaded vector ephemeris.

    Swiss 2.10.03 sweph.c delegates this point to swi_mean_node() in
    swemmoon.c. Frame/nutation handling is separate from its mean elements.
    """
    if runtime.swe is not None and body_id == runtime.swe.MEAN_NODE:
        return ANALYTICAL_MEAN_NODE_MODEL
    return runtime.ephemeris_model_from_retflag(returned_flags)


def physical_ephemeris_summary(models: Mapping[str, str]) -> str:
    """Summarize physical bodies, keeping reference points and quality apart."""
    physical = {model for name, model in models.items() if name not in NODE_BODIES}
    if not physical or physical == {APPROXIMATE_ORBIT_MODEL}:
        return "none"
    if len(physical) == 1:
        return next(iter(physical))
    return "mixed"


def _derive_engine_profile(
    *profiles: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    precisions = {
        str(profile["engine_precision"])
        for profile in profiles
        if profile is not None and profile.get("engine_precision")
    }
    backends = {
        str(profile["engine_backend"])
        for profile in profiles
        if profile is not None and profile.get("engine_backend")
    }

    if not precisions:
        engine_precision = "approximate_orbital_model"
    elif len(precisions) == 1:
        engine_precision = next(iter(precisions))
    else:
        engine_precision = "mixed_precision_runtime_model"

    if not backends:
        if engine_precision == "ephemeris_runtime_model":
            engine_backend = "swisseph_api"
        elif engine_precision == "mixed_precision_runtime_model":
            engine_backend = "mixed_runtime_backends"
        else:
            engine_backend = "fatebridge_approximate_orbital_model"
    elif len(backends) == 1:
        engine_backend = next(iter(backends))
    else:
        engine_backend = "mixed_runtime_backends"

    return {
        "engine_precision": engine_precision,
        "engine_backend": engine_backend,
    }


def _precision_label_zh(engine_precision: str) -> str:
    if engine_precision == "ephemeris_runtime_model":
        return "离线高精度"
    if engine_precision == "mixed_precision_runtime_model":
        return "离线混合精度"
    return "离线近似"


def _precision_label_from_profiles(
    *profiles: Optional[Dict[str, Any]],
) -> str:
    return _precision_label_zh(_derive_engine_profile(*profiles)["engine_precision"])


def _coerce_house_system_code(hsys: object) -> Optional[int]:
    """Translate a user-facing house-system identifier into the internal 0-8 code.

    Accepts:
    - ``int``/``str`` numeric values in 0..8
    - Swiss Ephemeris single-letter codes (case-insensitive): P, K, W, R, B,
      V, T, S, D. These match the ``swisseph_code`` bytes on each spec entry
      and align astro/chart hsys with the ``house_system`` strings the
      astro/timing endpoints already accept.
    - Key strings like "placidus"/"whole_sign"/"koch" (case-insensitive),
      matching the internal ``key`` attribute.

    Returns the canonical integer code, or ``None`` if the input cannot be
    resolved (caller raises a descriptive error)."""
    if hsys is None:
        return None
    try:
        return house_system_fields(hsys)["house_system_code"]
    except InvalidHouseSystemError:
        return None


def _resolve_offline_house_system(hsys: Any, *, context_label: str) -> Dict[str, Any]:
    resolved = _coerce_house_system_code(hsys)
    if resolved is None or resolved not in RELATIVE_HOUSE_SYSTEM_SPECS:
        raise ValueError(
            f"{context_label}离线模式暂仅支持 hsys=0..8（整宫制、Alcabitus、Regiomontanus、Placidus、Koch、Vehlow Equal、Polich Page、Sripati、天顶为第10宫宫头的等宫制）。"
        )
    if runtime.swe is None and resolved != 0:
        raise ValueError(
            f"当前环境缺少 swisseph，{context_label}离线模式仅能在 hsys=0(整宫制) 下运行。"
        )
    return {"value": resolved, **RELATIVE_HOUSE_SYSTEM_SPECS[resolved]}


def _resolve_relative_house_system(hsys: Any) -> Dict[str, Any]:
    return _resolve_offline_house_system(hsys, context_label="relative 关系盘")


def _resolve_core_chart_house_system(
    hsys: Any,
    *,
    chart_variant: str,
) -> Dict[str, Any]:
    if hsys in (None, ""):
        default_house_system = CORE_CHART_DEFAULT_HOUSE_SYSTEMS[chart_variant]
        # "equal" and "whole_sign" are Kerykeion-native and need no swisseph code.
        if default_house_system in ("whole_sign", "equal"):
            return {
                "value": None,
                "key": default_house_system,
                "label_zh": CORE_CHART_DEFAULT_HOUSE_LABELS_ZH[default_house_system],
                "source": "variant_default",
            }
        # For swisseph-backed defaults (e.g. "equal_mc"), look up the full spec so
        # _relative_house_layout has the swisseph_code it needs.  We do NOT call
        # _resolve_offline_house_system here because that raises when swe is None;
        # _relative_house_layout already handles swe=None gracefully.
        for code, spec in RELATIVE_HOUSE_SYSTEM_SPECS.items():
            if spec["key"] == default_house_system:
                return {
                    "value": code,
                    **spec,
                    "source": "variant_default",
                }
        return {
            "value": None,
            "key": default_house_system,
            "label_zh": CORE_CHART_DEFAULT_HOUSE_LABELS_ZH.get(
                default_house_system, default_house_system
            ),
            "source": "variant_default",
        }
    return {
        **_resolve_offline_house_system(hsys, context_label="核心星盘"),
        "source": "explicit",
    }


def _resolve_offline_zodiacal_mode(
    zodiacal: Any,
    *,
    context_label: str,
) -> Dict[str, Any]:
    try:
        resolved = int(zodiacal)
    except (TypeError, ValueError):
        raise ValueError(
            f"{context_label}离线模式暂仅支持 zodiacal=0(回归黄道) 或 zodiacal=1(恒星黄道/Lahiri)。"
        )
    if resolved not in RELATIVE_ZODIACAL_LABELS_ZH:
        raise ValueError(
            f"{context_label}离线模式暂仅支持 zodiacal=0(回归黄道) 或 zodiacal=1(恒星黄道/Lahiri)。"
        )
    return {
        "value": resolved,
        "zodiac": "sidereal" if resolved == 1 else "tropical",
        "label_zh": RELATIVE_ZODIACAL_LABELS_ZH[resolved],
        "sidereal": resolved == 1,
    }


def _resolve_relative_zodiacal_mode(zodiacal: Any) -> Dict[str, Any]:
    return _resolve_offline_zodiacal_mode(
        zodiacal,
        context_label="relative 关系盘",
    )


def _resolve_core_chart_zodiacal_mode(
    zodiacal: Any,
    *,
    chart_variant: str,
) -> Dict[str, Any]:
    if zodiacal in (None, ""):
        return {
            **_resolve_offline_zodiacal_mode(
                CORE_CHART_DEFAULT_ZODIACAL[chart_variant],
                context_label="核心星盘",
            ),
            "source": "variant_default",
        }
    return {
        **_resolve_offline_zodiacal_mode(
            zodiacal,
            context_label="核心星盘",
        ),
        "source": "explicit",
    }


def _relative_zodiac_profile_overrides(
    zodiacal_info: Dict[str, Any],
    *,
    ayanamsha: Optional[float] = None,
) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {
        "zodiac": zodiacal_info["zodiac"],
        "zodiacal": zodiacal_info["value"],
        "zodiac_label_zh": zodiacal_info["label_zh"],
    }
    if ayanamsha is not None:
        overrides["ayanamsha"] = round(ayanamsha, 4)
    return overrides
