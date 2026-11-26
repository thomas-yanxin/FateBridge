"""
San Shi United (三式合一：奇门 + 太乙 + 六壬/金口 综合) board.

Pure relocation from the package facade.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fatebridge.core.local_techniques.chart import (
    _build_metaphysics_analysis_context,
    _build_metaphysics_seed,
    _normalize_date_text,
    _normalize_time_text,
)
from fatebridge.core.local_techniques.qimen import build_qimen_with_options
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.metaphysics.sanshi_correspondences import palace_correspondences
from fatebridge.core.metaphysics.taiyi import build_taiyi_board
from fatebridge.core.metaphysics.taiyi_dangshi import noble_source_assessment
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
        "shiji_profile",
    }
    if unknown:
        raise ValueError("未实现的太乙选项：" + ", ".join(sorted(unknown)))
    mode = normalized.get("calculation_mode", "year")
    if not isinstance(mode, str) or mode not in {"year", "month", "day", "hour"}:
        raise ValueError("太乙calculation_mode仅支持year、month、day、hour")
    profile = normalized.get("hour_profile")
    if "hour_profile" in normalized and not isinstance(profile, str):
        raise ValueError("hour_profile必须是已发布时计配置名称")
    month_profile = normalized.get("month_profile")
    if "month_profile" in normalized and not isinstance(month_profile, str):
        raise ValueError("month_profile必须是已发布月计配置名称")
    year_profile = normalized.get("year_profile")
    if "year_profile" in normalized and not isinstance(year_profile, str):
        raise ValueError("year_profile必须是已发布年计配置名称")
    return build_taiyi_board(
        seed,
        gender="未知",
        calculation_mode=mode,
        hour_profile=profile,
        month_profile=month_profile,
        year_profile=year_profile,
        shiji_profile=normalized.get("shiji_profile"),
    )


def _source_profiles(qimen: dict[str, Any], liureng: dict[str, Any]) -> dict[str, Any]:
    """Keep source identities in a first view without copying whole audits."""
    result: dict[str, Any] = {"qimen": [], "liureng": []}
    raw = [("qimen", f"qimen.rulesets.{i}", r) for i, r in enumerate(qimen["rulesets"])]
    raw.append(("liureng", "liureng.ruleset", liureng["ruleset"]))
    for technique, path, ruleset in raw:
        profile = {
            key: ruleset[key]
            for key in (
                "id",
                "version",
                "author",
                "classical_author",
                "source",
                "source_urls",
                "classical_conformance",
                "classical_acceptance_passed",
            )
            if key in ruleset
        }
        profile.update(
            source_path=path,
            source_title=ruleset.get("source_title", ruleset.get("title", "")),
            unresolved_count=len(ruleset.get("unresolved", [])),
        )
        result[technique].append(profile)
    return result


def build_sanshiunited_result(
    *,
    date: str,
    time: str,
    zone: str | None = None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    qimen_options: dict[str, Any] | None = None,
    taiyi_options: dict[str, Any] | None = None,
    liureng_yue: str | None = None,
    liureng_is_diurnal: bool | None = None,
    liureng_guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
    use_true_solar_time: bool = False,
) -> dict[str, Any]:
    input_normalized = {
        "date": _normalize_date_text(date),
        "time": _normalize_time_text(time),
        "zone": zone or DEFAULT_BIRTH_TIMEZONE,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "qimen_options": qimen_options or {},
        "taiyi_options": taiyi_options or {},
        "liureng_yue": liureng_yue,
        "liureng_is_diurnal": liureng_is_diurnal,
        "liureng_guiren_profile": liureng_guiren_profile,
        "use_true_solar_time": bool(use_true_solar_time),
    }
    seed = _build_metaphysics_seed(
        date_text=input_normalized["date"],
        time_text=input_normalized["time"],
        timezone_name=input_normalized["zone"],
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        use_true_solar_time=bool(use_true_solar_time),
    )
    qimen_seed = seed
    qimen = build_qimen_with_options(qimen_seed, qimen_options)
    taiyi = _build_taiyi_with_options(seed, taiyi_options)
    seed = replace(
        seed,
        calendar_context={
            **seed.calendar_context,
            "ren_calendar_policy": require_ren_calendar(
                seed, month_general_override=liureng_yue
            ),
        },
    )
    liureng = build_liureng_board(
        seed,
        gender="未知",
        month_general_override=liureng_yue,
        is_diurnal_override=liureng_is_diurnal,
        guiren_profile=liureng_guiren_profile,
    )

    correspondences = palace_correspondences(taiyi, qimen, liureng)
    noble_assessment = noble_source_assessment(
        seed.pillars["day"][0],
        liureng,
        taiyi_mode=taiyi["calendar_summary"]["calculation_mode"],
    )
    analysis_context = _build_metaphysics_analysis_context(seed)
    four_pillars = create_pillar_dict(seed.pillars)
    qimen_analysis_context = _build_metaphysics_analysis_context(qimen_seed)
    qimen_four_pillars = create_pillar_dict(qimen_seed.pillars)
    subresults = {
        "qimen": {
            "analysis_type": "奇门遁甲",
            "analysis_context": qimen_analysis_context,
            "four_pillars": qimen_four_pillars,
            "calendar_context": qimen_seed.calendar_context,
        },
        "taiyi": {
            "analysis_type": "太乙神数",
            "analysis_context": analysis_context,
            "four_pillars": four_pillars,
        },
        "liureng_gods": {
            "analysis_type": "大六壬起课",
            "analysis_context": analysis_context,
            "four_pillars": four_pillars,
            "calendar_context": seed.calendar_context,
        },
    }

    return {
        "analysis_type": "三式合一",
        "analysis_context": analysis_context,
        "input_normalized": input_normalized,
        "qimen": qimen,
        "taiyi": taiyi,
        "liureng": liureng,
        "subresults": subresults,
        "synthesis": {
            "source_profiles": _source_profiles(qimen, liureng),
            "method": "scoped_evidence_aggregation_v1",
            "status": "parallel_boards_without_validated_joint_prediction",
            "time_scopes": {
                "taiyi": taiyi["ruleset"]["time_granularity"],
                "qimen": "casting_time",
                "liureng": "casting_time",
            },
            "common_input": {
                "date": input_normalized["date"],
                "time": input_normalized["time"],
                "timezone": input_normalized["zone"],
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
                    "technique": "liureng",
                    "field": "liureng.patterns",
                    "value": liureng.get("patterns", []),
                },
            ],
            "palace_correspondences": correspondences,
            "noble_source_assessment": noble_assessment,
            "agreement": "not_assessed_without_shared_event_and_adjudication_rule",
            "independent_evidence_count": None,
            "limitations": [
                (
                    (
                        "共用民用输入；太乙年计另用所选齐梁史历表，502年闰标分歧保留；奇门/六壬仍用各自现代适配，未认证三式共同古历时刻，也不能假设统计独立。"
                        if (taiyi.get("calendar_rules") or {}).get("year_profile")
                        == "jinjing_year_qiliang_table_v1"
                        else "共用民用输入；太乙年计另用所选历史晋历表，奇门/六壬仍用各自现代适配，未认证三式共同古历时刻，也不能假设统计独立。"
                    )
                    if (taiyi.get("calendar_rules") or {}).get("historical_calendar")
                    else "各盘共用输入及历法，不能假设统计独立。"
                ),
                "各术原典符合度须独立验收；本次太乙规则修正不认证奇门或六壬。",
                "太乙各计法按实际时间层解释；时计至点和时辰边界采用已声明的现代时钟适配，不能外推分钟级事件应验。",
            ],
        },
        "summary": (
            f"已运行本地三式合一聚合算法。"
            f"奇门：{qimen['dun_type']}{qimen['ju_number']}局。"
            f"太乙：{(taiyi.get('core_board') or {}).get('main_calculation', '无')}。"
            f"六壬：{next((item.get('name') for item in liureng.get('patterns', []) if isinstance(item, dict)), '无')}。"
        ),
    }
