"""San Shi United (三式合一：奇门 + 太乙 + 大六壬) local aggregation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.metaphysics.sanshi_correspondences import (
    CornerLodging,
    palace_correspondences,
)
from fatebridge.core.metaphysics.seed import (
    build_local_metaphysics_seed,
    build_metaphysics_analysis_context,
)
from fatebridge.core.metaphysics.taiyi import build_taiyi_board, noble_source_assessment
from fatebridge.core.qimen import build_qimen_with_options
from fatebridge.utils.civil_time import normalize_date_text, normalize_time_text
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.formatting import create_pillar_dict
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE


def _build_taiyi_with_options(
    seed: MetaphysicsSeed, options: dict[str, Any] | None
) -> dict[str, Any]:
    normalized = dict(options or {})
    unknown = set(normalized) - {
        "calculation_mode",
        "hour_profile",
        "month_profile",
        "year_profile",
        "day_profile",
        "shiji_profile",
        "table_policy",
    }
    if unknown:
        raise ValueError("未实现的太乙选项：" + ", ".join(sorted(unknown)))
    mode = normalized.get("calculation_mode", "year")
    if not isinstance(mode, str) or mode not in {
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "fate",
    }:
        raise ValueError(
            "太乙calculation_mode仅支持year、month、day、hour、minute、fate"
        )
    kwargs: dict[str, Any] = {
        "gender": "未知",
        "calculation_mode": mode,
        "hour_profile": normalized.get("hour_profile"),
        "month_profile": normalized.get("month_profile"),
        "year_profile": normalized.get("year_profile"),
        "shiji_profile": normalized.get("shiji_profile"),
    }
    if normalized.get("day_profile") is not None:
        kwargs["day_profile"] = normalized["day_profile"]
    if normalized.get("table_policy") is not None:
        kwargs["table_policy"] = normalized["table_policy"]
    return build_taiyi_board(seed, **kwargs)


def build_sanshiunited_result(
    *,
    date: str,
    time: str,
    timezone: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    qimen_options: dict[str, Any] | None = None,
    taiyi_options: dict[str, Any] | None = None,
    liuren_yue: str | None = None,
    liuren_is_diurnal: bool | None = None,
    liuren_guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
    use_true_solar_time: bool = False,
    corner_lodging: CornerLodging = "both",
) -> dict[str, Any]:
    date_text = normalize_date_text(date)
    time_text = normalize_time_text(time)
    timezone_name = timezone or DEFAULT_BIRTH_TIMEZONE
    parsed_latitude = parse_geo_coordinate(latitude, axis="latitude")
    parsed_longitude = parse_geo_coordinate(longitude, axis="longitude")
    input_normalized: dict[str, Any] = {
        "date": date_text,
        "time": time_text,
        "timezone": timezone_name,
        "latitude": parsed_latitude,
        "longitude": parsed_longitude,
        "qimen_options": qimen_options or {},
        "taiyi_options": taiyi_options or {},
        "liuren_yue": liuren_yue,
        "liuren_is_diurnal": liuren_is_diurnal,
        "liuren_guiren_profile": liuren_guiren_profile,
        "use_true_solar_time": bool(use_true_solar_time),
        "corner_lodging": corner_lodging,
    }
    base_seed = build_local_metaphysics_seed(
        date_text=date_text,
        time_text=time_text,
        timezone_name=timezone_name,
        lat=parsed_latitude,
        lon=parsed_longitude,
        gps_lat=None,
        gps_lon=None,
        use_true_solar_time=bool(use_true_solar_time),
    )
    ren_policy = require_ren_calendar(base_seed, month_general_override=liuren_yue)
    ren_seed = replace(
        base_seed,
        calendar_context={
            **base_seed.calendar_context,
            "ren_calendar_policy": ren_policy,
        },
    )

    qimen = build_qimen_with_options(base_seed, qimen_options)
    taiyi = _build_taiyi_with_options(base_seed, taiyi_options)
    liureng = build_liureng_board(
        ren_seed,
        gender="未知",
        month_general_override=liuren_yue,
        is_diurnal_override=liuren_is_diurnal,
        guiren_profile=liuren_guiren_profile,
    )

    correspondences = palace_correspondences(
        taiyi, qimen, liureng, corner_lodging=corner_lodging
    )
    noble_assessment = noble_source_assessment(
        base_seed.pillars["day"][0],
        liureng,
        taiyi_mode=taiyi["calendar_summary"]["calculation_mode"],
    )
    analysis_context = {
        **input_normalized,
        **build_metaphysics_analysis_context(base_seed),
    }
    four_pillars = create_pillar_dict(base_seed.pillars)

    # Compact subresults without 41 KB calendar_context / analysis_context 3x duplication.
    subresults = {
        "qimen": {"analysis_type": "奇门遁甲", "four_pillars": four_pillars},
        "taiyi": {"analysis_type": "太乙神数", "four_pillars": four_pillars},
        "liuren": {"analysis_type": "大六壬起课", "four_pillars": four_pillars},
    }

    return {
        "analysis_type": "三式合一",
        "analysis_context": analysis_context,
        "four_pillars": four_pillars,
        "qimen": qimen,
        "taiyi": taiyi,
        "liuren": liureng,
        "subresults": subresults,
        "synthesis": {
            "method": "sanshi_correspondence_v2",
            "status": "implemented",
            "time_scopes": {
                "taiyi": taiyi["ruleset"]["time_granularity"],
                "qimen": "casting_time",
                "liuren": "casting_time",
            },
            "common_input": {
                "date": input_normalized["date"],
                "time": input_normalized["time"],
                "timezone": input_normalized["timezone"],
            },
            "facts": [
                {
                    "technique": "taiyi",
                    "field": "taiyi.core_board.main_calculation",
                    "value": taiyi["core_board"]["main_calculation"],
                },
                {
                    "technique": "qimen",
                    "field": "qimen.ju_text",
                    "value": qimen["ju_text"],
                },
                {
                    "technique": "liuren",
                    "field": "liuren.patterns",
                    "value": liureng.get("patterns", []),
                },
            ],
            "palace_correspondences": correspondences,
            "noble_source_assessment": noble_assessment,
        },
        "summary": (
            f"奇门：{qimen['dun_type']}{qimen['ju_number']}局。"
            f"太乙：{(taiyi.get('core_board') or {}).get('main_calculation', '无')}。"
            f"六壬：{next((item.get('name') for item in liureng.get('patterns', []) if isinstance(item, dict)), '无')}。"
        ),
    }
