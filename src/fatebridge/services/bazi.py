"""Standalone BaZi tool surfaces for FateBridge."""

from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any, Callable

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import (
    build_calendar_context,
    current_local_datetime,
    get_solar_terms_for_year,
    localize_datetime,
)
from fatebridge.core.bazi.calendar import (
    BaZiCalendar,
    ChangshengSchool,
    DutyProfile,
    ZiHourPolicy,
    build_taixi,
    build_three_origins,
)
from fatebridge.core.bazi.relations import (
    collect_target_branch_relations,
    group_relations,
    pair_relations,
)
from fatebridge.core.bazi.shensha import (
    GU_CHEN_TARGETS,
    GUA_SU_TARGETS,
    GUO_YIN_TARGETS,
    HONG_LUAN_TARGETS,
    JIANG_XING_TARGETS,
    LU_SHEN_TARGETS,
    PEACH_BLOSSOM_TARGETS,
    TIAN_XI_TARGETS,
    TIAN_YI_TABLES,
    TRAVEL_HORSE_TARGETS,
    WEN_CHANG_TARGETS,
    build_shensha_profile,
)
from fatebridge.core.bazi.timing import TimingAnalysis
from fatebridge.services.birth_context import (
    BirthComputationContext,
    build_birth_computation_context,
)
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.services.timing_state import (
    build_current_timing_state,
    calculate_analysis_age,
)
from fatebridge.utils.birth_input import PersonInfo, normalize_gender
from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    SEXAGENARY_INDEX,
    TenGod,
    get_ten_god,
    iter_pillar_gods,
)
from fatebridge.utils.errors import (
    ParameterError,
    calculation_guard,
)
from fatebridge.utils.formatting import create_pillar_dict

_ORDER = ("year", "month", "day", "hour")

BRANCH_COMPASS_DIRECTIONS: dict[str, str] = {
    "子": "正北",
    "丑": "东北偏北",
    "寅": "东北偏东",
    "卯": "正东",
    "辰": "东南偏东",
    "巳": "东南偏南",
    "午": "正南",
    "未": "西南偏南",
    "申": "西南偏西",
    "酉": "正西",
    "戌": "西北偏西",
    "亥": "西北偏北",
}


def _group_branch_target(
    branch: str, mappings: tuple[tuple[tuple[str, ...], str], ...]
) -> str:
    return next(target for grp, target in mappings if branch in grp)


_TOPICS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "career": (
        ("正官", "七杀", "正印", "偏印", "食神", "伤官", "正财", "偏财"),
        ("month",),
    ),
    "wealth": (("正财", "偏财", "食神", "伤官", "比肩", "劫财"), ()),
    "education": (("正印", "偏印", "食神", "伤官", "正官", "七杀"), ("month",)),
    "personality": (tuple(g.value for g in TenGod), ()),
    "health": ((), ()),
    "relatives": (("偏财", "正印", "比肩", "劫财"), ("year", "month")),
    "marriage": ((), ("day",)),
    "romance": ((), ("day",)),
    "children": ((), ("hour",)),
}


def _resolve_analysis_date(
    analysis_year: int | None,
    analysis_month: int | None,
    analysis_day: int | None,
    *,
    timezone_name: str | None = None,
) -> datetime:
    if (
        analysis_year is not None
        and analysis_month is not None
        and analysis_day is not None
    ):
        return datetime(analysis_year, analysis_month, analysis_day)
    now = (
        current_local_datetime(timezone_name)
        if timezone_name is not None
        else current_local_datetime()
    )
    year = analysis_year if analysis_year is not None else now.year
    month = analysis_month if analysis_month is not None else now.month
    day = analysis_day if analysis_day is not None else now.day
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(day, last_day))


def _build_timing_overview(
    *,
    birth_context: BirthComputationContext,
    analysis_date: datetime,
    analysis_calendar_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timing_state = build_current_timing_state(
        birth_context,
        analysis_date=analysis_date,
        include_interactions=False,
    )
    dayun_result = timing_state["dayun_analysis"]
    liunian_result = timing_state["liunian_analysis"]
    liuyue_result = timing_state["liuyue_analysis"]
    liuri_result = timing_state["liuri_analysis"]
    liushi_result = timing_state["liushi_analysis"]

    if "dayun_info" in dayun_result:
        dayun_payload: dict[str, Any] = {
            "pillar": dayun_result["dayun_info"]["pillar"],
            "start_age": dayun_result["age_info"]["start_age"],
            "start_age_precise": dayun_result["age_info"].get("start_age_precise"),
            "dayun_age": dayun_result["age_info"]["dayun_age"],
            "years_in_period": dayun_result["age_info"]["years_in_period"],
            "selection_basis": dayun_result["age_info"]["selection_basis"],
            "start_at": dayun_result["dayun_info"]["start_at"],
            "end_at": dayun_result["dayun_info"]["end_at"],
            "child_limit": dayun_result.get("child_limit"),
        }
    elif dayun_result.get("status") == "before_dayun":
        dayun_payload = {
            "pillar": None,
            "status": "before_dayun",
            "child_limit": dayun_result["child_limit"],
            "xiaoyun": dayun_result["xiaoyun_info"],
            "first_dayun": dayun_result["first_dayun"],
        }
    else:
        dayun_payload = {
            "pillar": None,
            "status": dayun_result.get("status"),
            "message": dayun_result.get("message", "大运信息不可用"),
        }

    liuyue_info = liuyue_result["liuyue_info"]
    liuri_info = liuri_result["liuri_info"]
    liushi_info = liushi_result["liushi_info"]
    current_solar_term_name = (
        (analysis_calendar_context or {})
        .get("current_solar_term", {})
        .get("name", "未知")
    )
    next_solar_term_name = (
        (analysis_calendar_context or {}).get("next_solar_term", {}).get("name", "未知")
    )

    return {
        "analysis_date": analysis_date.strftime("%Y-%m-%d"),
        "dayun": dayun_payload,
        "liunian": {
            "pillar": liunian_result["liunian_info"]["pillar"],
            "stem_ten_god": liunian_result["liunian_info"]["stem_ten_god"],
        },
        "liuyue": {
            "pillar": liuyue_info["pillar"],
            "start_term": liuyue_info["solar_term_window"]["start_term"]["name"],
            "end_term": liuyue_info["solar_term_window"]["next_term"]["name"],
        },
        "liuri": {
            "pillar": liuri_info["pillar"],
            "weekday": liuri_info["weekday"],
        },
        "liushi": {
            "pillar": liushi_info["pillar"],
            "hour": liushi_info["hour"],
            "shichen": liushi_info["shichen"],
        },
        "current_jieqi": liuyue_info["solar_term_window"]["start_term"]["name"],
        "next_jieqi": liuyue_info["solar_term_window"]["next_term"]["name"],
        "current_solar_term_name": current_solar_term_name,
        "next_solar_term_name": next_solar_term_name,
    }


@calculation_guard("命理分析计算")
def calculate_bazi_overview(
    person: PersonInfo,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    return build_destiny_payload(context)


@calculation_guard("八字命盘")
def calculate_bazi_birth(
    person: PersonInfo,
    *,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    normalized = birth_context.normalized_birth_time
    analysis_date = _resolve_analysis_date(
        analysis_year,
        analysis_month,
        analysis_day,
        timezone_name=normalized.timezone,
    )
    base_analysis = build_destiny_payload(birth_context)
    three_origins = build_three_origins(birth_context.birth_pillars)
    taixi = build_taixi(birth_context.birth_pillars)
    shensha_profile = build_shensha_profile(
        pillars=birth_context.birth_pillars,
        three_origins=three_origins,
        taixi=taixi,
    )
    analysis_pillars = BaZiCalendar.get_four_pillars(
        analysis_date,
        timezone_name=normalized.timezone,
        zi_hour_policy=zi_hour_policy,
    )
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=normalized.timezone,
        pillars=analysis_pillars,
    )
    timing_overview = _build_timing_overview(
        birth_context=birth_context,
        analysis_date=analysis_date,
        analysis_calendar_context=analysis_calendar_context,
    )
    return {
        "analysis_type": "八字命盘",
        **(
            {"coverage": base_analysis["coverage"]}
            if "coverage" in base_analysis
            else {}
        ),
        "bazi_birth": {
            "engine": "fatebridge-offline",
            "time_algorithm": (
                "三柱模式(时辰未知)"
                if getattr(person, "birth_time_unknown", False)
                else ("真太阳时" if normalized.applied else "直接时间")
            ),
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            **(
                {"coverage": base_analysis["coverage"]}
                if "coverage" in base_analysis
                else {}
            ),
            "person_info": base_analysis["person_info"],
            "four_pillars": base_analysis["four_pillars"],
            "three_origins": three_origins,
            "taixi": taixi,
            "day_master": base_analysis["day_master"],
            "element_distribution": base_analysis["element_distribution"],
            "element_seasonal_phase": base_analysis["element_seasonal_phase"],
            "favorable_elements": base_analysis["favorable_elements"],
            "favorable_elements_status": base_analysis["favorable_elements_status"],
            "avoid_elements": base_analysis["avoid_elements"],
            "structure_profile": base_analysis["structure_profile"],
            "intra_month_duty": base_analysis["intra_month_duty"],
            "ten_gods": base_analysis["ten_gods"],
            "patterns": base_analysis["patterns"],
            "kongwang": shensha_profile["kongwang"],
            "shensha": shensha_profile["natal_entries"],
            "shensha_triggered": shensha_profile["triggered_natal"],
            "three_origins_shensha": shensha_profile["three_origins_entries"],
            "calendar_context": base_analysis["calendar_context"],
            "analysis_calendar_context": analysis_calendar_context,
            "timing_overview": timing_overview,
        },
    }


def _parse_pillar_str(
    pillar_str: str | None, field_name: str = "pillar"
) -> tuple[str, str] | None:
    if pillar_str is None:
        return None
    if not isinstance(pillar_str, str) or pillar_str not in SEXAGENARY_INDEX:
        raise ParameterError(
            "覆盖柱必须为六十甲子中的完整两字干支",
            [{"path": field_name, "code": "invalid_sexagenary_pillar"}],
        )
    return (pillar_str[0], pillar_str[1])


def _derive_current_pillars(
    birth_context: BirthComputationContext,
    analysis_date: datetime,
    gender: str,
) -> tuple[tuple[str, str] | None, tuple[str, str] | None, dict[str, Any]]:
    normalized = birth_context.normalized_birth_time
    timezone_name = normalized.timezone
    dayun_result = TimingEffectsAnalysis.analyze_dayun_effects(
        birth_context.birth_pillars,
        normalized.input_datetime,
        gender,
        calculate_analysis_age(normalized.input_datetime, analysis_date),
        timezone_name=timezone_name,
        original_element_counts=birth_context.original_element_counts,
        analysis_moment=analysis_date,
        allow_missing_gender=True,
    )
    dayun_info = dayun_result.get("dayun_info", {})
    dayun_pillar_str = dayun_info.get("pillar")
    liunian_pillar_str = TimingAnalysis.calculate_liunian(
        analysis_date.year, moment=analysis_date, timezone_name=timezone_name
    )["pillar"]
    anchor = localize_datetime(analysis_date, timezone_name)
    year_boundaries = [
        term
        for term in get_solar_terms_for_year(anchor.year, timezone_name)
        if term.name == "立春"
        and term.has_defined_local_clock
        and term.moment.date() == anchor.date()
    ]
    context: dict[str, Any] = {
        "analysis_date": analysis_date.strftime("%Y-%m-%d"),
        "analysis_datetime": anchor.isoformat(),
        "timezone": timezone_name,
        "input_granularity": "date",
        "anchor_policy": "local_midnight",
        "year_boundary_policy": "lichun_exact_moment",
        "boundary_status": (
            "year_boundary_day" if year_boundaries else "not_year_boundary_day"
        ),
        "boundaries_on_date": [term.as_dict() for term in year_boundaries],
        "dayun_pillar": dayun_pillar_str,
        "liunian_pillar": liunian_pillar_str,
        "dayun_age": (dayun_result.get("age_info") or {}).get("dayun_age"),
        "dayun_selection_basis": (dayun_result.get("age_info") or {}).get(
            "selection_basis"
        ),
        "dayun_start_at": (dayun_result.get("dayun_info") or {}).get("start_at"),
        "dayun_end_at": (dayun_result.get("dayun_info") or {}).get("end_at"),
        "source": "auto-derived",
    }
    if dayun_result.get("status") == "before_dayun":
        context["dayun_status"] = "before_dayun"
        context["child_limit"] = dayun_result["child_limit"]
        context["xiaoyun_pillar"] = dayun_result["xiaoyun_info"]["pillar"]
        context["xiaoyun"] = dayun_result["xiaoyun_info"]
    elif "status" in dayun_result:
        context["dayun_status"] = (
            "unavailable_gender_direction"
            if dayun_result["status"] == "unavailable_missing_gender"
            else dayun_result["status"]
        )
        context["message"] = dayun_result.get("message")
    return (
        _parse_pillar_str(dayun_pillar_str),
        _parse_pillar_str(liunian_pillar_str),
        context,
    )


def _build_lean_topic_facts(
    *,
    context: BirthComputationContext,
    topic: str,
    gender: str,
    dayun: tuple[str, str] | None,
    liunian: tuple[str, str] | None,
) -> dict[str, Any]:
    pillars = context.birth_pillars
    day_stem = pillars["day"][0]
    norm_gender = normalize_gender(gender)
    focus, palaces = _TOPICS[topic]

    if topic in ("marriage", "romance", "children"):
        male = ("正官", "七杀") if topic == "children" else ("正财", "偏财")
        female = ("食神", "伤官") if topic == "children" else ("正官", "七杀")
        focus = (
            male
            if norm_gender == "男"
            else female if norm_gender == "女" else male + female
        )

    gods: dict[str, list[dict[str, str]]] = {g.value: [] for g in TenGod}
    for entry in iter_pillar_gods({n: pillars[n] for n in _ORDER}, day_stem):
        gods[entry.ten_god.value].append(
            {
                "pillar": entry.pillar,
                "stem": entry.char,
                "branch": entry.branch,
                "location": entry.location,
            }
        )

    natal_stars = [
        {
            "ten_god": god,
            "visible_in": [e["pillar"] for e in gods[god] if e["location"] == "天干"],
            "hidden_in": [
                f"{e['pillar']}({e['branch']})"
                for e in gods[god]
                if e["location"] == "地支藏干"
            ],
        }
        for god in focus
        if gods[god]
    ]

    temporal = {
        n: p for n, p in (("dayun", dayun), ("liunian", liunian)) if p is not None
    }

    marker_targets: list[tuple[str, str, str]] = []
    if topic == "career":
        for target in TIAN_YI_TABLES["standard"][day_stem]:
            marker_targets.append(("天乙贵人", "day_stem", target))
        marker_targets.append(("禄神", "day_stem", LU_SHEN_TARGETS[day_stem]))
        for pos in ("year", "day"):
            b = pillars[pos][1]
            marker_targets.append(
                ("驿马", f"{pos}_branch", _group_branch_target(b, TRAVEL_HORSE_TARGETS))
            )
            marker_targets.append(
                ("将星", f"{pos}_branch", _group_branch_target(b, JIANG_XING_TARGETS))
            )
        marker_targets.append(("国印贵人", "day_stem", GUO_YIN_TARGETS[day_stem]))
        marker_targets.append(("文昌", "day_stem", WEN_CHANG_TARGETS[day_stem]))
    if topic == "education":
        marker_targets.append(("文昌", "day_stem", WEN_CHANG_TARGETS[day_stem]))
    if topic in ("marriage", "romance"):
        yb = pillars["year"][1]
        marker_targets.extend(
            (
                ("红鸾", "year_branch", HONG_LUAN_TARGETS[yb]),
                ("天喜", "year_branch", TIAN_XI_TARGETS[yb]),
            )
        )
        for pos in ("year", "day"):
            b = pillars[pos][1]
            t = _group_branch_target(b, PEACH_BLOSSOM_TARGETS)
            marker_targets.append(("咸池", f"{pos}_branch", t))
    if topic == "marriage":
        yb = pillars["year"][1]
        marker_targets.extend(
            (
                ("孤辰", "year_branch", GU_CHEN_TARGETS[yb]),
                ("寡宿", "year_branch", GUA_SU_TARGETS[yb]),
            )
        )

    markers = [
        {
            "name": name,
            "anchor": anchor,
            "target_branch": target,
            **(
                {"direction": BRANCH_COMPASS_DIRECTIONS[target]}
                if name == "天乙贵人"
                else {}
            ),
            "natal_positions": [p for p in _ORDER if pillars[p][1] == target],
            "timing_layers": [
                layer for layer, (_, b) in temporal.items() if b == target
            ],
        }
        for name, anchor, target in marker_targets
    ]

    timing_layers = []
    for layer_name, (t_stem, t_branch) in temporal.items():
        incoming_gods = [
            {
                "stem": t_stem,
                "location": "天干",
                "ten_god": get_ten_god(day_stem, t_stem).value,
                "in_topic": get_ten_god(day_stem, t_stem).value in focus,
            },
            *[
                {
                    "stem": h,
                    "location": "地支藏干",
                    "ten_god": get_ten_god(day_stem, h).value,
                    "in_topic": get_ten_god(day_stem, h).value in focus,
                }
                for h in BRANCH_HIDDEN_STEMS[t_branch]
            ],
        ]
        rels = collect_target_branch_relations(
            t_branch, pillars, layer_name, target_stem=t_stem
        )
        palace_hits = [
            r
            for r in rels
            if r.get("with_pillar") in palaces
            or any(p in palaces for p in r.get("with_pillars", ()))
        ]
        timing_layers.append(
            {
                "layer": layer_name,
                "pillar": f"{t_stem}{t_branch}",
                "stars": incoming_gods,
                "natal_relations": rels,
                "palace_hits": palace_hits,
            }
        )

    natal_palaces = {
        palace: [
            r
            for other in _ORDER
            if other != palace
            for r in pair_relations(palace, other, pillars)
        ]
        for palace in palaces
    }

    ea = context.element_analysis
    return {
        "topic": topic,
        "four_pillars": create_pillar_dict(pillars),
        "day_master": {
            "stem": day_stem,
            "element": ea["day_master"]["element"],
            "strength": ea["day_master"]["strength"],
        },
        "favorable_elements": ea["favorable_elements"],
        "avoid_elements": ea["avoid_elements"],
        "dominant_structure": ea["structure_profile"]["dominant_structure"]["label"],
        "structure_detail": ea["structure_profile"]["dominant_structure"],
        "seasonal_climate": ea["structure_profile"]["seasonal_climate"],
        "element_distribution": ea["element_distribution"],
        "element_seasonal_phase": ea["element_seasonal_phase"],
        "natal_stars": natal_stars,
        "markers": markers,
        "palace_relations": natal_palaces,
        "natal_groups": group_relations(pillars),
        "timing_layers": timing_layers,
    }


def _run_bazi_dimension_analysis(
    person: PersonInfo,
    *,
    topic: str,
    analysis_type: str,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    dayun_pillar: str | None = None,
    liunian_pillar: str | None = None,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    dayun = _parse_pillar_str(dayun_pillar, "dayun_pillar")
    liunian = _parse_pillar_str(liunian_pillar, "liunian_pillar")
    birth_context = build_birth_computation_context(
        person,
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
    )
    gender = normalize_gender(person.gender)

    if dayun is None or liunian is None:
        analysis_date = _resolve_analysis_date(
            analysis_year,
            analysis_month,
            analysis_day,
            timezone_name=birth_context.normalized_birth_time.timezone,
        )
        auto_dayun, auto_liunian, timing_context = _derive_current_pillars(
            birth_context, analysis_date, gender
        )
        timing_context["overridden"] = {
            "dayun_pillar": dayun is not None,
            "liunian_pillar": liunian is not None,
        }
        if dayun is None:
            dayun = auto_dayun
        if liunian is None:
            liunian = auto_liunian
        timing_context["dayun_pillar"] = "".join(dayun) if dayun else None
        timing_context["liunian_pillar"] = "".join(liunian) if liunian else None
        if timing_context["overridden"]["dayun_pillar"]:
            timing_context.update(
                dayun_status="explicit_override",
                dayun_selection_basis=None,
                dayun_start_at=None,
                dayun_end_at=None,
            )
    else:
        timing_context = {
            "dayun_pillar": "".join(dayun),
            "liunian_pillar": "".join(liunian),
            "source": "explicit_pillar_overrides",
            "dayun_status": "explicit_override",
            "overridden": {"dayun_pillar": True, "liunian_pillar": True},
        }

    topic_facts = _build_lean_topic_facts(
        context=birth_context,
        topic=topic,
        gender=gender,
        dayun=dayun,
        liunian=liunian,
    )
    return {
        "analysis_type": analysis_type,
        f"{topic}_analysis": {
            "calendar_context": birth_context.birth_calendar_context,
            "timing_context": timing_context,
            "topic_facts": topic_facts,
        },
    }


def _make_bazi_dimension_service(
    topic: str,
    analysis_type: str,
) -> Callable[..., dict[str, Any]]:
    @calculation_guard(analysis_type)
    def service(
        person: PersonInfo,
        *,
        analysis_year: int | None = None,
        analysis_month: int | None = None,
        analysis_day: int | None = None,
        dayun_pillar: str | None = None,
        liunian_pillar: str | None = None,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
        changsheng_school: ChangshengSchool = "fire_earth_same_palace",
        duty_profile: DutyProfile = "sanming",
    ) -> dict[str, Any]:
        return _run_bazi_dimension_analysis(
            person,
            topic=topic,
            analysis_type=analysis_type,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
            dayun_pillar=dayun_pillar,
            liunian_pillar=liunian_pillar,
            zi_hour_policy=zi_hour_policy,
            changsheng_school=changsheng_school,
            duty_profile=duty_profile,
        )

    return service


calculate_bazi_marriage = _make_bazi_dimension_service("marriage", "八字婚姻分析")
calculate_bazi_career = _make_bazi_dimension_service("career", "八字事业分析")
calculate_bazi_wealth = _make_bazi_dimension_service("wealth", "八字财运分析")
calculate_bazi_health = _make_bazi_dimension_service("health", "八字健康分析")
calculate_bazi_children = _make_bazi_dimension_service("children", "八字子女分析")
calculate_bazi_education = _make_bazi_dimension_service("education", "八字学业分析")
calculate_bazi_personality = _make_bazi_dimension_service("personality", "八字性格分析")
calculate_bazi_relatives = _make_bazi_dimension_service("relatives", "八字六亲分析")
calculate_bazi_romance = _make_bazi_dimension_service("romance", "八字正缘桃花分析")
