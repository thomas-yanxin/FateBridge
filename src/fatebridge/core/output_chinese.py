"""Nested facts for Chinese professional and local divination techniques.

Stable rows, palaces, lessons and calendar facts are validated. Dynamic names
(stars, transformations and verse/hexagram keys) remain dictionary keys. Raw
interpretation, plugin details and user question inputs remain extensible JSON.
"""

from typing import Any, Dict, List, Optional

from pydantic import JsonValue

from fatebridge.core.output_base import PartialOutput

Object = Dict[str, JsonValue]


class Pillar(PartialOutput):
    stem: Optional[str] = None
    branch: Optional[str] = None


class FourPillars(PartialOutput):
    year: Optional[Pillar] = None
    month: Optional[Pillar] = None
    day: Optional[Pillar] = None
    hour: Optional[Pillar] = None


class PersonInfo(PartialOutput):
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_datetime: Optional[str] = None
    birth_place: Optional[str] = None
    birth_timezone: Optional[str] = None
    birth_longitude: Optional[float] = None
    birth_latitude: Optional[float] = None
    normalized_birth_datetime: Optional[str] = None
    time_algorithm: Optional[str] = None


class AnalysisContext(PartialOutput):
    context_role: Optional[str] = None
    analysis_year: Optional[int] = None
    analysis_month: Optional[int] = None
    analysis_day: Optional[int] = None
    analysis_hour: Optional[int] = None
    analysis_minute: Optional[int] = None
    input_datetime: Optional[str] = None
    corrected_datetime: Optional[str] = None
    timezone: Optional[str] = None
    longitude: Optional[float] = None
    applied_true_solar: Optional[bool] = None
    time_algorithm: Optional[str] = None
    total_correction_minutes: Optional[float] = None
    current_jieqi: Optional[str] = None
    next_jieqi: Optional[str] = None
    lunar_display: Optional[str] = None
    birth_datetime: Optional[str] = None
    analysis_datetime: Optional[str] = None
    age_years: Optional[float] = None
    house_system: Optional[str] = None
    zodiac_type: Optional[str] = None
    name: Optional[str] = None
    birth_place: Optional[str] = None


class SolarTerm(PartialOutput):
    date_key: Optional[str] = None
    datetime: Optional[str] = None
    day_ganzhi: Optional[str] = None
    name: Optional[str] = None


class Trigram(PartialOutput):
    name: Optional[str] = None
    cname: Optional[str] = None
    element: Optional[str] = None
    elem: Optional[str] = None
    lines: Optional[List[int]] = None
    nature: Optional[str] = None
    symbol: Optional[str] = None
    value: Optional[List[int]] = None
    theme: Optional[str] = None
    keywords: Optional[str] = None
    image: Optional[str] = None
    favorable: Optional[str] = None
    caution: Optional[str] = None
    guidance: Optional[str] = None


class Hexagram(PartialOutput):
    name: Optional[str] = None
    binary_code: Optional[str] = None
    code: Optional[str] = None
    lookup_type: Optional[str] = None
    matched_query: Optional[str] = None
    lines: Optional[List[int]] = None
    lower: Optional[Trigram] = None
    upper: Optional[Trigram] = None
    moving_line: Optional[int] = None
    symbol: Optional[str] = None
    theme: Optional[str] = None
    image: Optional[str] = None
    judgement: Optional[str] = None
    summary: Optional[str] = None
    guidance: Optional[str] = None
    favorable: Optional[str] = None
    caution: Optional[str] = None
    text: Optional[str] = None
    desc: Optional[str] = None


class MeihuaSeed(PartialOutput):
    hour_branch: Optional[str] = None
    year_branch: Optional[str] = None
    lunar_day: Optional[int] = None
    lunar_month: Optional[int] = None
    moving_line: Optional[int] = None
    upper_number: Optional[int] = None
    lower_number: Optional[int] = None


class Meihua(PartialOutput):
    method: Optional[str] = None
    seed: Optional[MeihuaSeed] = None
    base_hexagram: Optional[Hexagram] = None
    changed_hexagram: Optional[Hexagram] = None
    mutual_hexagram: Optional[Hexagram] = None
    cuo_hexagram: Optional[Hexagram] = None
    zong_hexagram: Optional[Hexagram] = None
    body_trigram: Optional[Trigram] = None
    use_trigram: Optional[Trigram] = None
    body_use_relation: Optional[str] = None
    body_use_summary: Optional[str] = None
    element_relation: Optional[str] = None
    moving_palace: Optional[str] = None
    summary: Optional[str] = None


class LunarCalendar(PartialOutput):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    is_leap_month: Optional[bool] = None
    year_cn: Optional[str] = None
    month_cn: Optional[str] = None
    day_cn: Optional[str] = None
    birth: Optional[str] = None
    display: Optional[str] = None
    day_ganzhi: Optional[str] = None
    month_ganzhi: Optional[str] = None
    time_ganzhi: Optional[str] = None
    year_jieqi_ganzhi: Optional[str] = None
    solar_datetime: Optional[str] = None
    timezone: Optional[str] = None
    jieqi: Optional[str] = None
    jiedelta: Optional[str] = None
    days_until_next_jieqi: Optional[float] = None
    previous_jieqi: Optional[SolarTerm] = None
    next_jieqi: Optional[SolarTerm] = None
    meihua: Optional[Meihua] = None


class MonthBoundary(PartialOutput):
    branch: Optional[str] = None
    month_index: Optional[int] = None
    days_since_start: Optional[float] = None
    days_until_next: Optional[float] = None
    start_term: Optional[SolarTerm] = None
    next_term: Optional[SolarTerm] = None


class SolarTermDelta(PartialOutput):
    days_since_current: Optional[float] = None
    days_until_next: Optional[float] = None
    description: Optional[str] = None


class LunarSupport(PartialOutput):
    supported: Optional[bool] = None
    supported_range: Optional[Dict[str, str]] = None


class CalendarContext(PartialOutput):
    solar_datetime: Optional[str] = None
    timezone: Optional[str] = None
    lunar_calendar: Optional[LunarCalendar] = None
    current_solar_term: Optional[SolarTerm] = None
    next_solar_term: Optional[SolarTerm] = None
    bazi_month_boundary: Optional[MonthBoundary] = None
    solar_term_delta: Optional[SolarTermDelta] = None
    lunar_calendar_support: Optional[LunarSupport] = None


class BranchName(PartialOutput):
    branch: Optional[str] = None
    name: Optional[str] = None


class LunarDate(PartialOutput):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    is_leap_month: Optional[bool] = None


class ZiweiPosition(BranchName):
    ganzhi: Optional[str] = None


class ZiweiStar(PartialOutput):
    name: Optional[str] = None
    label: Optional[str] = None
    brightness: Optional[str] = None
    mutagen: Optional[str] = None


class ZiweiPalace(PartialOutput):
    name: Optional[str] = None
    ganzhi: Optional[str] = None
    daxian: Optional[str] = None
    daxian_period: Optional[int] = None
    stars: Optional[List[str]] = None
    stars_detail: Optional[List[ZiweiStar]] = None


class ZiweiCalendarRules(PartialOutput):
    late_zi: Optional[str] = None
    leap_month: Optional[str] = None
    year_boundary: Optional[str] = None


class WuxingJu(PartialOutput):
    element: Optional[str] = None
    label: Optional[str] = None
    nayin: Optional[str] = None
    number: Optional[int] = None


class ZiweiBirth(PartialOutput):
    engine: Optional[str] = None
    calendar_rules: Optional[ZiweiCalendarRules] = None
    daxian_direction: Optional[str] = None
    hour_branch: Optional[str] = None
    lunar_date: Optional[LunarDate] = None
    ming_gong: Optional[ZiweiPosition] = None
    shen_gong: Optional[ZiweiPosition] = None
    palaces: Optional[List[ZiweiPalace]] = None
    sihua: Optional[Dict[str, str]] = None
    time_algorithm: Optional[str] = None
    wuxing_ju: Optional[WuxingJu] = None
    year_stem: Optional[str] = None


class ZiweiMutagenNatalLink(PartialOutput):
    transformation: Optional[str] = None
    star: Optional[str] = None
    status: Optional[str] = None
    natal_palace_name: Optional[str] = None
    natal_palace_ganzhi: Optional[str] = None
    natal_branch: Optional[str] = None
    natal_star_label: Optional[str] = None
    natal_star_brightness: Optional[str] = None
    natal_mutagen: Optional[str] = None


class ZiweiScope(PartialOutput):
    scope: Optional[str] = None
    branch: Optional[str] = None
    branch_index: Optional[int] = None
    stem: Optional[str] = None
    palace_ganzhi: Optional[str] = None
    palace_name: Optional[str] = None
    scope_palace_role: Optional[str] = None
    natal_palace_name: Optional[str] = None
    mutagen: Optional[Dict[str, str]] = None
    mutagen_natal_links: Optional[List[ZiweiMutagenNatalLink]] = None


class ZiweiInterpretationScope(PartialOutput):
    contract_version: Optional[str] = None
    scope_palace_meaning: Optional[str] = None
    transformation_meaning: Optional[str] = None
    full_scope_palaces_supported: Optional[bool] = None
    limitations: Optional[List[str]] = None


class ZiweiHoroscope(PartialOutput):
    engine: Optional[str] = None
    calendar_rules: Optional[ZiweiCalendarRules] = None
    nominal_age: Optional[int] = None
    interpretation_scope: Optional[ZiweiInterpretationScope] = None
    scopes: Optional[List[ZiweiScope]] = None


class ZiweiFocusedRules(PartialOutput):
    sihua: Optional[Dict[str, str]] = None
    year_stem: Optional[str] = None


class ZiweiRuleCatalogue(PartialOutput):
    ming_gong_method: Optional[str] = None
    shen_gong_method: Optional[str] = None
    palace_sequence: Optional[List[str]] = None
    sihua_by_year_stem: Optional[Dict[str, Dict[str, str]]] = None


class LiurenLesson(PartialOutput):
    anchor_branch: Optional[str] = None
    index: Optional[int] = None
    lower_branch: Optional[str] = None
    upper_branch: Optional[str] = None
    relation: Optional[str] = None
    relations: Optional[Dict[str, str]] = None
    style_basis: Optional[str] = None
    style_hint: Optional[str] = None
    text: Optional[str] = None
    upper_lower_relation: Optional[str] = None
    use_candidate: Optional[bool] = None


class LiurenTransmission(PartialOutput):
    branch: Optional[str] = None
    ganzhi: Optional[str] = None
    god: Optional[str] = None
    relation: Optional[str] = None


class LiurenTransmissions(PartialOutput):
    initial: Optional[LiurenTransmission] = None
    middle: Optional[LiurenTransmission] = None
    final: Optional[LiurenTransmission] = None
    method: Optional[str] = None


class LiurenBoardRow(PartialOutput):
    earth_branch: Optional[str] = None
    sky_branch: Optional[str] = None
    god: Optional[str] = None


class LiurenPattern(PartialOutput):
    basis: Optional[str] = None
    name: Optional[str] = None


class LiurenMeta(PartialOutput):
    current_term: Optional[str] = None
    guiren_earth_branch: Optional[str] = None
    is_diurnal: Optional[bool] = None
    lunar_display: Optional[str] = None
    questioner_gender: Optional[str] = None
    selected_lesson_index: Optional[int] = None
    selected_lesson_relation: Optional[str] = None


class Liuren(PartialOutput):
    engine: Optional[str] = None
    board_order: Optional[str] = None
    board_style: Optional[str] = None
    board_style_detail: Optional[str] = None
    guiren_system: Optional[str] = None
    kongwang: Optional[str] = None
    meta: Optional[LiurenMeta] = None
    month_general: Optional[BranchName] = None
    overview: Optional[List[str]] = None
    patterns: Optional[List[LiurenPattern]] = None
    four_lessons: Optional[List[LiurenLesson]] = None
    three_transmissions: Optional[LiurenTransmissions] = None
    twelve_board: Optional[List[LiurenBoardRow]] = None
    twelve_life_element: Optional[str] = None
    xun_head: Optional[str] = None


class Runyear(PartialOutput):
    age: Optional[int] = None
    engine: Optional[str] = None
    ganzhi: Optional[str] = None
    gender: Optional[str] = None


class QimenHexagram(PartialOutput):
    binary_code: Optional[str] = None
    name: Optional[str] = None


class QimenPalace(PartialOutput):
    name: Optional[str] = None
    content_palace: Optional[str] = None
    content_trigram: Optional[str] = None
    trigram: Optional[str] = None
    door: Optional[str] = None
    door_hexagram: Optional[QimenHexagram] = None
    earth_stem: Optional[str] = None
    heaven_stem: Optional[str] = None
    god: Optional[str] = None
    star: Optional[str] = None


class QimenLeader(PartialOutput):
    code: Optional[str] = None
    content_palace: Optional[str] = None
    content_trigram: Optional[str] = None
    palace: Optional[str] = None
    trigram: Optional[str] = None
    star: Optional[str] = None
    door: Optional[str] = None


class QimenOptions(PartialOutput):
    layout: Optional[str] = None
    palaceShift: Optional[int] = None
    reverse: Optional[bool] = None


class Qimen(PartialOutput):
    engine: Optional[str] = None
    dun_type: Optional[str] = None
    fu_tou: Optional[str] = None
    fushi_hexagram: Optional[QimenHexagram] = None
    ju_number: Optional[int] = None
    ju_text: Optional[str] = None
    kongwang: Optional[str] = None
    layout: Optional[str] = None
    options_applied: Optional[QimenOptions] = None
    palaces: Optional[List[QimenPalace]] = None
    reference: Optional[str] = None
    xun_head: Optional[str] = None
    yuan: Optional[str] = None
    yuan_order: Optional[str] = None
    zhifu: Optional[QimenLeader] = None
    zhishi: Optional[QimenLeader] = None


class TaiyiCore(PartialOutput):
    chenji: Optional[str] = None
    dingmu: Optional[str] = None
    diyi: Optional[str] = None
    guest_count: Optional[int] = None
    guest_count_des: Optional[List[str]] = None
    guest_general: Optional[int] = None
    guest_vice_general: Optional[int] = None
    heshen: Optional[str] = None
    jishen: Optional[str] = None
    junji: Optional[str] = None
    kook_number: Optional[int] = None
    kook_year: Optional[str] = None
    main_calculation: Optional[str] = None
    main_count: Optional[int] = None
    main_count_des: Optional[List[str]] = None
    main_general: Optional[int] = None
    main_vice_general: Optional[int] = None
    minji: Optional[str] = None
    set_count: Optional[int] = None
    shiji: Optional[str] = None
    sishen: Optional[str] = None
    suijun: Optional[str] = None
    taiyi_position: Optional[str] = None
    tianyi: Optional[str] = None
    wenchang_position: Optional[str] = None
    wufu: Optional[int] = None
    zhifu: Optional[str] = None


class TaiyiPalace(PartialOutput):
    markers: Optional[List[str]] = None
    palace: Optional[str] = None


class Taiyi(PartialOutput):
    engine: Optional[str] = None
    accumulation_label: Optional[str] = None
    core_board: Optional[TaiyiCore] = None
    life_method: Optional[str] = None
    palace_marks: Optional[List[TaiyiPalace]] = None
    rotation: Optional[str] = None
    style_label: Optional[str] = None
    taiyi_palace: Optional[str] = None
    wenchang_palace: Optional[str] = None
    big_pattern: Optional[str] = None
    small_pattern: Optional[str] = None


class JinkouOverview(PartialOutput):
    board_style: Optional[str] = None
    board_style_detail: Optional[str] = None
    di_fen: Optional[str] = None
    gender: Optional[str] = None
    guishen: Optional[BranchName] = None
    kongwang: Optional[str] = None
    month_general: Optional[BranchName] = None
    si_da_kong: Optional[str] = None
    transmission_method: Optional[str] = None
    use_position: Optional[str] = None
    use_position_basis: Optional[str] = None
    yuejiang: Optional[BranchName] = None


class JinkouRow(PartialOutput):
    content: Optional[str] = None
    element: Optional[str] = None
    label: Optional[str] = None
    power: Optional[str] = None
    shenjiang: Optional[str] = None


class LabelValue(PartialOutput):
    label: Optional[str] = None
    value: Optional[str] = None


class Jinkou(PartialOutput):
    engine: Optional[str] = None
    overview: Optional[JinkouOverview] = None
    rows: Optional[List[JinkouRow]] = None
    shensha: Optional[List[LabelValue]] = None


class SixyaoLine(PartialOutput):
    branch: Optional[str] = None
    change: Optional[bool] = None
    element: Optional[str] = None
    god: Optional[str] = None
    liuqin: Optional[str] = None
    liushen: Optional[str] = None
    name: Optional[str] = None
    position: Optional[int] = None
    shi_ying: Optional[str] = None
    value: Optional[int] = None


class SixyaoCast(PartialOutput):
    method: Optional[str] = None
    source: Optional[str] = None
    seed: Optional[int] = None


class SixyaoHexagramInfo(PartialOutput):
    changed_palace: Optional[str] = None
    changed_palace_element: Optional[str] = None
    changed_position: Optional[str] = None
    current_palace: Optional[str] = None
    current_palace_element: Optional[str] = None
    current_position: Optional[str] = None
    shi_line: Optional[int] = None
    ying_line: Optional[int] = None


class SixyaoDescription(PartialOutput):
    code: Optional[str] = None
    name: Optional[str] = None
    theme: Optional[str] = None
    summary: Optional[str] = None
    guidance: Optional[str] = None
    favorable: Optional[str] = None
    caution: Optional[str] = None
    raw: Optional[Hexagram] = None


class SixyaoFlags(PartialOutput):
    liuchong_base: Optional[bool] = None
    liuchong_changed: Optional[bool] = None
    liuhe_base: Optional[bool] = None
    liuhe_changed: Optional[bool] = None


class Tongshefa(PartialOutput):
    baseLeft: Optional[Hexagram] = None
    baseRight: Optional[Hexagram] = None
    mutualLeft: Optional[Hexagram] = None
    mutualRight: Optional[Hexagram] = None
    relation: Optional[str] = None
    main_relation: Optional[str] = None
    left_elem: Optional[str] = None
    right_elem: Optional[str] = None


class CanpingVerses(PartialOutput):
    numNi: Optional[int] = None
    numShun: Optional[int] = None
    textNi: Optional[str] = None
    textShun: Optional[str] = None


class CanpingRow(PartialOutput):
    age: Optional[int] = None
    ageEnd: Optional[int] = None
    ageStart: Optional[int] = None
    branch: Optional[str] = None
    index: Optional[int] = None
    ni: Optional[int] = None
    numNi: Optional[int] = None
    numShun: Optional[int] = None
    shun: Optional[int] = None
    ziRound: Optional[int] = None
    verses: Optional[CanpingVerses] = None
    dayunBranch: Optional[str] = None
    dayunRange: Optional[str] = None
    ganzhi: Optional[str] = None
    taisuiBranch: Optional[str] = None
    year: Optional[int] = None


class CanpingSeries(PartialOutput):
    dayun: Optional[List[CanpingRow]] = None
    element: Optional[str] = None
    partName: Optional[str] = None
    qiyunAge: Optional[int] = None
    rows: Optional[List[CanpingRow]] = None


class HeluoHexagram(PartialOutput):
    lines: Optional[List[int]] = None
    name: Optional[str] = None
    yuan: Optional[int] = None
    low: Optional[str] = None
    up: Optional[str] = None


class HeluoChart(PartialOutput):
    di: Optional[int] = None
    diGua: Optional[str] = None
    diNum: Optional[int] = None
    gender: Optional[str] = None
    hourZhi: Optional[str] = None
    tian: Optional[int] = None
    tianGua: Optional[str] = None
    tianNum: Optional[int] = None
    tianTop: Optional[bool] = None
    yangGan: Optional[bool] = None
    yangLing: Optional[bool] = None
    yangMing: Optional[bool] = None
    hou: Optional[HeluoHexagram] = None
    xian: Optional[HeluoHexagram] = None


class HeluoPeriod(PartialOutput):
    ageEnd: Optional[int] = None
    ageStart: Optional[int] = None
    gua: Optional[str] = None
    lines: Optional[List[int]] = None
    pos: Optional[int] = None
    yang: Optional[bool] = None
    yearStart: Optional[int] = None
    years: Optional[int] = None


class HeluoDayun(PartialOutput):
    all: Optional[List[HeluoPeriod]] = None
    hou: Optional[List[HeluoPeriod]] = None
    xian: Optional[List[HeluoPeriod]] = None
    endAge: Optional[int] = None
    xianEndAge: Optional[int] = None


class LocalAngles(PartialOutput):
    ascendant: Optional[float] = None
    midheaven: Optional[float] = None


class LocalHouse(PartialOutput):
    id: Optional[str] = None
    lon: Optional[float] = None
    sign: Optional[str] = None
    sign_zh: Optional[str] = None


class LocalObject(PartialOutput):
    house: Optional[str] = None
    id: Optional[str] = None
    lon: Optional[float] = None
    sign: Optional[str] = None
    signlon: Optional[float] = None


class LocalChart(PartialOutput):
    angles: Optional[LocalAngles] = None
    houses: Optional[List[LocalHouse]] = None
    objects: Optional[List[LocalObject]] = None
    ok: Optional[bool] = None


class LocalChartBundle(PartialOutput):
    chart: Optional[LocalChart] = None
    params: Optional[Object] = None


class SanshiSubresult(PartialOutput):
    analysis_context: Optional[AnalysisContext] = None
    analysis_type: Optional[str] = None
    calendar_context: Optional[CalendarContext] = None
    four_pillars: Optional[FourPillars] = None
    liureng: Optional[Liuren] = None


class QimenSubresult(SanshiSubresult):
    pan: Optional[Qimen] = None


class TaiyiSubresult(SanshiSubresult):
    pan: Optional[Taiyi] = None


class SanshiSubresults(PartialOutput):
    liureng_gods: Optional[SanshiSubresult] = None
    qimen: Optional[QimenSubresult] = None
    taiyi: Optional[TaiyiSubresult] = None


CHINESE_FIELDS: Dict[str, Any] = {
    "four_pillars": FourPillars,
    "person_info": PersonInfo,
    "analysis_context": AnalysisContext,
    "birth_context": AnalysisContext,
    "calendar_context": CalendarContext,
    "jieqi_year": List[SolarTerm],
    "selected_jieqi": List[SolarTerm],
    "target_year_jieqi": List[SolarTerm],
    "lunar_calendar": LunarCalendar,
    "meihua": Meihua,
    "tongshefa": Tongshefa,
    "ziwei_birth": ZiweiBirth,
    "ziwei_horoscope": ZiweiHoroscope,
    "focused_rules": ZiweiFocusedRules,
    "rule_catalogue": ZiweiRuleCatalogue,
    "liureng": Liuren,
    "runyear": Runyear,
    "qimen": Qimen,
    "taiyi": Taiyi,
    "jinkou": Jinkou,
    "current_hexagram": Hexagram,
    "changed_hexagram": Hexagram,
    "hexagram_info": SixyaoHexagramInfo,
    "cast": SixyaoCast,
    "descriptions": Dict[str, SixyaoDescription],
    "pattern_flags": SixyaoFlags,
    "benming": CanpingRow,
    "liunian_series": CanpingSeries,
    "subresults": SanshiSubresults,
}

# Root names such as chart, dayun, lines and result have different meanings in
# different families. Resolve them by tool instead of weakening them with unions.
CHINESE_TOOL_FIELDS: Dict[str, Dict[str, Any]] = {
    "sixyao": {"lines": List[SixyaoLine], "moving_lines": List[int]},
    "gua_lookup": {"result": Hexagram},
    "gua_meiyi": {"queries": List[str], "results": Dict[str, Hexagram]},
    "canping": {"dayun": List[CanpingRow]},
    "heluo": {"chart": HeluoChart, "dayun": HeluoDayun},
    "suzhan": {"chart": LocalChart},
    "otherbu": {"chart": LocalChartBundle, "diceChart": LocalChartBundle},
}
