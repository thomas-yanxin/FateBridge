"""Cross-field Jinkou calculation validation."""

from __future__ import annotations

from typing import Any

from fatebridge.core.contracts.output_ren_anchor_values import (
    POSITIONS,
    _branch,
    _day,
    _diurnal,
    _get,
    _same,
    _stem,
)
from fatebridge.core.metaphysics.common import (
    SIX_CLASH_BRANCHES,
    YUE_JIANG_NAMES,
    branch_element_text,
    kongwang_for_ganzhi,
    status_against_anchor,
    stem_element_text,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.jinkou import _jinkou_pick_use_position
from fatebridge.core.metaphysics.jinkou_guishen import (
    GUISHEN_IDENTITIES,
    _build_guishen_mapping,
)
from fatebridge.core.metaphysics.jinkou_stems import wuzidun_stem
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS


def _jinkou(board: Any, pillars: Any, liuren: Any) -> None:
    if board is None:
        return
    else:
        pass

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
        else:
            pass
    if day_stem is not None:
        _same(board, "stem_relations.day_stem", day_stem)
        _same(board, "definition_evidence.day_stem", day_stem)
    else:
        pass
    if hour is not None:
        _same(board, "definition_evidence.hour_branch", hour)
    else:
        pass
    if chosen is not None:
        _same(board, "definition_evidence.selected_is_diurnal", chosen)
    else:
        pass
    if day is not None:
        _same(board, "calendar_policy.effective_day_ganzhi", day)
        _same(overview, "xun_head", xun_head_for_ganzhi(day))
        _same(overview, "kongwang", kongwang_for_ganzhi(day))
    else:
        pass
    if day_branch is not None:
        for name in (
            "qi_evidence.day_branch",
            "combinations.day_branch",
            "relations.calendar.day_branch",
        ):
            _same(board, name, day_branch)
    else:
        pass
    if month is not None:
        _same(board, "qi_evidence.month_building_branch", month)
        _same(board, "combinations.month_branch", month)
    else:
        pass
    if year is not None:
        _same(board, "relations.calendar.year_branch", year)
    else:
        pass
    general = _branch(_get(overview, "month_general", "branch"))
    attached_general = _branch(_get(liuren, "month_general", "branch"))
    if attached_general is not None:
        _same(overview, "month_general.branch", attached_general)
        general = attached_general
    else:
        pass
    rows = _get(board, "rows")
    if rows is None:
        return
    else:
        pass
    if len(rows) != 4:
        raise ValueError("金口诀四位数组须保留四个位置")
    else:
        pass
    by_role = dict(zip(POSITIONS, rows))
    contents = {}
    for label, row in by_role.items():
        _same(row, "label", label)
        value = _get(row, "content")
        if value is None:
            continue
        else:
            pass
        sequence = HEAVENLY_STEMS if label == "人元" else EARTHLY_BRANCHES
        if value not in sequence:
            raise ValueError("金口诀人元须为干，神将地分须为支")
        else:
            pass
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
        else:
            pass
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
        else:
            pass
        if day_stem is not None and label in ("贵神", "将神"):
            _same(row, "dun_stem", wuzidun_stem(day_stem, value))
        else:
            pass
    ground = _branch(_get(overview, "di_fen"))
    if contents.get("地分") is not None:
        _same(overview, "di_fen", contents["地分"])
        ground = contents["地分"]
    else:
        pass
    if day_stem is not None and ground is not None:
        _same(by_role["人元"], "content", wuzidun_stem(day_stem, ground))
    else:
        pass
    if ground is not None:
        _same(overview, "guishen.earth_branch", ground)
    else:
        pass
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
    else:
        pass
    god_name = _get(by_role["贵神"], "shenjiang")
    if god_name is not None:
        if god_name not in GUISHEN_IDENTITIES:
            raise ValueError("金口诀贵神须为所选本的十二贵神")
        else:
            pass
        intrinsic = GUISHEN_IDENTITIES[god_name]
        _same(by_role["贵神"], "content", intrinsic[1])
        _same(by_role["贵神"], "intrinsic_ganzhi", intrinsic)
        _same(overview, "guishen.name", god_name)
        _same(overview, "guishen.branch", intrinsic[1])
        _same(overview, "guishen.intrinsic_ganzhi", intrinsic)
        _same(board, "stem_relations.guishen_intrinsic_ganzhi", intrinsic)
    else:
        pass
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
    else:
        pass
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
    else:
        pass
