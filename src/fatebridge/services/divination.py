"""
FateBridge divination services.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Literal

from fatebridge.core.almanac import (
    LUNAR_SUPPORTED_SOLAR_END,
    LUNAR_SUPPORTED_SOLAR_START,
    build_calendar_context,
    get_day_ganzhi,
)
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.core.divination import build_meihua_interpretation, lookup_gua
from fatebridge.core.heluo.judgment import (
    DEFAULT_MONTH_ASSIGNMENT,
    MonthAssignmentMethod,
)
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.local_techniques.sanshi import build_sanshiunited_result
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.core.local_techniques.suzhan import build_suzhan_result
from fatebridge.core.local_techniques.tongshefa import build_tongshefa_result
from fatebridge.core.meihua.casting import (
    MeihuaUnspecifiedClockError,
    apply_clock_input_notice,
    clock_components,
    resolve_meihua_cast_datetime,
    resolve_meihua_clock,
)
from fatebridge.core.meihua.relations import build_meihua_evidence
from fatebridge.core.meihua.texts import (
    calendar_label_precision,
    solar_reference_notice,
    solar_term_date_reference,
)
from fatebridge.core.meihua.topics import (
    apply_day_qi,
    apply_external_omens,
    apply_motion_context,
    apply_observation_context,
    apply_postheaven_count_reference,
    apply_qi_branch_timing_references,
    apply_qi_day_timing_references,
    apply_reputation_supplement,
    apply_situational_responses,
    apply_stage_emphasis,
    apply_trigram_relation_symbols,
)
from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.core.sukuyo.calendar import _basis_parameters as basis_parameters
from fatebridge.core.sukuyo.calendar import calendar_mansion, rulesets
from fatebridge.core.sukuyo.sanjiu import (
    DistanceRule,
    candidate_relation_analysis,
    relation_between_su27,
)
from fatebridge.core.sukuyo.texts import (
    joint_reconstruction_contract,
    palace_reference,
)
from fatebridge.core.zhouyi import classical_hexagram
from fatebridge.utils.errors import ParameterError, calculation_guard
from fatebridge.utils.formatting import create_pillar_dict
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE


def _civil_day_qi_context(moment: datetime, *, bazi_day_ganzhi: str) -> dict[str, Any]:
    """Build civil midnight vs. 23:00 zi-hour day-ganzhi candidates for Meihua."""
    civil = moment.date()
    selected = get_day_ganzhi(civil.year, civil.month, civil.day)
    zi_date = civil + timedelta(days=int(moment.hour == 23))
    zi = get_day_ganzhi(zi_date.year, zi_date.month, zi_date.day)
    candidates = [
        {
            "id": "local_midnight",
            "date": civil.isoformat(),
            "ganzhi": selected,
            "day_branch": selected[1],
        }
    ]
    if moment.hour == 23:
        candidates.append(
            {
                "id": "zi_start",
                "date": zi_date.isoformat(),
                "ganzhi": zi,
                "day_branch": zi[1],
            }
        )
    return {
        "selected_candidate_id": "local_midnight",
        "candidates": candidates,
        "bazi_day_ganzhi": bazi_day_ganzhi,
    }


@calculation_guard("梅花时卦分析")
def calculate_meihua_analysis(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int | None = None,
    analysis_second: int | None = None,
    analysis_timezone: str | None = None,
    analysis_utc_offset: str | None = None,
    analysis_longitude: float | None = None,
    use_true_solar_time: bool = False,
    question: str | None = None,
    interpretation_topic: str = "general",
    weather_context: dict[str, Any] | None = None,
    external_observations: list[dict[str, Any]] | None = None,
    matter_scenario: str | None = None,
    observer_activity: str | None = None,
    observation_context: dict[str, Any] | None = None,
    response_context: dict[str, Any] | None = None,
    reputation_context: dict[str, Any] | None = None,
    _clock_supplied_components: list[str] | None = None,
) -> dict[str, Any]:
    """
    梅花时卦分析工具 - 按指定时刻生成本卦、变卦、互卦、错卦、综卦与体用关系。
    """
    options = MeihuaInterpretationOptions.model_validate(
        {
            "interpretation_topic": interpretation_topic,
            "weather_context": weather_context,
            "reputation_context": reputation_context,
            "response_context": response_context,
            "observation_context": observation_context,
            "observer_activity": observer_activity,
            "matter_scenario": matter_scenario,
            "external_observations": external_observations,
        }
    )
    timezone_name = analysis_timezone or DEFAULT_BIRTH_TIMEZONE
    if analysis_minute is not None and (
        type(analysis_minute) is not int or not 0 <= analysis_minute <= 59
    ):
        return ParameterError(
            "analysis_minute须为已确认的0至59整数分钟；未知时省略。",
            [{"path": "analysis_minute", "code": "invalid_civil_minute"}],
        ).as_result()
    if analysis_second is not None and (
        type(analysis_second) is not int or not 0 <= analysis_second <= 59
    ):
        return ParameterError(
            "analysis_second须为已确认的0至59整秒；未知时省略，不支持闰秒标签60。",
            [{"path": "analysis_second", "code": "invalid_civil_second"}],
        ).as_result()

    supplied_clock = clock_components(
        analysis_minute, analysis_second, _clock_supplied_components
    )
    analysis_datetime = datetime(
        analysis_year,
        analysis_month,
        analysis_day,
        analysis_hour,
        0 if analysis_minute is None else analysis_minute,
        0 if analysis_second is None else analysis_second,
    )
    try:
        analysis_datetime, clock_resolution = resolve_meihua_clock(
            analysis_datetime,
            timezone_name,
            analysis_utc_offset,
            seconds_supplied="second" in supplied_clock,
            minute_supplied="minute" in supplied_clock,
            component_provenance=(
                "bound_request_model_fields_set"
                if _clock_supplied_components is not None
                else "direct_service_optional_components"
            ),
        )
    except MeihuaUnspecifiedClockError as error:
        return ParameterError(
            str(error),
            [{"path": "analysis_timezone", "code": "unresolved_timezone_offset"}],
        ).as_result()
    except ParameterError as error:
        return {**error.as_result(), "status_code": 422}
    if (
        not LUNAR_SUPPORTED_SOLAR_START
        <= analysis_datetime.date()
        <= LUNAR_SUPPORTED_SOLAR_END
    ):
        return {
            "error": (
                f"起卦日期超出农历支持区间{LUNAR_SUPPORTED_SOLAR_START.isoformat()}"
                f"至{LUNAR_SUPPORTED_SOLAR_END.isoformat()}。"
            ),
            "error_code": "validation_error",
            "status_code": 422,
            "retryable": False,
            "issues": [{"path": "analysis_date", "code": "unsupported_calendar_date"}],
        }

    cast_datetime, solar_meta = resolve_meihua_cast_datetime(
        analysis_datetime,
        timezone_name=timezone_name,
        longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
    )
    pillars = BaZiCalendar.get_four_pillars(
        cast_datetime,
        timezone_name=timezone_name,
    )
    calendar_context = build_calendar_context(
        cast_datetime,
        timezone_name=timezone_name,
        pillars=pillars,
    )
    lunar_calendar = calendar_context.get("lunar_calendar") or {}
    raw_meihua = lunar_calendar.get("meihua")
    meihua = deepcopy(raw_meihua) if raw_meihua else None

    if not meihua:
        # A missing lunar context is a runtime-dependency problem, not a
        # user-input problem, so surface it as 503 with an explicit
        # error_code so clients and the HTTP layer can distinguish it.
        return {
            "error": "当前环境缺少农历上下文，无法生成梅花时卦。",
            "analysis_type": "梅花时卦分析",
            "error_code": "dependency_missing",
            "status_code": 503,
            "retryable": False,
        }

    meihua.update(
        {
            "ruleset_id": "meihua_lunar_time_v1",
            "year_boundary": "lunar_new_year",
            "leap_month_rule": "use_lunar_month_number_without_increment",
            "mutual_rule": "qian_kun_use_changed_hexagram_otherwise_base",
        }
    )
    for key in (
        "base_hexagram",
        "changed_hexagram",
    ):
        meihua[key]["classical"] = classical_hexagram(meihua[key]["binary_code"])
    meihua.update(
        build_meihua_evidence(
            meihua,
            lunar_year=lunar_calendar["year"],
            is_leap_month=lunar_calendar["is_leap_month"],
            timezone_name=timezone_name,
            month_branch=calendar_context["bazi_month_boundary"]["branch"],
        )
    )
    meihua["calendar_policy"]["true_solar_time_applied"] = solar_meta[
        "true_solar_time_applied"
    ]
    meihua["calendar_policy"]["civil_clock_resolution"] = clock_resolution
    label_precision = calendar_label_precision(analysis_datetime.date())
    meihua["calendar_policy"]["label_precision"] = label_precision
    solar_reference = solar_term_date_reference(calendar_context)
    meihua["calendar_policy"]["solar_term_date_reference"] = solar_reference
    calendar_context["lunar_calendar"] = {**lunar_calendar, "meihua": meihua}
    interpretation = build_meihua_interpretation(
        meihua,
        interpretation_topic=interpretation_topic,
        weather_context=weather_context,
    )
    if label_precision["matched_events"]:
        interpretation["comprehensive_judgement"] += (
            " 本次沿用已公布历表取数；相关朔日被香港天文台列为可能相差一日，"
            "当前日期位于明示的软件复核范围。如历表月日修订，须重新起算；"
            "此处没有推定另一套日期或卦象。"
        )

    apply_external_omens(
        meihua,
        interpretation,
        (
            [
                item.model_dump(mode="json", exclude_none=True)
                for item in options.external_observations
            ]
            if options.external_observations is not None
            else None
        ),
    )

    apply_stage_emphasis(
        meihua,
        interpretation,
        matter_scenario=options.matter_scenario,
        scenario_fact_path="analysis_context.matter_scenario",
    )

    apply_motion_context(
        meihua,
        interpretation,
        observer_activity=options.observer_activity,
        observer_fact_path="analysis_context.observer_activity",
    )

    apply_postheaven_count_reference(meihua, interpretation)

    normalized_observation = (
        options.observation_context.model_dump(mode="json")
        if options.observation_context is not None
        else None
    )
    apply_observation_context(
        meihua,
        interpretation,
        normalized_observation,
        context_fact_path="analysis_context.observation_context",
    )

    apply_day_qi(
        meihua,
        interpretation,
        (
            _civil_day_qi_context(
                analysis_datetime, bazi_day_ganzhi=str(lunar_calendar["day_ganzhi"])
            )
            if interpretation_topic != "weather"
            else None
        ),
    )

    normalized_response = (
        options.response_context.model_dump(mode="json")
        if options.response_context is not None
        else None
    )
    apply_situational_responses(
        meihua,
        interpretation,
        normalized_response,
        context_fact_path="analysis_context.response_context",
    )
    reference_notice = solar_reference_notice(solar_reference)
    if reference_notice is not None:
        interpretation["solar_term_date_reference_notice"] = reference_notice
        interpretation["comprehensive_judgement"] += " " + reference_notice

    apply_trigram_relation_symbols(meihua, interpretation)

    normalized_reputation = (
        options.reputation_context.model_dump(mode="json", exclude_none=True)
        if options.reputation_context is not None
        else None
    )
    apply_reputation_supplement(
        meihua,
        interpretation,
        context=normalized_reputation,
        context_fact_path="analysis_context.reputation_context",
    )

    apply_qi_day_timing_references(meihua, interpretation)

    apply_qi_branch_timing_references(meihua, interpretation)

    apply_clock_input_notice(interpretation, clock_resolution)
    return {
        "analysis_type": "梅花时卦分析",
        "analysis_context": {
            **(
                {"reputation_context": normalized_reputation}
                if reputation_context is not None
                else {}
            ),
            **(
                {"response_context": normalized_response}
                if response_context is not None
                else {}
            ),
            **(
                {"observation_context": normalized_observation}
                if observation_context is not None
                else {}
            ),
            **(
                {"observer_activity": observer_activity}
                if observer_activity is not None
                else {}
            ),
            **(
                {"matter_scenario": matter_scenario}
                if matter_scenario is not None
                else {}
            ),
            "analysis_datetime": calendar_context["solar_datetime"],
            "timezone": timezone_name,
            "civil_utc_offset": clock_resolution["resolved_utc_offset"],
            "civil_instant_utc": clock_resolution["instant_utc"],
            "question": question or "",
            "interpretation_topic": interpretation_topic,
            "weather_context": weather_context,
            "lunar_display": lunar_calendar.get("display"),
            "current_jieqi": calendar_context["current_solar_term"]["name"],
            "next_jieqi": calendar_context["next_solar_term"]["name"],
        },
        "four_pillars": create_pillar_dict(pillars),
        "calendar_context": calendar_context,
        "meihua": meihua,
        "interpretation": interpretation,
        "summary": interpretation["comprehensive_judgement"],
    }


@calculation_guard("卦象查询")
def calculate_gua_lookup(
    *,
    queries: list[str],
    lookup_mode: Literal["auto", "hexagram", "trigram"] = "auto",
) -> dict[str, Any]:
    """
    卦象查询工具 - 支持六十四卦与八卦的批量离线义理查询。
    """
    cleaned = [item.strip() for item in (queries or []) if item and item.strip()]
    if not cleaned:
        raise ValueError("queries 至少需要提供一个非空卦名或卦码。")

    results = {q: lookup_gua(q, lookup_mode=lookup_mode) for q in cleaned}
    ordered_names = [f"{results[q]['name']}（{results[q]['code']}）" for q in cleaned]
    summary = (
        ordered_names[0]
        if len(cleaned) == 1
        else f"共查询{len(cleaned)}项卦象：{'、'.join(ordered_names)}。"
    )
    return {
        "analysis_type": "卦象查询",
        "lookup_mode": lookup_mode,
        "queries": cleaned,
        "results": results,
        "summary": summary,
    }


@calculation_guard("统摄法分析")
def calculate_tongshefa_analysis(
    *,
    taiyin: str | None = None,
    taiyang: str | None = None,
    shaoyang: str | None = None,
    shaoyin: str | None = None,
) -> dict[str, Any]:
    """Calculate the four-trigram TongSheFa comparison."""
    return dict(
        build_tongshefa_result(
            taiyin=taiyin,
            taiyang=taiyang,
            shaoyang=shaoyang,
            shaoyin=shaoyin,
        )
    )


@calculation_guard("邵子参评数分析")
def calculate_canping_analysis(
    *,
    date: str,
    time: str,
    timezone: str | None = None,
    birth_utc_offset: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    gender: str | None = None,
    method: str = "gu",
    dayun_method: str = "bazi_appendix_v1",
    analysis_datetime: str | None = None,
    use_true_solar_time: bool = True,
) -> dict[str, Any]:
    """邵子参评数 / 金锁银匙分析工具。"""
    return build_canping_result(
        date=date,
        time=time,
        timezone=timezone,
        birth_utc_offset=birth_utc_offset,
        latitude=latitude,
        longitude=longitude,
        gender=gender,
        method=method,
        dayun_method=dayun_method,
        analysis_datetime=analysis_datetime,
        use_true_solar_time=use_true_solar_time,
    )


@calculation_guard("河洛理数分析")
def calculate_heluo_analysis(
    *,
    date: str,
    time: str,
    timezone: str | None = None,
    birth_utc_offset: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    gender: str | None = None,
    use_true_solar_time: bool = True,
    analysis_year: int | None = None,
    month_index: int | None = None,
    day_index: int | None = None,
    month_assignment_method: MonthAssignmentMethod = DEFAULT_MONTH_ASSIGNMENT,
) -> dict[str, Any]:
    """河洛理数分析工具。"""
    return build_heluo_result(
        date=date,
        time=time,
        timezone=timezone,
        birth_utc_offset=birth_utc_offset,
        latitude=latitude,
        longitude=longitude,
        gender=gender,
        use_true_solar_time=use_true_solar_time,
        analysis_year=analysis_year,
        month_index=month_index,
        day_index=day_index,
        month_assignment_method=month_assignment_method,
    )


@calculation_guard("六爻分析")
def calculate_sixyao_analysis(
    *,
    date: str,
    time: str,
    timezone: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    question: str | None = None,
    gua_code: str | None = None,
    changed_code: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    method: Literal["auto", "coin", "time"] = "auto",
    coins: list[int] | None = None,
    seed: int | None = None,
    focus_line: int | None = None,
    focus_kinship: str | None = None,
    focus_kind: str | None = None,
    timing_days: int = 0,
    event_horizon: str | None = None,
) -> dict[str, Any]:
    """六爻 / 易卦分析工具。"""
    return build_sixyao_result(
        date=date,
        time=time,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude,
        question=question,
        gua_code=gua_code,
        changed_code=changed_code,
        lines=lines,
        method=method,
        coins=coins,
        seed=seed,
        focus_line=focus_line,
        focus_kinship=focus_kinship,
        focus_kind=focus_kind,
        timing_days=timing_days,
        event_horizon=event_horizon,
    )


@calculation_guard("宿占分析")
def calculate_suzhan_analysis(
    *,
    date: str,
    time: str | None = None,
    timezone: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    szchart: int = 0,
    szshape: int = 0,
    house_system: int | str = "D",
    zodiac_type: str = "Tropic",
    house_start_mode: int = 1,
    doubing_su28: bool = True,
    leap_month_policy: str = "unresolved",
    natal_mansion: str | None = None,
    activity: str | None = None,
    activity_details: list[str] | None = None,
    calendar_profile: str = "t1299_fullmoon27",
    calendar_day_part: str | None = None,
    textual_pada: int | None = None,
    calendar_basis: str = "chinese_hko_utc08",
    chart_requested: bool = False,
    distance_rule: DistanceRule = "symmetric",
    birth_year: int | None = None,
    target_year: int | None = None,
    urgent: bool = False,
) -> dict[str, Any]:
    """宿占 / 宿盘分析工具。"""
    return build_suzhan_result(
        date=date,
        time=time,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude,
        szchart=szchart,
        szshape=szshape,
        house_start_mode=house_start_mode,
        doubing_su28=doubing_su28,
        house_system=house_system,
        zodiac_type=zodiac_type,
        leap_month_policy=leap_month_policy,
        natal_mansion=natal_mansion,
        activity=activity,
        activity_details=activity_details,
        calendar_profile=calendar_profile,
        calendar_day_part=calendar_day_part,
        textual_pada=textual_pada,
        calendar_basis=calendar_basis,
        chart_requested=chart_requested,
        distance_rule=distance_rule,
        birth_year=birth_year,
        target_year=target_year,
        urgent=urgent,
    )


@calculation_guard("宿曜双人相性")
def calculate_sukuyo_compatibility(
    *,
    person1_name: str = "甲方",
    person1_date: str,
    person1_time: str | None = None,
    person1_zone: str | None = None,
    person2_name: str = "乙方",
    person2_date: str,
    person2_time: str | None = None,
    person2_zone: str | None = None,
    leap_month_policy: str = "unresolved",
    calendar_profile: str = "t1299_fullmoon27",
    person1_calendar_day_part: str | None = None,
    person2_calendar_day_part: str | None = None,
    person1_textual_pada: int | None = None,
    person2_textual_pada: int | None = None,
    calendar_basis: str = "chinese_hko_utc08",
    distance_rule: DistanceRule = "symmetric",
) -> dict[str, Any]:
    """按显式宿主历法月日定本命宿，依T1299三九法返回双向关系。"""
    contexts = [
        calendar_mansion(
            person1_date,
            person1_time,
            person1_zone,
            leap_month_policy=leap_month_policy,
            calendar_profile=calendar_profile,
            calendar_day_part=person1_calendar_day_part,
            calendar_basis=calendar_basis,
        ),
        calendar_mansion(
            person2_date,
            person2_time,
            person2_zone,
            leap_month_policy=leap_month_policy,
            calendar_profile=calendar_profile,
            calendar_day_part=person2_calendar_day_part,
            calendar_basis=calendar_basis,
        ),
    ]

    people = [
        {
            "name": name,
            "natal_su27": context["natal_su27"],
            "calendar": context,
            "palace_reference": palace_reference(context, pada),
        }
        for name, context, pada in zip(
            (person1_name, person2_name),
            contexts,
            (person1_textual_pada, person2_textual_pada),
        )
    ]
    first, second = (p["natal_su27"] for p in people)

    calendar_label = basis_parameters(calendar_basis)[3]
    resolved = first is not None and second is not None
    forward = (
        relation_between_su27(first, second, distance_rule=distance_rule)
        if resolved
        else None
    )
    reverse = (
        relation_between_su27(second, first, distance_rule=distance_rule)
        if resolved
        else None
    )
    candidate_analysis = candidate_relation_analysis(
        contexts[0], contexts[1], distance_rule=distance_rule
    )
    if forward is not None and reverse is not None:
        dist = f"（{forward['distance']}）" if forward.get("distance") else ""
        summary = (
            f"{person1_name}（{first}）与{person2_name}（{second}）"
            f"为{forward['pair']}{dist}：正{forward['relation']}、反{reverse['relation']}。"
        )
    elif any(c.get("calendar_candidates") for c in contexts):
        summary = (
            f"所选{calendar_label}历日存在候选，双向关系见candidate_relation_analysis。"
        )
    else:
        summary = "闰月/半日或规则次序未定，候选关系见candidate_relation_analysis。"

    result: dict[str, Any] = {
        "analysis_type": "宿曜双人相性 / T1299三九法",
        "status": "computed" if resolved else "partial",
        "su27_basis": contexts[0]["mansion_method_id"],
        "person1": people[0],
        "person2": people[1],
        "pair": forward["pair"] if forward else None,
        "person1_to_person2": forward,
        "person2_to_person1": reverse,
        "candidate_relation_analysis": candidate_analysis,
        "summary": summary,
    }
    if calendar_basis != "chinese_hko_utc08":
        result["calendar_basis"] = calendar_basis
    return result


@calculation_guard("占星骰子分析")
def calculate_otherbu_analysis(
    *,
    date: str | None = None,
    time: str | None = None,
    timezone: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    tradition: bool = False,
    sign: str | None = None,
    house: int | None = None,
    planet: str | None = None,
    question: str | None = None,
    house_system: int | str = "D",
    zodiac_type: str = "Tropic",
    fortune_method: str = "sect_reversing",
) -> dict[str, Any]:
    """西洋游戏 / 占星骰子分析工具。"""
    return build_otherbu_result(
        date=date,
        time=time,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude,
        tradition=tradition,
        sign=sign,
        house=house,
        planet=planet,
        question=question,
        house_system=house_system,
        zodiac_type=zodiac_type,
        fortune_method=fortune_method,
    )


@calculation_guard("三式合一分析")
def calculate_sanshiunited_analysis(
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
    use_true_solar_time: bool = True,
    corner_lodging: Literal[
        "unassessed", "first_branch", "second_branch", "both"
    ] = "both",
) -> dict[str, Any]:
    """三式合一本地聚合工具。"""
    return build_sanshiunited_result(
        date=date,
        time=time,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude,
        qimen_options=qimen_options,
        taiyi_options=taiyi_options,
        liuren_yue=liuren_yue,
        liuren_is_diurnal=liuren_is_diurnal,
        liuren_guiren_profile=liuren_guiren_profile,
        use_true_solar_time=use_true_solar_time,
        corner_lodging=corner_lodging,
    )
