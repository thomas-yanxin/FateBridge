"""Cross-field Liuren calculation validation."""

from __future__ import annotations

from typing import Any

from fatebridge.core.contracts.output_liuren_branches import align_branch_relations
from fatebridge.core.contracts.output_liuren_cross_harmony import align_cross_harmony
from fatebridge.core.contracts.output_liuren_day_placements import align_day_placements
from fatebridge.core.contracts.output_liuren_god_yin import align_god_yin
from fatebridge.core.contracts.output_liuren_progression import align_progression
from fatebridge.core.contracts.output_liuren_seasonal import align_seasonal
from fatebridge.core.contracts.output_liuren_selection import validate_selection
from fatebridge.core.contracts.output_ren_anchor_values import (
    _branch,
    _day,
    _diurnal,
    _get,
    _same,
    _stem,
)
from fatebridge.core.metaphysics.common import (
    GUI_REN_SEQUENCE,
    branch_element_text,
    kongwang_for_ganzhi,
    liuqin_against_day,
    rotate_sequence,
    stem_element_text,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.liureng import _liureng_month_general_on_hour
from fatebridge.core.metaphysics.liureng_life_stages import life_stage_cycle
from fatebridge.core.metaphysics.liureng_trine_seasonal import nominal_seasonal_evidence
from fatebridge.core.metaphysics.ren_evidence import xun_dun_stems
from fatebridge.core.metaphysics.ren_gods import noble_start
from fatebridge.utils.data import EARTHLY_BRANCHES


def _liuren(
    board: Any, pillars: Any, runyear: Any = None, *, complete: bool = False
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

        validate_selection(board.model_dump(exclude_unset=True), _day(pillars))

    align_branch_relations(board, pillars)

    align_day_placements(board, _day(pillars))

    align_cross_harmony(board, _day(pillars))

    align_progression(board, pillars)

    day = _day(pillars)
    stem = _stem(_get(pillars, "day", "stem"))
    month = _branch(_get(pillars, "month", "branch"))
    hour = _branch(_get(pillars, "hour", "branch"))
    if month is not None:

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
