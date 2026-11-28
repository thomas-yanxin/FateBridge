"""Output contracts and cross-chart anchor validators for Ren and Sanshi."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, JsonValue, ValidationInfo, model_validator

from fatebridge.core.contracts.base import PartialOutput, ProjectedOutput
from fatebridge.core.contracts.common import (
    AnalysisContext,
    CalendarContext,
    FourPillars,
    Object,
)
from fatebridge.core.contracts.jinkou import (
    Jinkou,
    align_branch_breaks,
    require_complete_branch_stars,
    require_complete_natal_course,
    require_complete_pattern_anchors,
    require_complete_relations,
    require_complete_strength_evidence,
)
from fatebridge.core.contracts.liuren import (
    Liuren,
    Runyear,
    align_branch_relations,
    align_cross_harmony,
    align_day_placements,
    align_god_yin,
    align_progression,
    align_seasonal,
    require_complete_branch_relations,
    require_complete_course_conditions,
    require_complete_cross_harmony,
    require_complete_day_placements,
    require_complete_emptiness,
    require_complete_god_yin,
    require_complete_nominal_seasonal,
    require_complete_ordered_patterns,
    require_complete_progression,
    require_complete_published_dates,
    require_complete_seasonal,
    validate_selection,
)
from fatebridge.core.contracts.qimen import Qimen
from fatebridge.core.contracts.taiyi import Taiyi
from fatebridge.core.metaphysics.common import (
    GUI_REN_SEQUENCE,
    YUE_JIANG_NAMES,
    liuqin_against_day,
    status_against_anchor,
)
from fatebridge.core.metaphysics.jinkou.board import (
    _build_guishen_mapping,
    _jinkou_pick_use_position,
)
from fatebridge.core.metaphysics.jinkou.patterns import (
    GUISHEN_IDENTITIES,
    wuzidun_stem,
)
from fatebridge.core.metaphysics.liureng.board import _liureng_month_general_on_hour
from fatebridge.core.metaphysics.liureng.stars import (
    life_stage_cycle,
    nominal_seasonal_evidence,
)
from fatebridge.core.metaphysics.ren_calendar import xun_dun_stems
from fatebridge.core.metaphysics.ren_diurnal import resolve_diurnal
from fatebridge.core.metaphysics.ren_gods import noble_start
from fatebridge.core.receipt_models import RunMetadata
from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    SIX_CLASH_BRANCHES,
    branch_element_text,
    kongwang_for_ganzhi,
    rotate_sequence,
    sexagenary_index_for,
    stem_element_text,
    xun_head_for_ganzhi,
)

__all__ = [
    "CorrespondenceLiuren",
    "CorrespondenceLiurenCandidate",
    "CorrespondenceQimen",
    "CorrespondenceRuleset",
    "JinkouOutput",
    "LiurenChartOutput",
    "LiurenYearlyTimingOutput",
    "NobleSourceAssessment",
    "NobleSourceComparison",
    "PalaceCorrespondence",
    "PalaceCorrespondences",
    "QimenSubresult",
    "REN_ANCHOR_TOOLS",
    "RenAnchoredOutput",
    "SanshiCombinedChartOutput",
    "SanshiFact",
    "SanshiSubresult",
    "SanshiSubresults",
    "SanshiSynthesis",
    "TaiyiSubresult",
    "require_complete_ren_anchors",
]

POSITIONS = ("人元", "贵神", "将神", "地分")
REN_ANCHOR_TOOLS = frozenset(
    {"jinkou", "liuren_chart", "liuren_yearly_timing", "sanshi_combined_chart"}
)


class CorrespondenceQimen(PartialOutput):
    source_path: str | None = None
    index: int | None = None
    trigram: str | None = None
    star: str | None = None
    door: str | None = None
    god: str | None = None
    hosted_stars: list[str] | None = None


class CorrespondenceLiurenCandidate(PartialOutput):
    source_path: str | None = None
    earth_branch: str | None = None
    sky_branch: str | None = None
    god: str | None = None


class CorrespondenceLiuren(CorrespondenceLiurenCandidate):
    status: str | None = None
    reason: str | None = None
    sector_candidates: list[CorrespondenceLiurenCandidate] | None = None


class PalaceCorrespondence(PartialOutput):
    marker: str | None = None
    taiyi_source_path: str | None = None
    taiyi_number: int | None = None
    taiyi_palace: str | None = None
    trigram: str | None = None
    direction: str | None = None
    qimen: CorrespondenceQimen | None = None
    liuren: CorrespondenceLiuren | None = None


class CorrespondenceRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    conformance: str | None = None


class PalaceCorrespondences(PartialOutput):
    ruleset: CorrespondenceRuleset | None = None
    corner_lodging: str | None = None
    entries: list[PalaceCorrespondence] | None = None


class SanshiFact(PartialOutput):
    technique: str | None = None
    field: str | None = None
    value: JsonValue | None = None


class NobleSourceComparison(PartialOutput):
    source_id: str | None = None
    source_branch: str | None = None
    matches: bool | None = None


class NobleSourceAssessment(PartialOutput):
    status: str | None = None
    day_stem: str | None = None
    is_diurnal: bool | None = None
    actual_profile: str | None = None
    actual_start_branch: str | None = None
    comparisons: list[NobleSourceComparison] | None = None


class SanshiSynthesis(PartialOutput):
    method: str | None = None
    status: str | None = None
    time_scopes: dict[str, str] | None = None
    common_input: dict[str, str] | None = None
    facts: list[SanshiFact] | None = None
    palace_correspondences: PalaceCorrespondences | None = None
    noble_source_assessment: NobleSourceAssessment | None = None


class SanshiSubresult(PartialOutput):
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    four_pillars: FourPillars | None = None
    liuren: Liuren | None = None


class QimenSubresult(SanshiSubresult):
    pan: Qimen | None = None


class TaiyiSubresult(SanshiSubresult):
    pan: Taiyi | None = None


class SanshiSubresults(PartialOutput):
    liuren: SanshiSubresult | None = None
    qimen: QimenSubresult | None = None
    taiyi: TaiyiSubresult | None = None


def _get(obj: object, *parts: str) -> object:
    cur: object = obj
    for part in parts:
        cur = cur.get(part) if isinstance(cur, Mapping) else getattr(cur, part, None)
        if cur is None:
            break
    return cur


def _has(obj: object, name: str) -> bool:
    if isinstance(obj, BaseModel):
        return name in obj.model_fields_set
    return isinstance(obj, Mapping) and name in obj


def _same(obj: object, field: str, expected: object) -> None:
    actual = _get(obj, *field.split("."))
    if actual is not None and actual != expected:
        raise ValueError(f"六壬金口诀同次计算依据不一致：{field}")


def _branch(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in EARTHLY_BRANCHES:
        raise ValueError("六壬金口诀支位须为十二地支")
    return value


def _stem(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in HEAVENLY_STEMS:
        raise ValueError("六壬金口诀日干须为十天干")
    return value


def _day(pillars: object) -> str | None:
    a = _stem(_get(pillars, "day", "stem"))
    b = _branch(_get(pillars, "day", "branch"))
    if a is None or b is None:
        return None
    value = a + b
    try:
        sexagenary_index_for(value)
    except KeyError as exc:
        raise ValueError("六壬金口诀占日须为有效六十甲子") from exc
    return value


def _diurnal(holder: object, hour: str | None) -> bool | None:
    evidence = _get(holder, "diurnal_evidence")
    if hour is not None:
        _same(evidence, "hour_branch", hour)
        if (
            _has(evidence, "explicit_choice")
            and _get(evidence, "diurnal_mode") != "sunrise_sunset"
            and _get(evidence, "selection_source") != "sunrise_sunset_ephemeris"
        ):
            raw_choice = _get(evidence, "explicit_choice")
            if raw_choice is not None and type(raw_choice) is not bool:
                raise ValueError("is_diurnal 必须是布尔选择或省略")
            expected = resolve_diurnal(hour, raw_choice)
            _same(evidence, "is_diurnal", expected["is_diurnal"])
            _same(evidence, "selection_source", expected["selection_source"])
            _same(holder, "is_diurnal", expected["is_diurnal"])
    chosen = _get(holder, "is_diurnal")
    if chosen is not None:
        _same(evidence, "is_diurnal", chosen)
    else:
        chosen = _get(evidence, "is_diurnal")
    if chosen is None:
        return None
    if not isinstance(chosen, bool):
        raise ValueError("六壬金口诀昼夜选择须为布尔值")
    return chosen


def _jinkou(board: object, pillars: object, liuren: object) -> None:
    if board is None:
        return

    day = _day(pillars)
    day_stem = _stem(_get(pillars, "day", "stem"))
    day_branch = _branch(_get(pillars, "day", "branch"))
    month = _branch(_get(pillars, "month", "branch"))
    year = _branch(_get(pillars, "year", "branch"))
    hour = _branch(_get(pillars, "hour", "branch"))
    overview = _get(board, "overview")
    chosen = _diurnal(overview, hour)
    for field, expected in (
        ("year_branch", year),
        ("month_building_branch", month),
        ("day_ganzhi", day),
    ):
        if expected is not None:
            _same(board, "branch_stars." + field, expected)
    if day_stem is not None:
        _same(board, "stem_relations.day_stem", day_stem)
        _same(board, "definition_evidence.day_stem", day_stem)
    if hour is not None:
        _same(board, "definition_evidence.hour_branch", hour)
    if chosen is not None:
        _same(board, "definition_evidence.selected_is_diurnal", chosen)
    if day is not None:
        _same(board, "calendar_policy.effective_day_ganzhi", day)
        _same(overview, "xun_head", xun_head_for_ganzhi(day))
        _same(overview, "kongwang", kongwang_for_ganzhi(day))
    if day_branch is not None:
        for name in (
            "qi_evidence.day_branch",
            "combinations.day_branch",
            "relations.calendar.day_branch",
        ):
            _same(board, name, day_branch)
    if month is not None:
        _same(board, "qi_evidence.month_building_branch", month)
        _same(board, "combinations.month_branch", month)
    if year is not None:
        _same(board, "relations.calendar.year_branch", year)
    general = _branch(_get(overview, "month_general", "branch"))
    attached_general = _branch(_get(liuren, "month_general", "branch"))
    if attached_general is not None:
        _same(overview, "month_general.branch", attached_general)
        general = attached_general
    rows = _get(board, "rows")
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("金口诀四位数组须保留四个位置")
    by_role = dict(zip(POSITIONS, rows))
    contents: dict[str, str] = {}
    for label, row in by_role.items():
        _same(row, "label", label)
        value = _get(row, "content")
        if value is None:
            continue
        sequence = HEAVENLY_STEMS if label == "人元" else EARTHLY_BRANCHES
        if not isinstance(value, str) or value not in sequence:
            raise ValueError("金口诀人元须为干，神将地分须为支")
        contents[label] = value
        phase = (
            stem_element_text(value) if label == "人元" else branch_element_text(value)
        )
        _same(row, "element", phase)
        _same(row, "polarity", "阳" if sequence.index(value) % 2 == 0 else "阴")
        if month is not None:
            seasonal = status_against_anchor(branch_element_text(month), phase)
            _same(row, "seasonal_power", seasonal)
            _same(
                row,
                "month_break",
                label != "人元" and value == SIX_CLASH_BRANCHES[month],
            )
        if day is not None:
            empty_phase = {"甲子": "水", "甲午": "水", "甲寅": "金", "甲申": "金"}.get(
                xun_head_for_ganzhi(day)
            )
            _same(
                row,
                "xun_kong",
                label != "人元" and value in kongwang_for_ganzhi(day)[:2],
            )
            _same(row, "si_da_kong", phase == empty_phase)
        if day_stem is not None and label in ("贵神", "将神"):
            _same(row, "dun_stem", wuzidun_stem(day_stem, value))
    ground = _branch(_get(overview, "di_fen"))
    if contents.get("地分") is not None:
        _same(overview, "di_fen", contents["地分"])
        ground = contents["地分"]
    if day_stem is not None and ground is not None:
        _same(by_role["人元"], "content", wuzidun_stem(day_stem, ground))
    if ground is not None:
        _same(overview, "guishen.earth_branch", ground)
    if (
        day_stem is not None
        and ground is not None
        and hour is not None
        and chosen is not None
    ):
        start, mapping = _build_guishen_mapping(day_stem, hour, chosen)
        god_name = mapping[ground]
        _same(by_role["贵神"], "shenjiang", god_name)
        _same(overview, "guishen.name", god_name)
        _same(overview, "guishen.start_branch", start)
        _same(overview, "guishen.direction", "逆" if start in "巳午未申酉戌" else "顺")
    god_name_val = _get(by_role["贵神"], "shenjiang")
    if god_name_val is not None:
        if not isinstance(god_name_val, str) or god_name_val not in GUISHEN_IDENTITIES:
            raise ValueError("金口诀贵神须为所选本的十二贵神")
        intrinsic = GUISHEN_IDENTITIES[god_name_val]
        _same(by_role["贵神"], "content", intrinsic[1])
        _same(by_role["贵神"], "intrinsic_ganzhi", intrinsic)
        _same(overview, "guishen.name", god_name_val)
        _same(overview, "guishen.branch", intrinsic[1])
        _same(overview, "guishen.intrinsic_ganzhi", intrinsic)
        _same(board, "stem_relations.guishen_intrinsic_ganzhi", intrinsic)
    if general is not None and ground is not None and hour is not None:
        located = EARTHLY_BRANCHES[
            (
                EARTHLY_BRANCHES.index(general)
                + EARTHLY_BRANCHES.index(ground)
                - EARTHLY_BRANCHES.index(hour)
            )
            % 12
        ]
        _same(by_role["将神"], "content", located)
        _same(by_role["将神"], "shenjiang", YUE_JIANG_NAMES[located])
        _same(overview, "yuejiang.branch", located)
        _same(overview, "yuejiang.name", YUE_JIANG_NAMES[located])
    if len(contents) == 4:
        inputs = [
            dict(
                label=k,
                polarity=(
                    "阳"
                    if (HEAVENLY_STEMS if k == "人元" else EARTHLY_BRANCHES).index(v)
                    % 2
                    == 0
                    else "阴"
                ),
            )
            for k, v in contents.items()
        ]
        use, _, _ = _jinkou_pick_use_position(inputs)
        _same(overview, "use_position", use)
        _same(board, "use_evidence.polarity_position", use)
        for label, row in by_role.items():
            _same(row, "is_use", label == use)


def _liuren(
    board: object,
    pillars: object,
    runyear: object = None,
    *,
    complete: bool = False,
) -> None:
    align_god_yin(board, pillars, runyear)
    align_seasonal(board, pillars)
    if board is None:
        return
    if not complete and all(
        _get(board, *path) is None
        for path in (
            ("calendar_policy", "effective_day_ganzhi"),
            ("auxiliary_stars", "day_ganzhi"),
            ("transmission_relations", "day_ganzhi"),
            ("emptiness_evidence", "day_ganzhi"),
        )
    ):
        board_dict = (
            board.model_dump(exclude_unset=True)
            if isinstance(board, BaseModel)
            else dict(board) if isinstance(board, Mapping) else {}
        )
        validate_selection(board_dict, _day(pillars))

    align_branch_relations(board, pillars)
    align_day_placements(board, _day(pillars))
    align_cross_harmony(board, _day(pillars))
    align_progression(board, pillars)

    day = _day(pillars)
    stem = _stem(_get(pillars, "day", "stem"))
    month = _branch(_get(pillars, "month", "branch"))
    hour = _branch(_get(pillars, "hour", "branch"))
    if month is not None:
        trines = _get(board, "transmission_relations", "trines")
        if isinstance(trines, list):
            for trine in trines:
                evidence = _get(trine, "nominal_seasonal_evidence")
                element = _get(trine, "nominal_element") or _get(
                    evidence, "nominal_element"
                )
                if (
                    evidence is not None
                    and isinstance(element, str)
                    and element
                    in (
                        "木",
                        "火",
                        "金",
                        "水",
                    )
                ):
                    for field, value in nominal_seasonal_evidence(
                        month, element
                    ).items():
                        _same(evidence, field, value)
    meta = _get(board, "meta")
    chosen = _diurnal(meta, hour)
    if day is not None:
        for path in (
            "calendar_policy.effective_day_ganzhi",
            "emptiness_evidence.day_ganzhi",
            "auxiliary_stars.day_ganzhi",
            "transmission_relations.day_ganzhi",
        ):
            _same(board, path, day)
        _same(board, "xun_head", xun_head_for_ganzhi(day))
        _same(board, "kongwang", kongwang_for_ganzhi(day))
        _same(runyear, "year_fate.day_ganzhi", day)
    for source, target in (
        ("year", "year_branch"),
        ("month", "month_building_branch"),
        ("hour", "hour_branch"),
    ):
        branch = _branch(_get(pillars, source, "branch"))
        if branch is not None:
            _same(board, "emptiness_evidence." + target, branch)
    stages = life_stage_cycle(stem) if stem is not None else None
    if stem is not None:
        _same(board, "life_stages.day_stem", stem)
        _same(board, "life_stages.stage_by_branch", stages)
    if month is not None:
        _same(board, "auxiliary_stars.month_building_branch", month)
        _same(
            board,
            "auxiliary_stars.nominal_month",
            (EARTHLY_BRANCHES.index(month) - 2) % 12 + 1,
        )
        _same(board, "month_building_element", branch_element_text(month))
    general = _branch(_get(board, "month_general", "branch"))
    if general is not None:
        _same(board, "emptiness_evidence.month_general_branch", general)
    sky = (
        _liureng_month_general_on_hour(hour_branch=hour, month_general_branch=general)
        if hour is not None and general is not None
        else None
    )
    earth = {v: k for k, v in sky.items()} if sky is not None else None
    empty_evidence = _get(board, "emptiness_evidence")
    if sky is not None and empty_evidence is not None:
        empty_rows = _get(empty_evidence, "rows")
        if isinstance(empty_rows, list):
            for row in empty_rows:
                seat = _branch(_get(row, "earth_branch"))
                if seat is not None:
                    _same(row, "sky_branch", sky[seat])
    gods = None
    profile = _get(meta, "guiren_profile")
    if (
        stem is not None
        and chosen is not None
        and sky is not None
        and profile is not None
    ):
        if profile not in ("liuren_common_v1", "tanyuan_xieji_v1"):
            raise ValueError("六壬贵人表配置未知")
        start = noble_start(stem, chosen, profile)
        assert earth is not None
        reverse = earth[start] in "巳午未申酉戌"
        gods = dict(
            zip(
                rotate_sequence(EARTHLY_BRANCHES, start, reverse=reverse),
                GUI_REN_SEQUENCE,
            )
        )
        _same(meta, "guiren_earth_branch", earth[start])
    twelve_board = _get(board, "twelve_board")
    if isinstance(twelve_board, list):
        for row in twelve_board:
            seated = _branch(_get(row, "earth_branch"))
            branch = _branch(_get(row, "sky_branch"))
            if seated is not None and sky is not None:
                _same(row, "sky_branch", sky[seated])
            if branch is not None and gods is not None:
                _same(row, "god", gods[branch])
    transmissions = _get(board, "three_transmissions")
    dun = xun_dun_stems(day) if day is not None else None
    for name in ("initial", "middle", "final"):
        node = _get(transmissions, name)
        branch = _branch(_get(node, "branch"))
        seated = _branch(_get(node, "earth_branch"))
        if branch is not None:
            if dun is not None:
                value = dun.get(branch)
                _same(node, "dun_stem", value)
                _same(node, "ganzhi", value + branch if value is not None else None)
                _same(node, "xun_kong", branch not in dun)
            if earth is not None:
                _same(node, "earth_branch", earth[branch])
            if gods is not None:
                _same(node, "god", gods[branch])
            if stages is not None:
                _same(node, "day_stem_life_stage", stages[branch])
            if stem is not None:
                _same(
                    node,
                    "relation",
                    liuqin_against_day(
                        stem_element_text(stem), branch_element_text(branch)
                    ),
                )
        if seated is not None:
            if dun is not None:
                _same(node, "seated_kong", seated not in dun)
            if stages is not None:
                _same(node, "seated_day_stem_life_stage", stages[seated])


class RenAnchoredOutput(PartialOutput):
    @model_validator(mode="after")
    def shared_ren_calculation_anchors(self, info: ValidationInfo) -> RenAnchoredOutput:
        complete = bool(info.context and info.context.get("full_result"))
        pillars = _get(self, "four_pillars")
        board = _get(self, "liuren")
        sub = _get(self, "subresults", "liuren")
        if sub is not None:
            subpillars = _get(sub, "four_pillars")
            _liuren(_get(sub, "liuren"), subpillars, complete=complete)
            if pillars is None:
                pillars = subpillars
        _liuren(board, pillars, _get(self, "runyear"), complete=complete)
        _jinkou(_get(self, "jinkou"), pillars, board)
        _jinkou(_get(self, "jinkou", "year_fate", "course"), pillars, board)
        _jinkou(
            _get(self, "jinkou", "natal_course", "course"),
            pillars,
            board,
        )
        return self


def require_complete_ren_anchors(
    key: str, result: Mapping[str, object], *, _year_course: bool = False
) -> None:
    """Only full service output: projection models deliberately stay partial."""
    if key not in REN_ANCHOR_TOOLS:
        return

    def require(obj: object, paths: tuple[str, ...]) -> None:
        for path in paths:
            if _get(obj, *path.split(".")) is None:
                raise ValueError(f"完整六壬金口诀输出缺少计算依据：{path}")

    def pillars(obj: object) -> None:
        for role in ("year", "month", "day", "hour"):
            require(obj, (role + ".stem", role + ".branch"))

    def liuren(obj: object) -> None:
        if not isinstance(obj, Mapping):
            raise ValueError("完整六壬金口诀输出缺少主盘依据")
        require_complete_god_yin(obj)
        yin_roles = _get(obj, "god_yin", "year_fate_uppers")
        natal_earth: object = None
        annual_earth: object = None
        if key == "liuren_yearly_timing":
            if not isinstance(yin_roles, Mapping):
                raise ValueError("完整类神阴神须保留同次年命上神及可空年命事实")
            for role in ("natal", "annual"):
                placement = _get(result, "runyear", "year_fate", role)
                if not isinstance(placement, dict) or "sky_branch" not in placement:
                    raise ValueError("完整类神阴神须保留同次年命上神及可空年命事实")
                if yin_roles[role] != placement["sky_branch"]:
                    raise ValueError("完整类神阴神不能替换同次年命上神")
            natal_earth = _get(result, "runyear", "year_fate", "natal", "earth_branch")
            annual_earth = _get(
                result, "runyear", "year_fate", "annual", "earth_branch"
            )
        elif yin_roles != {"natal": None, "annual": None}:
            raise ValueError("未提供六壬年命计算的入口不能给阴神编造年命上神")

        require_complete_seasonal(obj)
        require_complete_nominal_seasonal(obj)
        require_complete_published_dates(_get(obj, "calendar_policy"))
        require_complete_ordered_patterns(obj)
        require_complete_course_conditions(obj)
        require_complete_day_placements(obj)
        require_complete_cross_harmony(obj)
        require_complete_progression(obj)
        require_complete_branch_relations(obj)
        require_complete_emptiness(
            obj,
            natal=natal_earth if isinstance(natal_earth, str) else None,
            annual=annual_earth if isinstance(annual_earth, str) else None,
        )
        require(
            obj,
            (
                "calendar_policy.effective_day_ganzhi",
                "month_general.branch",
                "xun_head",
                "kongwang",
                "life_stages.day_stem",
                "auxiliary_stars.day_ganzhi",
                "auxiliary_stars.month_building_branch",
                "transmission_relations.day_ganzhi",
                "transmission_relations.rows",
                "transmission_relations.rules",
                "transmission_relations.trines",
                "meta.guiren_profile",
                "meta.is_diurnal",
                "meta.diurnal_evidence.hour_branch",
            ),
        )
        validate_selection(obj, complete=True)

    if not _year_course:
        board = _get(result, "liuren")
        if key == "sanshi_combined_chart":
            sub = _get(result, "subresults", "liuren")
            pillars(_get(sub, "four_pillars"))
            sub_board = _get(sub, "liuren")
            if sub_board is not None and sub_board is not board:
                liuren(sub_board)
        else:
            pillars(_get(result, "four_pillars"))
        if key != "jinkou" or board is not None:
            liuren(board)
    if key == "liuren_yearly_timing":
        require(result, ("runyear.year_fate.day_ganzhi",))
    if key == "jinkou":
        jinkou_board = result.get("jinkou")
        if not isinstance(jinkou_board, Mapping):
            raise ValueError("完整金口诀输出缺少主盘依据")
        align_branch_breaks(jinkou_board, complete=True)
        published_dates_policy = _get(
            result, "calendar_context", "ren_calendar_policy"
        ) or jinkou_board.get("calendar_policy")
        require_complete_published_dates(published_dates_policy)
        require_complete_strength_evidence(jinkou_board)
        require_complete_pattern_anchors(jinkou_board)
        require_complete_branch_stars(jinkou_board)
        require_complete_relations(jinkou_board)
        require(
            result,
            (
                "jinkou.calendar_policy.effective_day_ganzhi",
                "jinkou.stem_relations.day_stem",
                "jinkou.definition_evidence.day_stem",
                "jinkou.definition_evidence.hour_branch",
                "jinkou.definition_evidence.day_night_candidates",
                "jinkou.definition_evidence.ding_routes",
                "jinkou.overview.di_fen",
                "jinkou.overview.month_general.branch",
                "jinkou.overview.is_diurnal",
                "jinkou.overview.diurnal_evidence.hour_branch",
                "jinkou.rows",
                "jinkou.relations.si_jue.natal.left_branch",
                "jinkou.relations.si_jue.natal.status",
                "jinkou.relations.si_jue.natal.input_source",
                "jinkou.relations.si_jue.unavailable",
            ),
        )
        natal = _get(result, "jinkou", "relations", "si_jue", "natal")
        if not isinstance(natal, dict) or any(
            k not in natal for k in ("right_branch", "matched", "element")
        ):
            raise ValueError("完整金口诀须保留大绝的本命支及可空判定")
        if not _year_course:
            require_complete_natal_course(jinkou_board)
            natal_child = _get(result, "jinkou", "natal_course", "course")
            if isinstance(natal_child, Mapping):
                require_complete_ren_anchors(
                    key, dict(result, jinkou=natal_child), _year_course=True
                )
            annual = _get(result, "jinkou", "year_fate")
            if not isinstance(annual, dict) or any(
                name not in annual
                for name in (
                    "method_id",
                    "status",
                    "birth_year_ganzhi",
                    "birth_xun",
                    "gender",
                    "age_ordinal",
                    "age_basis",
                    "course_basis",
                    "start_ganzhi",
                    "direction",
                    "ganzhi",
                    "branch",
                    "missing_inputs",
                    "natal_branch",
                    "natal_branch_source",
                    "source_section",
                    "course",
                )
            ):
                raise ValueError("完整金口诀须保留京本行年资料及可空另课")
            annual_course = annual.get("course")
            if isinstance(annual_course, Mapping):
                require(annual_course, ("overview.di_fen_source",))
                child = dict(result, jinkou=annual_course)
                require_complete_ren_anchors(key, child, _year_course=True)


class LiurenChartOutput(ProjectedOutput, RenAnchoredOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    four_pillars: FourPillars | None = None
    liuren: Liuren | None = None


class LiurenYearlyTimingOutput(ProjectedOutput, RenAnchoredOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    coverage: Object | None = None
    four_pillars: FourPillars | None = None
    liuren: Liuren | None = None
    runyear: Runyear | None = None


class JinkouOutput(ProjectedOutput, RenAnchoredOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    calendar_context: CalendarContext | None = None
    four_pillars: FourPillars | None = None
    jinkou: Jinkou | None = None


class SanshiCombinedChartOutput(ProjectedOutput, RenAnchoredOutput):
    run_metadata: RunMetadata | None = None
    analysis_context: AnalysisContext | None = None
    analysis_type: str | None = None
    four_pillars: FourPillars | None = None
    liuren: Liuren | None = None
    qimen: Qimen | None = None
    taiyi: Taiyi | None = None
    subresults: SanshiSubresults | None = None
    summary: Object | list[JsonValue] | str | None = None
    synthesis: SanshiSynthesis | None = None
