"""Calendar 宿曜: direct T1299 full-moon methods and scoped 三九法.

No longitude partition determines a calendrical natal mansion. The 28-name
vocabulary is independent of the chart engine to prevent a circular import.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, cast

from lunardate import LunarDate

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.sukuyo_calendar_basis import (
    DEFAULT_CALENDAR_BASIS,
    HISTORICAL_CALENDAR_BASIS,
    JAPANESE_CALENDAR_BASES,
    JAPANESE_CALENDAR_BASIS,
    basis_identifiers,
    basis_parameters,
    japanese_calendar_reader,
    range_provenance,
)
from fatebridge.core.sukuyo_date_support import input_timezone_context
from fatebridge.core.sukuyo_profiles import (
    DEFAULT_PROFILE,
    HINOO_PROFILE,
    fullmoon_calculation,
    select_profile,
)
from fatebridge.core.sukuyo_profiles import source_bundle as profile_sources
from fatebridge.core.sukuyo_relations import (
    _ALIASES,
    _GOOD_CONTACT,
    RELATION_PAIR,
    RELATION_TEMPLATE,
    SU27_ORDER,
    SU28_NAMES,
    TEXT_URL,
    normalize_mansion,
    relation_between_su27,
)
from fatebridge.utils.timezones import (
    parse_timezone_name,
    validate_local_clock,
)

MONTH_STARTS = list("室奎胃毕参鬼张角氐心斗虚")
NAOJ_URL = "https://eco.mtk.nao.ac.jp/koyomi/wiki/C6F3BDBDC8ACBDC9.html"
CALENDAR_ZONE = timezone(timedelta(hours=8))


@lru_cache(maxsize=1)
def _calendar_corrections() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "data/sukuyo_calendar_corrections.json"
            ).read_text(encoding="utf-8")
        ),
    )


def rulesets(
    calendar_profile: str = DEFAULT_PROFILE,
    calendar_basis: str = DEFAULT_CALENDAR_BASIS,
) -> Dict[str, Any]:
    offset = basis_parameters(calendar_basis)[0]
    source = profile_sources()
    from fatebridge.core.sukuyo_calendar_text import source_bundle as day_sources
    from fatebridge.core.sukuyo_clothing import source_bundle as clothing_sources
    from fatebridge.core.sukuyo_directions import source_bundle as direction_sources
    from fatebridge.core.sukuyo_lower import source_bundle as lower_sources
    from fatebridge.core.sukuyo_lower_methods import source_bundle as method_sources
    from fatebridge.core.sukuyo_padas import source_bundle as pada_sources
    from fatebridge.core.sukuyo_sanjiu_days import source_bundle as sanjiu_sources
    from fatebridge.core.sukuyo_six_palaces import six_palace_reference
    from fatebridge.core.sukuyo_special_days import scope_for_weekday_basis
    from fatebridge.core.sukuyo_special_days import source_bundle as special_sources
    from fatebridge.core.sukuyo_taibai import source_bundle as taibai_sources

    lower = lower_sources()
    clothing = clothing_sources()
    padas = pada_sources()
    methods = method_sources()
    days = day_sources()
    directions = direction_sources()
    specials = special_sources()
    sanjiu = sanjiu_sources()
    six = six_palace_reference(None)
    taibai = taibai_sources()
    result: Dict[str, Any] = {
        "calendar": {
            "id": (
                source["hinoo_addendum"]["id"]
                if calendar_profile == HINOO_PROFILE
                else source["id"]
            ),
            "author": "不空译；T1299下卷望日逆顺法",
            "source": TEXT_URL,
            "locator": "T21n1299_p0394c20-0395a04; p0395b01-08",
            "calendar_profile": calendar_profile,
            "corroborating_source": NAOJ_URL,
            "hinoo_addendum": (
                deepcopy(source["hinoo_addendum"])
                if calendar_profile == HINOO_PROFILE
                else None
            ),
            "scope": "以原典十五日望宿逆顺数，生日加十三含首计数独立复核；使用现代中国农历，不重建唐历或日本旧历。",
        },
        "relations": {
            "id": "t1299_sanjiu_v1",
            "author": "不空译；上卷杨景风修注",
            "source": TEXT_URL,
            "locator": "T21n1299_p0391b06-18; p0397c01-19",
            "scope": "三九顺序及双向结交规则；六类配对名仅为界面归类。",
        },
        "personal_day_witnesses": {
            "id": sanjiu["id"],
            "author": sanjiu["author"],
            "source": sanjiu["source_url"],
            "source_sha256": sanjiu["source_sha256"],
            "locator": "T21n1299_p0391b19-25; p0397c25-0398a17",
            "scope": sanjiu["scope"],
        },
        "six_palace_positions": {
            "id": six["ruleset_id"],
            "author": "不空译；上卷杨景风修注",
            "source": six["source_url"],
            "source_sha256": six["source_sha256"],
            "locator": six["locator"],
            "scope": six["scope"],
        },
        "calendar_day": {
            "id": days["id"],
            "author": "不空译；上卷杨景风修注",
            "source": TEXT_URL,
            "locator": "T21n1299_p0392c29-0393c06; p0393c18-0394c16",
            "scope": "黑白月日名、一般日类及昼夜条文；保留字面差异，按下卷夹注释一夜为十一夜，钟时映射未完成。",
        },
        "taibai_directions": {
            "id": taibai["id"],
            "author": taibai["author"],
            "source": taibai["source_url"],
            "source_sha256": taibai["source_sha256"],
            "locator": taibai["locator"],
            "scope": taibai["scope"],
        },
        "clothing": {
            "id": clothing["id"],
            "author": clothing["author"],
            "source": clothing["source_url"],
            "source_sha256": clothing["source_sha256"],
            "locator": clothing["locator"],
            "scope": clothing["scope"],
        },
        "travel_directions": {
            "id": directions["id"],
            "author": directions["author"],
            "source": directions["source_url"],
            "locator": directions["locator"],
            "selected_text": directions["selected_text"],
            "scope": directions["scope"],
        },
        "special_days": {
            "id": specials["id"],
            "author": specials["author"],
            "source": specials["source_url"],
            "selected_primary": specials["selected_primary"],
            "selected_lower_activity_witness": specials[
                "selected_lower_activity_witness"
            ],
            "locator": "T21n1299_p0392c17-28; p0398b21-0398c07",
            "scope": scope_for_weekday_basis(
                specials["scope"], f"modern_utc_plus{offset:02}_civil_midnight"
            ),
        },
        "lower_mansion_day": {
            "id": lower["id"],
            "author": lower["author"],
            "source": lower["source_url"],
            "locator": lower["locator"],
            "scope": "27宿逐条索引及六类事项摘录；细节缺失和文本未校定时保留条件，未收录事项不推为禁忌。",
        },
        "lower_methods": {
            "id": methods["id"],
            "author": methods["author"],
            "source": methods["source_url"],
            "locator": methods["nature_locator"] + "; " + methods["weekday_locator"],
            "scope": methods["scope"],
        },
        "conjunction_doctrine": {
            "id": lower["conjunction_doctrine"]["id"],
            "author": "不空译；下卷宿月配合段",
            "source": lower["source_url"],
            "locator": lower["conjunction_doctrine"]["locator"],
            "scope": "六、十二、九宿文献分组；末九成员由宿序推得，不等于已求出天文角距、宿界或过宿时刻。",
        },
        "palace_reference": {
            "id": padas["id"],
            "author": padas["author"],
            "source": padas["source_url"],
            "locator": padas["locator"],
            "scope": "原典27宿四足、十二宫九足的名宿查表；显式足序是查表条件，未由历日、钟时或现代星图推得出生足位。",
        },
        "unresolved": [
            "T1299大唐月建图为含牛的28宿表，与二月五日毕宿例及27宿三九法不能直接合并。",
            "业宿日：上卷0391b19-20称吉，下卷0398a07-08称不成就；不合成单一结论。",
            "危日婚姻：下卷0398a02称宜定婚姻，0398a09-10又称不宜；保留两条，不投票合成。",
            "壁宿南行：下卷逐宿0396b21称不宜，行动禁闭法0397b06-07列宜；分别保留，不抵销。",
            "近中远相性距离不在本次采用的三九原文中；九组序号不等于关系距离。",
        ],
        "textual_resolutions": [deepcopy(days["verse_abbreviation_resolution"])],
    }
    if calendar_basis in JAPANESE_CALENDAR_BASES:
        result["calendar"]["scope"] = (
            "以T1299下卷表定望日算法配宿；宿主为显式NAOJ日本历史月朔参考，采用延伸格里历日期和固定UTC+09；早期纪年为重建，未复原历史地方时或解决跨出版方异日。"
            if calendar_basis == HISTORICAL_CALENDAR_BASIS
            else "以T1299下卷表定望日算法配宿；宿主为显式HuTime日本旧历逐日参考，统一UTC+09历日，不称唐历、完整天保历或历史日本地方时已复原。"
        )
        result["calendar_reference"] = japanese_calendar_reader(
            calendar_basis
        ).reference_metadata()
    return result


def lunar_mansion(month: int, day: int) -> str:
    """T1299's two full-moon algorithms agree with the independent NAOJ table."""
    return cast(str, fullmoon_calculation(month, day, SU27_ORDER)["direct_mansion"])


def _lunar_fields(
    civil: date, calendar_basis: str = DEFAULT_CALENDAR_BASIS
) -> tuple[int, int, int, bool]:
    if calendar_basis in JAPANESE_CALENDAR_BASES:
        return cast(
            tuple[int, int, int, bool],
            japanese_calendar_reader(calendar_basis).lunar_fields(civil),
        )
    if calendar_basis != DEFAULT_CALENDAR_BASIS:
        raise ValueError("未知的宿曜宿主历法，不能回退中国历")
    correction = _calendar_corrections()["corrections"].get(civil.isoformat())
    if correction is not None:
        return (
            int(correction[0]),
            int(correction[1]),
            int(correction[2]),
            bool(correction[3]),
        )
    lunar = LunarDate.fromSolarDate(civil.year, civil.month, civil.day)
    return lunar.year, lunar.month, lunar.day, bool(lunar.isLeapMonth)


def calendar_mansion(
    date_text: str,
    time_text: Optional[str] = None,
    zone: Optional[str] = None,
    *,
    leap_month_policy: str = "unresolved",
    calendar_profile: str = DEFAULT_PROFILE,
    calendar_day_part: Optional[str] = None,
    calendar_basis: str = DEFAULT_CALENDAR_BASIS,
) -> Dict[str, Any]:
    """Use the explicit host calendar and reference zone, never guessed hours."""
    offset, first_date, last_date, calendar_label = basis_parameters(calendar_basis)
    calendar_system, calendar_backend = basis_identifiers(calendar_basis)
    timezone_label = f"UTC+{offset:02}:00"
    if leap_month_policy not in {"unresolved", "repeat_month"}:
        raise ValueError("leap_month_policy仅支持unresolved或repeat_month")
    civil_date = date.fromisoformat(date_text.replace("/", "-"))
    selected_zone = zone or "+08:00"
    input_moment = None
    date_support = None
    if time_text:
        naive = datetime.fromisoformat(f"{civil_date.isoformat()}T{time_text}")
        if naive.tzinfo is not None:
            raise ValueError("time不得内嵌时区；请使用zone")
        moment = localize_datetime(naive, selected_zone)
        input_moment = moment.isoformat()
        try:
            validate_local_clock(moment)
            # The validated local offset identifies this instant even when its
            # intermediate UTC label would be in year zero. Do not require a
            # representable UTC datetime if the host reference date is valid.
            input_offset = moment.utcoffset()
            assert input_offset is not None
            calendar_date = (naive + timedelta(hours=offset) - input_offset).date()
        except OverflowError as error:
            raise ValueError(
                "所给钟时的日界换算超出可表示的民用日期范围；未替换时区或回退其他历法。"
            ) from error
    else:
        zone_info = parse_timezone_name(selected_zone)
        if isinstance(zone_info, timezone) and zone_info.utcoffset(None) == timedelta(
            hours=offset
        ):
            calendar_date = civil_date
        else:
            from fatebridge.core.sukuyo_date_support import local_date_support

            date_support = local_date_support(
                civil_date.isoformat(), selected_zone, calendar_offset_hours=offset
            )
            if len(date_support["possible_calendar_dates"]) > 1:
                return _date_uncertain_calendar(
                    civil_date,
                    selected_zone,
                    date_support,
                    leap_month_policy=leap_month_policy,
                    calendar_profile=calendar_profile,
                    calendar_day_part=calendar_day_part,
                    calendar_basis=calendar_basis,
                )
            calendar_date = date.fromisoformat(
                date_support["possible_calendar_dates"][0]
            )
    if not first_date <= calendar_date <= last_date:
        raise ValueError(
            f"宿曜{calendar_label}历法支持{first_date}至{last_date}；范围外不回退其他历法或外推"
            f"。{range_provenance(calendar_basis)}"
        )
    year, month, day, leap = _lunar_fields(calendar_date, calendar_basis)
    correction = (
        _calendar_corrections()["corrections"].get(calendar_date.isoformat())
        if calendar_basis == DEFAULT_CALENDAR_BASIS
        else None
    )
    previous = None
    if calendar_profile == HINOO_PROFILE and day == 1 and calendar_date > first_date:
        previous_date = calendar_date - timedelta(days=1)
        py, pm, pd, pl = _lunar_fields(previous_date, calendar_basis)
        previous = {
            "calendar_date": previous_date.isoformat(),
            "lunar_year": py,
            "lunar_month": pm,
            "lunar_day": pd,
            "is_leap_month": pl,
        }
        if leap:
            before_regular_date = calendar_date - timedelta(days=pd + 1)
            if before_regular_date >= first_date:
                ry, rm, rd, rl = _lunar_fields(before_regular_date, calendar_basis)
                previous["before_regular_month"] = {
                    "calendar_date": before_regular_date.isoformat(),
                    "lunar_year": ry,
                    "lunar_month": rm,
                    "lunar_day": rd,
                    "is_leap_month": rl,
                }
    selection = select_profile(
        month,
        day,
        leap,
        SU27_ORDER,
        profile=calendar_profile,
        leap_policy=leap_month_policy,
        day_part=calendar_day_part,
        previous_lunar=previous,
    )
    resolved = selection["resolved"]
    mansion = selection["natal_su27"] or selection["host_calculation"]["direct_mansion"]
    from fatebridge.core.sukuyo_calendar_text import month_table_variant
    from fatebridge.core.sukuyo_koya import printed_month_reference

    host = selection["host_calculation"]
    variant = month_table_variant(
        month,
        day,
        host["direct_mansion"],
        resolved and mansion == host["direct_mansion"],
    )

    result: Dict[str, Any] = {
        "status": "computed" if resolved else "partial",
        "input_date": civil_date.isoformat(),
        "input_datetime": input_moment,
        "input_timezone": selected_zone,
        "input_timezone_rules": input_timezone_context(selected_zone),
        "birth_time_known": bool(time_text),
        "calendar_date": calendar_date.isoformat(),
        "calendar_timezone": timezone_label,
        "calendar_system": calendar_system,
        "calendar_backend": calendar_backend,
        "calendar_correction": (
            "sukuyo_hko_corrections_v1" if correction is not None else None
        ),
        "calendar_source": (
            "https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T2069c.txt"
            if calendar_date == date(2069, 12, 30)
            else f"https://www.hko.gov.hk/en/gts/time/calendar/text/files/T{calendar_date.year}e.txt"
        ),
        "lunar_year": year,
        "lunar_month": month,
        "lunar_day": day,
        "is_leap_month": leap,
        "leap_month_policy": selection["effective_leap_month_policy"],
        "calendar_profile": calendar_profile,
        "mansion_method_id": selection["mansion_method_id"],
        "calendar_day_part": calendar_day_part,
        "resolution_reason": selection["resolution_reason"],
        "natal_su27": selection["natal_su27"],
        "candidate_su27": selection["candidate_su27"],
        "candidate_su27s": selection["candidate_su27s"],
        "month_start_mansion": lunar_mansion(month, 1),
        "month_start_mansion_basis": "unsplit_T1299_host_month",
        "profile_calculation": selection,
        "source_table_variant": variant,
        "printed_edition_reference": printed_month_reference(
            host, variant, selection, leap
        ),
        "rule_trace": [
            {
                "rule_id": "t1299_lower_fullmoon27_two_methods",
                "source": TEXT_URL,
                "locator": "T21n1299_p0394c20-0395a04; p0395b01-08",
                "inputs": {
                    "month": month,
                    "day": day,
                    "fullmoon_mansion": selection["host_calculation"][
                        "fullmoon_mansion"
                    ],
                },
                "output": selection["host_calculation"]["direct_mansion"],
                "applied_to_primary": resolved
                and selection["natal_su27"]
                == selection["host_calculation"]["direct_mansion"],
            }
        ]
        + (
            [
                {
                    "rule_id": "t2465_repeat_and_short_month_assignment",
                    "source": selection["hinoo_source"]["source_url"],
                    "locator": (
                        selection["hinoo_source"]["leap_locator"]
                        + "; "
                        + selection["hinoo_source"]["short_month_locator"]
                    ),
                    "inputs": {
                        "day_part": calendar_day_part,
                        "previous_lunar": previous,
                    },
                    "output": selection["natal_su27"],
                    "candidate_outputs": selection["candidate_su27s"],
                    "applied_to_primary": resolved,
                }
            ]
            if calendar_profile == HINOO_PROFILE
            else []
        ),
        "limitations": (
            ["T1299默认档案未指定闰月配宿；同名月候选未作为确定宿。"]
            if selection["resolution_reason"] == "leap_month_policy_unresolved"
            else []
        )
        + (
            ["闰月重用同名月为显式约定，不宣称原典唯一算法。"]
            if leap and resolved
            else []
        )
        + (
            [
                "小月缺日分配在次月初一前/后半，候选宿不同；未提供原典日序半日，不能用出生钟时自动代填。"
            ]
            if selection["resolution_reason"] == "hinoo_short_month_day_part_unresolved"
            else []
        )
        + (
            [
                (
                    "Hinoo研究档案将T2465规则应用于T1299宿表及现代中国历日；保留十二月三十日星/室字面差异，不宣称历史旧历完全复原。"
                    if offset == 8
                    else (
                        "Hinoo研究档案将T2465规则应用于T1299宿表及NAOJ日本历史参考；保留十二月三十日星/室字面差异，半日钟时和规则次序仍未校定。"
                        if calendar_basis == HISTORICAL_CALENDAR_BASIS
                        else "Hinoo研究档案将T2465规则应用于T1299宿表及HuTime日本旧历参考；保留十二月三十日星/室字面差异，不宣称完整历史历法或半日钟时已复原。"
                    )
                )
            ]
            if calendar_profile == HINOO_PROFILE
            else []
        )
        + (
            [
                "闰月复用与小月分宿同时适用，规则先后未由原典明确；前半重建结果不一致，保留候选。"
            ]
            if selection["resolution_reason"]
            == "hinoo_leap_short_month_precedence_unresolved"
            else []
        ),
    }
    if date_support is not None:
        result["date_support"] = date_support
    if calendar_basis in JAPANESE_CALENDAR_BASES:
        reference = japanese_calendar_reader(calendar_basis).date_reference(
            calendar_date
        )
        result["calendar_basis"] = calendar_basis
        result["calendar_reference"] = reference
        result["calendar_source"] = reference["date_source_uri"]
        result["rule_trace"].append(
            {
                "rule_id": reference["id"],
                "source": reference["date_source_uri"],
                "source_bundle_sha256": reference["source_bundle_sha256"],
                "calendar_basis": calendar_basis,
                "calendar_timezone": timezone_label,
                "output": {"year": year, "month": month, "day": day, "leap": leap},
                "historical_local_time_reconstruction": False,
            }
        )
    return result


def _date_uncertain_calendar(
    civil_date: date,
    zone: str,
    support: Dict[str, Any],
    *,
    leap_month_policy: str,
    calendar_profile: str,
    calendar_day_part: Optional[str],
    calendar_basis: str = DEFAULT_CALENDAR_BASIS,
) -> Dict[str, Any]:
    offset, first_date, last_date, calendar_label = basis_parameters(calendar_basis)
    calendar_system, calendar_backend = basis_identifiers(calendar_basis)
    candidates = []
    excluded = []
    for value in support["possible_calendar_dates"]:
        # Lower-boundary support may honestly include year zero. It is
        # outside all public host domains and must remain an excluded branch.
        if not first_date.isoformat() <= value <= last_date.isoformat():
            excluded.append(value)
            continue
        target = date.fromisoformat(value)
        # A derived reference-date candidate is a table lookup, never an imputed
        # observed birth clock. Each branch retains its full calendar profile.
        candidate = calendar_mansion(
            value,
            zone=f"+{offset:02}:00",
            leap_month_policy=leap_month_policy,
            calendar_profile=calendar_profile,
            calendar_day_part=calendar_day_part,
            calendar_basis=calendar_basis,
        )
        candidate["input_origin"] = (
            "derived_calendar_date_candidate_not_observed_birth_date"
        )
        candidates.append(candidate)
    if not candidates:
        raise ValueError(
            f"所有可能{calendar_label}历日均超出{first_date}至{last_date}的支持范围。"
            + range_provenance(calendar_basis)
        )
    complete = not excluded and all(
        c["profile_calculation"][
            "candidate_set_complete_under_declared_reconstructions"
        ]
        for c in candidates
    )
    names = list(
        dict.fromkeys(
            name
            for c in candidates
            for name in ([c["natal_su27"]] if c["natal_su27"] else c["candidate_su27s"])
        )
    )
    resolved = complete and len(names) == 1 and all(c["natal_su27"] for c in candidates)
    primary = names[0] if resolved else None

    def common(key: str) -> Any:
        first = candidates[0][key]
        return (
            deepcopy(first)
            if not excluded and all(c[key] == first for c in candidates)
            else None
        )

    profile = {
        "calendar_profile": calendar_profile,
        "mansion_method_id": candidates[0]["mansion_method_id"],
        "resolved": resolved,
        "resolution_reason": "local_date_spans_chinese_calendar_dates",
        "natal_su27": primary,
        "candidate_su27s": [] if resolved else names,
        "candidate_set_complete_under_declared_reconstructions": complete,
        "historical_calendar_reconstruction": False,
        "classical_full_profile_acceptance": False,
    }
    result = {
        "status": "partial",
        "input_date": civil_date.isoformat(),
        "input_datetime": None,
        "input_timezone": zone,
        "input_timezone_rules": input_timezone_context(zone),
        "birth_time_known": False,
        "calendar_date": None,
        "calendar_timezone": f"UTC+{offset:02}:00",
        "calendar_system": calendar_system,
        "calendar_backend": calendar_backend,
        "calendar_source": None,
        "calendar_correction": common("calendar_correction"),
        **{
            k: common(k)
            for k in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
        },
        "leap_month_policy": common("leap_month_policy"),
        "calendar_profile": calendar_profile,
        "mansion_method_id": candidates[0]["mansion_method_id"],
        "calendar_day_part": calendar_day_part,
        "resolution_reason": "local_date_spans_chinese_calendar_dates",
        "natal_su27": primary,
        "candidate_su27": names[0] if not resolved and len(names) == 1 else None,
        "candidate_su27s": [] if resolved else names,
        "profile_calculation": profile,
        "date_support": support,
        "calendar_candidates": candidates,
        "out_of_range_calendar_dates": excluded,
        "source_table_variant": None,
        "rule_trace": [
            {
                "rule_id": support["method_id"],
                "input_date": civil_date.isoformat(),
                "input_timezone": zone,
                "output_calendar_dates": support["possible_calendar_dates"],
                "birth_time_imputed": False,
            }
        ],
        "limitations": [
            f"当地日期对应多个{calendar_label}历日；逐个保留，未猜测出生时刻。"
        ]
        + (
            [f"部分可能{calendar_label}历日超出支持范围，已列宿候选不保证穷尽。"]
            if excluded
            else []
        ),
    }
    if calendar_basis in JAPANESE_CALENDAR_BASES:
        result["calendar_basis"] = calendar_basis
        result["calendar_reference"] = japanese_calendar_reader(
            calendar_basis
        ).reference_metadata()
        result["resolution_reason"] = "local_date_spans_japanese_reference_dates"
        result["profile_calculation"]["resolution_reason"] = result["resolution_reason"]
    return result


def su28_to_su27(name: str, longitude: Optional[float] = None) -> str:
    """Validate a shared name, refusing the former invented 牛 midpoint rule."""
    name = normalize_mansion(name)
    if name not in SU28_NAMES:
        raise ValueError(f"未知宿名：{name!r}")
    if name == "牛":
        raise ValueError("牛宿不能凭黄经映射成二十七宿；请按农历月日重新计算")
    return name


def sukuyo_relation(
    self_su: str,
    other_su: str,
    self_longitude: Optional[float] = None,
    other_longitude: Optional[float] = None,
) -> Dict[str, Any]:
    """Name-level helper. Longitudes never determine natal 宿."""
    return relation_between_su27(su28_to_su27(self_su), su28_to_su27(other_su))


def candidate_relation_analysis(
    first: Dict[str, Any], second: Dict[str, Any]
) -> Dict[str, Any]:
    resolved = first["natal_su27"] is not None and second["natal_su27"] is not None
    choices = [
        (
            [c["natal_su27"]]
            if c["natal_su27"] is not None
            else c.get("candidate_su27s", [])
        )
        for c in (first, second)
    ]
    complete = all(
        c["profile_calculation"][
            "candidate_set_complete_under_declared_reconstructions"
        ]
        for c in (first, second)
    )
    result: Dict[str, Any] = {
        "status": "not_needed" if resolved else "candidate_only",
        "candidate_set_complete_within_profile": complete,
        "rows": (
            [
                {
                    "person1_su27": a,
                    "person2_su27": b,
                    "person1_to_person2": relation_between_su27(a, b),
                    "person2_to_person1": relation_between_su27(b, a),
                    "pair": relation_between_su27(a, b)["pair"],
                    "applied_to_primary": False,
                }
                for a in choices[0]
                for b in choices[1]
            ]
            if not resolved
            else []
        ),
        "scope": "仅对已列候选作条件组合，不是已定相性；默认闰月政策未定时同名月候选不保证穷尽。排列按来源输入次序，不是优劣排名。",
    }
    if first.get("calendar_candidates") or second.get("calendar_candidates"):
        for row in result["rows"]:
            for label, context in (("person1", first), ("person2", second)):
                candidates = context.get("calendar_candidates", [context])
                name = row[f"{label}_su27"]
                row[f"{label}_calendar_dates"] = [
                    c["calendar_date"]
                    for c in candidates
                    if name
                    in ([c["natal_su27"]] if c["natal_su27"] else c["candidate_su27s"])
                ]
        result["calendar_date_uncertainty_remains"] = True
    from fatebridge.core.sukuyo_joint_candidates import (
        add_shared_reconstruction_support,
    )

    return add_shared_reconstruction_support(first, second, result)


def day_evidence(
    context: Dict[str, Any],
    natal_mansion: Optional[str] = None,
    activity: Optional[str] = None,
    activity_details: Optional[Sequence[str]] = None,
    textual_pada: Optional[int] = None,
) -> Dict[str, Any]:
    """T1299 day evidence, retaining separate upper and lower witnesses."""
    from fatebridge.core.sukuyo_six_palaces import six_palace_reference

    if context.get("calendar_candidates"):
        from fatebridge.core.sukuyo_date_support import (
            support_completeness_reading,
            support_interval_duration_reading,
        )

        alternatives = [
            day_evidence(c, natal_mansion, activity, activity_details, textual_pada)
            for c in context["calendar_candidates"]
        ]
        # Identical complete facts may survive, but never infer a common fact
        # when a possible date lies outside the validated calendar range.
        complete_dates = not context["out_of_range_calendar_dates"]
        result: Dict[str, Any] = {
            k: (
                deepcopy(v)
                if complete_dates and all(a.get(k) == v for a in alternatives)
                else None
            )
            for k, v in alternatives[0].items()
            if k not in {"calendar", "reading_text"}
        }
        result["calendar"] = context
        # These positions depend only on the supplied natal mansion. Missing
        # calendar coverage cannot erase a fact independent of the target date.
        result["six_palace_reference"] = six_palace_reference(natal_mansion)
        result["candidate_days"] = alternatives
        support_lines = "".join(
            f"参考历日{interval['calendar_date']}由UTC区间"
            f"[{interval['start_utc_inclusive']}, {interval['end_utc_exclusive']})支持。"
            + support_interval_duration_reading(interval)
            + "\n"
            for interval in (context.get("date_support") or {}).get(
                "utc_support_intervals", []
            )
        )
        result["reading_text"] = (
            f"出生当地日期{context['input_date']}（{context['input_timezone']}）对应多个可能{'日本历史参考' if context.get('calendar_basis') == HISTORICAL_CALENDAR_BASIS else '日本旧历参考' if context.get('calendar_basis') in JAPANESE_CALENDAR_BASES else '中国'}历日；未补造出生时刻。\n"
            + support_lines
            + support_completeness_reading(context)
            + "\n"
            + (
                "以上为左闭右开的可能时刻集合，不是实际出生时刻或概率；不据此选择唯一历日。\n"
                if support_lines
                else ""
            )
            + "\n".join(
                f"条件历日{a['calendar']['calendar_date']}：\n{a['reading_text']}"
                for a in alternatives
            )
            + (
                (
                    "\n还有超出该日本参考资料支持范围的可能历日，已列分支不穷尽。"
                    if context.get("calendar_basis") in JAPANESE_CALENDAR_BASES
                    else "\n还有超出1901至2099支持范围的可能历日，已列分支不穷尽。"
                )
                if not complete_dates
                else ""
            )
        )
        return result
    mansion = context["natal_su27"]
    from fatebridge.core.sukuyo_candidate_days import (
        mansion_nature,
        personal_day_evidence,
    )

    personal_day = personal_day_evidence(natal_mansion, mansion)
    nature = mansion_nature(mansion)
    day = context["lunar_day"]
    from fatebridge.core.sukuyo_weekday import civil_weekday

    weekday_reference = civil_weekday(
        context["calendar_date"], context.get("calendar_timezone", "")
    )
    weekday = weekday_reference["index_sunday_zero"]
    from fatebridge.core.sukuyo_special_days import special_day_evidence

    special_evidence = special_day_evidence(
        mansion,
        weekday,
        context.get("candidate_su27s", []),
        weekday_basis=weekday_reference["basis"],
    )
    special_matches = special_evidence["primary"]["matched_labels"]
    activities = {
        "安重": ["长期营建", "园林仓储", "结交与婚礼"],
        "和善": ["问学技艺", "音乐礼仪", "求婚与冠带出行"],
        "急速": ["买卖交关", "进路出行", "入学受业"],
        "轻燥": ["使节往来", "舟行", "礼乐与种植"],
        "刚柔": ["金属与器具工艺", "买卖", "入宅与盟会"],
        "毒害": [],
        "猛恶": [],
    }
    result = {
        "calendar": context,
        "six_palace_reference": six_palace_reference(natal_mansion),
        "personal_day": personal_day,
        "day_mansion": mansion,
        "weekday": weekday_reference,
        "lunar_half": "白" if day <= 15 else "黑",
        "half_day": (day - 1) % 15 + 1,
        "nature": nature,
        "nature_ruleset": "t1299_upper_seven_natures_v1",
        "traditional_activity_examples": activities.get(nature, []) if nature else [],
        "activity_scope": "上卷文化性释义，非现实行动许可；不输出原文中的伤害或医疗操作指令。",
        "special_day_labels": special_matches,
        "special_day_evidence": special_evidence,
        "special_day_source": {
            "source": TEXT_URL,
            "locator": "T21n1299_p0392c17-28",
            "scope": "上卷七曜与宿组合；不将标签当事件概率。",
            "ruleset_id": special_evidence["ruleset_id"],
            "witness": "upper_taisho",
        },
        "rule_trace": [
            {
                "rule_id": "t1299_upper_seven_natures",
                "input": mansion,
                "output": nature,
                "source": TEXT_URL,
                "locator": "T21n1299_p0390c16-p0391a26",
            }
        ],
        "interpretation_scope": "七类名称为原典术语；不据此判定个人品德、疾病、灾祸或现实必然结果。",
        "textual_variants": [
            "nature字段保留上卷；lower_methods另列下卷七宿性与七曜章法，胃/牛、轻宿标题及卖/买卖异文分开保留，不静默替换。"
        ]
        + (
            [
                "上卷月曜主文私精与下卷私情字面不同；上卷旅行条文未补定，因私条件仅应用下卷。"
            ]
            if weekday == 1
            else []
        ),
    }
    from fatebridge.core.sukuyo_activities import assess_activity
    from fatebridge.core.sukuyo_calendar_text import (
        calendar_day_evidence,
        render_day_reading,
    )
    from fatebridge.core.sukuyo_directions import travel_direction_evidence
    from fatebridge.core.sukuyo_lower import (
        conjunction_doctrine,
        lower_mansion_evidence,
    )
    from fatebridge.core.sukuyo_lower_methods import lower_methods_evidence
    from fatebridge.core.sukuyo_padas import palace_reference
    from fatebridge.core.sukuyo_taibai import taibai_direction_reference

    result["calendar_day"] = calendar_day_evidence(
        day,
        host_calendar_label=(
            "日本旧历参考"
            if context.get("calendar_basis") in JAPANESE_CALENDAR_BASES
            else "中国农历"
        ),
    )
    from fatebridge.core.sukuyo_kenyu import printed_clock_reference

    result["calendar_day"]["clock_doctrine"]["kenyu_printed_reference"] = (
        printed_clock_reference(
            result["weekday"]["luminary"], result["weekday"]["basis"]
        )
    )
    result["palace_reference"] = palace_reference(context, textual_pada)
    result["taibai_direction_reference"] = taibai_direction_reference(day)
    result["lower_mansion_day"] = lower_mansion_evidence(mansion)
    result["lower_methods"] = lower_methods_evidence(
        mansion,
        result["weekday"]["luminary"],
        nature,
        weekday_basis=result["weekday"]["basis"],
    )
    result["conjunction_doctrine"] = conjunction_doctrine(
        mansion, context.get("candidate_su27s", [])
    )
    result["directional_travel"] = travel_direction_evidence(
        mansion, context.get("candidate_su27s", [])
    )
    if activity == "clothing":
        from fatebridge.core.sukuyo_clothing import clothing_reference

        result["clothing_reference"] = clothing_reference(context)
    result["candidate_days"] = []
    from fatebridge.core.sukuyo_kenyu_lingbi import conditional_lingbi_reference

    result["kenyu_lingbi_reference"] = conditional_lingbi_reference(
        context,
        (
            result["personal_day"]["relation"]["relation"]
            if result["personal_day"]
            else None
        ),
    )
    result["activity_assessment"] = assess_activity(result, activity, activity_details)
    from fatebridge.core.sukuyo_candidate_days import candidate_mansion_days

    result["candidate_mansion_days"] = candidate_mansion_days(
        result, natal_mansion, activity, activity_details
    )
    result["reading_text"] = render_day_reading(result)
    return result
