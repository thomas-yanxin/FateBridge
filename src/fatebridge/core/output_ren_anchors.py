"""Cross-object calculation facts, without inventing missing projected anchors."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_validator

from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

from .metaphysics.common import (
    GUI_REN_SEQUENCE,
    SIX_CLASH_BRANCHES,
    YUE_JIANG_NAMES,
    branch_element_text,
    kongwang_for_ganzhi,
    liuqin_against_day,
    rotate_sequence,
    sexagenary_index_for,
    status_against_anchor,
    stem_element_text,
    xun_head_for_ganzhi,
)
from .metaphysics.jinkou_stems import wuzidun_stem
from .metaphysics.liureng_life_stages import life_stage_cycle
from .metaphysics.ren_diurnal import resolve_diurnal
from .metaphysics.ren_evidence import xun_dun_stems
from .metaphysics.ren_gods import noble_start
from .output_base import PartialOutput

POSITIONS = ("人元", "贵神", "将神", "地分")


def _get(obj: Any, *parts: str) -> Any:
    for part in parts:
        obj = obj.get(part) if isinstance(obj, dict) else getattr(obj, part, None)
        if obj is None:
            break
    return obj


def _has(obj: Any, name: str) -> bool:
    if isinstance(obj, BaseModel):
        return name in obj.model_fields_set
    return isinstance(obj, dict) and name in obj


def _same(obj: Any, field: str, expected: Any) -> None:
    actual = _get(obj, *field.split("."))
    if actual is not None and actual != expected:
        raise ValueError(f"六壬金口诀同次计算依据不一致：{field}")


def _branch(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in EARTHLY_BRANCHES:
        raise ValueError("六壬金口诀支位须为十二地支")
    return value


def _stem(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in HEAVENLY_STEMS:
        raise ValueError("六壬金口诀日干须为十天干")
    return value


def _day(pillars: Any) -> str | None:
    a, b = _stem(_get(pillars, "day", "stem")), _branch(_get(pillars, "day", "branch"))
    if a is None or b is None:
        return None
    value = a + b
    try:
        sexagenary_index_for(value)
    except KeyError as exc:
        raise ValueError("六壬金口诀占日须为有效六十甲子") from exc
    return value


def _diurnal(holder: Any, hour: str | None) -> bool | None:
    evidence = _get(holder, "diurnal_evidence")
    if hour is not None:
        _same(evidence, "hour_branch", hour)
        if _has(evidence, "explicit_choice"):
            expected = resolve_diurnal(hour, _get(evidence, "explicit_choice"))
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


def _jinkou(board: Any, pillars: Any, liuren: Any) -> None:
    if board is None:
        return
    from fatebridge.core.metaphysics.jinkou_guishen import (
        GUISHEN_IDENTITIES,
        _build_guishen_mapping,
    )

    from .metaphysics.jinkou import _jinkou_pick_use_position

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
    if len(rows) != 4:
        raise ValueError("金口诀四位数组须保留四个位置")
    by_role = dict(zip(POSITIONS, rows))
    contents = {}
    for label, row in by_role.items():
        _same(row, "label", label)
        value = _get(row, "content")
        if value is None:
            continue
        sequence = HEAVENLY_STEMS if label == "人元" else EARTHLY_BRANCHES
        if value not in sequence:
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
    god_name = _get(by_role["贵神"], "shenjiang")
    if god_name is not None:
        if god_name not in GUISHEN_IDENTITIES:
            raise ValueError("金口诀贵神须为所选本的十二贵神")
        intrinsic = GUISHEN_IDENTITIES[god_name]
        _same(by_role["贵神"], "content", intrinsic[1])
        _same(by_role["贵神"], "intrinsic_ganzhi", intrinsic)
        _same(overview, "guishen.name", god_name)
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


def _liuren(board: Any, pillars: Any, runyear: Any = None) -> None:
    from .output_liuren_god_yin import align_god_yin

    align_god_yin(board, pillars, runyear)
    from .output_liuren_seasonal import align_seasonal

    align_seasonal(board, pillars)
    if board is None:
        return
    from .output_liuren_selection import validate_selection

    if hasattr(board, "model_dump"):
        validate_selection(board.model_dump(exclude_unset=True), _day(pillars))
    else:
        validate_selection(board, _day(pillars))
    from .output_liuren_branches import align_branch_relations

    align_branch_relations(board, pillars)
    from .output_liuren_day_placements import align_day_placements

    align_day_placements(board, _day(pillars))
    from .output_liuren_cross_harmony import align_cross_harmony

    align_cross_harmony(board, _day(pillars))
    from .output_liuren_progression import align_progression

    align_progression(board, pillars)
    from .metaphysics.liureng import _liureng_month_general_on_hour

    day = _day(pillars)
    stem = _stem(_get(pillars, "day", "stem"))
    month = _branch(_get(pillars, "month", "branch"))
    hour = _branch(_get(pillars, "hour", "branch"))
    if month is not None:
        from .metaphysics.liureng_trine_seasonal import nominal_seasonal_evidence

        for trine in _get(board, "transmission_relations", "trines") or []:
            evidence = _get(trine, "nominal_seasonal_evidence")
            element = _get(trine, "nominal_element") or _get(
                evidence, "nominal_element"
            )
            if evidence is not None and element in ("木", "火", "金", "水"):
                for field, value in nominal_seasonal_evidence(month, element).items():
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
        for row in _get(empty_evidence, "rows") or []:
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
    for row in _get(board, "twelve_board") or []:
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
    def shared_ren_calculation_anchors(self) -> RenAnchoredOutput:
        pillars = _get(self, "four_pillars")
        _liuren(_get(self, "liureng"), pillars, _get(self, "runyear"))
        _jinkou(_get(self, "jinkou"), pillars, _get(self, "liureng"))
        _jinkou(
            _get(self, "jinkou", "year_fate", "course"), pillars, _get(self, "liureng")
        )
        _jinkou(
            _get(self, "jinkou", "natal_course", "course"),
            pillars,
            _get(self, "liureng"),
        )
        sub = _get(self, "subresults", "liureng_gods")
        if sub is not None:
            subpillars = _get(sub, "four_pillars")
            _liuren(_get(sub, "liureng"), subpillars)
            # The legacy 三式 root shares this Liu Ren computation, not the
            # Qimen/Taiyi branch conventions or an invented root four_pillars.
            _liuren(_get(self, "liureng"), subpillars)
        return self


REN_ANCHOR_TOOLS = frozenset(
    {"jinkou", "liureng_gods", "liureng_runyear", "sanshiunited"}
)


def require_complete_ren_anchors(
    key: str, result: dict[str, Any], *, _year_course: bool = False
) -> None:
    """Only full service output: projection models deliberately stay partial."""
    if key not in REN_ANCHOR_TOOLS:
        return

    def require(obj: Any, paths: tuple[str, ...]) -> None:
        for path in paths:
            if _get(obj, *path.split(".")) is None:
                raise ValueError(f"完整六壬金口诀输出缺少计算依据：{path}")

    def pillars(obj: Any) -> None:
        for role in ("year", "month", "day", "hour"):
            require(obj, (role + ".stem", role + ".branch"))

    def liuren(obj: Any) -> None:
        from .output_liuren_god_yin import require_complete_god_yin

        require_complete_god_yin(obj)
        yin_roles = _get(obj, "god_yin", "year_fate_uppers")
        if key == "liureng_runyear":
            for role in ("natal", "annual"):
                placement = _get(result, "runyear", "year_fate", role)
                if not isinstance(placement, dict) or "sky_branch" not in placement:
                    raise ValueError("完整类神阴神须保留同次年命上神及可空年命事实")
                if yin_roles[role] != placement["sky_branch"]:
                    raise ValueError("完整类神阴神不能替换同次年命上神")
        elif yin_roles != {"natal": None, "annual": None}:
            raise ValueError("未提供六壬年命计算的入口不能给阴神编造年命上神")
        from .output_liuren_seasonal import require_complete_seasonal

        require_complete_seasonal(obj)
        from .output_liuren_trine_seasonal import require_complete_nominal_seasonal

        require_complete_nominal_seasonal(obj)
        from .output_ren_term_dates import require_complete_published_dates

        require_complete_published_dates(_get(obj, "calendar_policy"))
        from .output_liuren_branches import require_complete_branch_relations
        from .output_liuren_course_conditions import require_complete_course_conditions
        from .output_liuren_cross_harmony import require_complete_cross_harmony
        from .output_liuren_day_placements import require_complete_day_placements
        from .output_liuren_emptiness import require_complete_emptiness
        from .output_liuren_ordered_patterns import require_complete_ordered_patterns
        from .output_liuren_progression import require_complete_progression

        require_complete_ordered_patterns(obj)
        require_complete_course_conditions(obj)
        require_complete_day_placements(obj)
        require_complete_cross_harmony(obj)
        require_complete_progression(obj)
        require_complete_branch_relations(obj)
        require_complete_emptiness(obj)
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
        from .output_liuren_selection import require_complete_selection

        require_complete_selection(obj)

    if key == "sanshiunited":
        sub = _get(result, "subresults", "liureng_gods")
        pillars(_get(sub, "four_pillars"))
        liuren(_get(sub, "liureng"))
    else:
        pillars(_get(result, "four_pillars"))
    liuren(_get(result, "liureng"))
    if key == "liureng_runyear":
        require(result, ("runyear.year_fate.day_ganzhi",))
    if key == "jinkou":
        from .output_jinkou_breaks import align_branch_breaks

        align_branch_breaks(result["jinkou"], complete=True)
        from .output_ren_term_dates import require_complete_published_dates

        require_complete_published_dates(result["jinkou"]["calendar_policy"])
        from .output_jinkou_strength import require_complete_strength_evidence

        require_complete_strength_evidence(result["jinkou"])
        from .output_jinkou_patterns import require_complete_pattern_anchors

        require_complete_pattern_anchors(result["jinkou"])
        from .output_jinkou_definitions import require_complete_chapter_witness

        require_complete_chapter_witness(result["jinkou"])
        from .output_jinkou_branch_stars import require_complete_branch_stars

        require_complete_branch_stars(result["jinkou"])
        from .output_jinkou_relations import require_complete_relations

        require_complete_relations(result["jinkou"])
        require(
            result,
            (
                "jinkou.calendar_policy.effective_day_ganzhi",
                "jinkou.stem_relations.day_stem",
                "jinkou.definition_evidence.day_stem",
                "jinkou.definition_evidence.hour_branch",
                "jinkou.definition_evidence.entries",
                "jinkou.definition_evidence.cross_generation_hypotheses",
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
            key not in natal for key in ("right_branch", "matched", "element")
        ):
            raise ValueError("完整金口诀须保留大绝的本命支及可空判定")
        traces = [
            t
            for t in _get(result, "jinkou", "rule_trace") or []
            if _get(t, "rule_id") == "jinkou.jingben_relations"
        ]
        traced = (
            _get(traces[0], "result", "si_jue", "natal") if len(traces) == 1 else None
        )
        if not isinstance(traced, dict) or any(
            key not in traced
            for key in (
                "left_branch",
                "right_branch",
                "matched",
                "element",
                "status",
                "input_source",
            )
        ):
            raise ValueError("完整金口诀须保留唯一的将命大绝规则轨迹")
        if not _year_course:
            from .output_jinkou_natal_course import require_complete_natal_course

            require_complete_natal_course(result["jinkou"])
            natal_child = _get(result, "jinkou", "natal_course", "course")
            if natal_child is not None:
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
                    "course_ground_is_observed",
                    "start_ganzhi",
                    "direction",
                    "ganzhi",
                    "branch",
                    "missing_inputs",
                    "natal_branch",
                    "natal_branch_source",
                    "age_boundary_classically_verified",
                    "birth_year_calendar_boundary_verified",
                    "comprehensive_year_fate_adjudicated",
                    "source_url",
                    "source_sha256",
                    "source_section",
                    "original_pdf_pages",
                    "relation_adjudication",
                    "relation_note",
                    "scope",
                    "course",
                )
            ):
                raise ValueError("完整金口诀须保留京本行年资料及可空另课")
            if annual["course"] is not None:
                require(annual["course"], ("overview.di_fen_source",))
                child = dict(result, jinkou=annual["course"])
                require_complete_ren_anchors(key, child, _year_course=True)
