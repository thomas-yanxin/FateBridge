"""Coexisting branch relations from 探原, separate from transmission selection."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES
from .common import SEXAGENARY_INDEX
from .liureng_transmissions import STEM_HOUSES

# Printed pairs, not a day-polarity algorithm inferred from the prose.
PAIRS = {
    "liuhe": ("子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未"),
    "liupo": ("午卯", "辰丑", "酉子", "戌未", "亥寅", "申巳"),
    "liuhai": ("酉戌", "申亥", "未子", "午丑", "巳寅", "辰卯"),
    "liuchong": ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"),
}
XING = dict(zip("子卯寅巳申丑戌未辰午酉亥", "卯子巳申寅戌未丑辰午酉亥"))


def branch_pair_facts(left: str, right: str) -> dict[str, Any]:
    if left not in EARTHLY_BRANCHES or right not in EARTHLY_BRANCHES:
        raise ValueError("六壬支位关系需要单个有效地支")
    pair = frozenset((left, right))
    return {
        "same_branch": left == right,
        **{k: any(pair == frozenset(p) for p in pairs) for k, pairs in PAIRS.items()},
        "left_xing_right": XING[left] == right,
        "right_xing_left": XING[right] == left,
        "harmony_annotation": (
            "破合"
            if pair == frozenset("寅亥")
            else "刑合" if pair == frozenset("巳申") else None
        ),
    }


def branch_relations(
    *,
    day_ganzhi: str,
    year_branch: str,
    month_branch: str,
    hour_branch: str,
    month_general_branch: str,
    sky_by_earth: dict[str, str],
    lessons: list[dict[str, Any]],
    transmissions: list[str],
) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("六壬支位关系需要有效日干支")
    branches = set(EARTHLY_BRANCHES)
    if any(
        v not in branches
        for v in (year_branch, month_branch, hour_branch, month_general_branch)
    ):
        raise ValueError("六壬支位关系需要有效年月时支与月将")
    if set(sky_by_earth) != branches or set(sky_by_earth.values()) != branches:
        raise ValueError("六壬支位关系需要完整天地盘")
    offsets = {
        (EARTHLY_BRANCHES.index(s) - EARTHLY_BRANCHES.index(e)) % 12
        for e, s in sky_by_earth.items()
    }
    if offsets != {
        (
            EARTHLY_BRANCHES.index(month_general_branch)
            - EARTHLY_BRANCHES.index(hour_branch)
        )
        % 12
    }:
        raise ValueError("六壬支位关系天地盘与月将加时不一致")
    house = STEM_HOUSES[day_ganzhi[0]]
    lower = [house, sky_by_earth[house], day_ganzhi[1], sky_by_earth[day_ganzhi[1]]]
    if len(lessons) != 4 or any(
        l.get("index") != i
        or l.get("lower_branch") != b
        or l.get("upper_branch") != sky_by_earth[b]
        for i, (l, b) in enumerate(zip(lessons, lower), 1)
    ):
        raise ValueError("六壬支位关系四课与日干寄宫及天地盘不一致")
    if len(transmissions) != 3 or any(v not in branches for v in transmissions):
        raise ValueError("六壬支位关系需要完整三传")
    rows = []

    def add(
        identifier: str, left_role: str, right_role: str, left: str, right: str
    ) -> None:
        rows.append(
            dict(
                id=identifier,
                left_role=left_role,
                right_role=right_role,
                left_branch=left,
                right_branch=right,
                facts=branch_pair_facts(left, right),
            )
        )

    for earth in EARTHLY_BRANCHES:
        add(f"seat.{earth}", "天盘支", "地盘支", sky_by_earth[earth], earth)
    for i, lesson in enumerate(lessons, 1):
        add(
            f"lesson.{i}",
            f"第{i}课上神",
            "日干寄宫支" if i == 1 else f"第{i}课下支",
            lesson["upper_branch"],
            lesson["lower_branch"],
        )
    for name, a, b in (
        ("initial_middle", 0, 1),
        ("middle_final", 1, 2),
        ("initial_final", 0, 2),
    ):
        add(
            f"transmission.{name}",
            ("初传", "中传", "末传")[a],
            ("初传", "中传", "末传")[b],
            transmissions[a],
            transmissions[b],
        )
    targets = [
        (f"lesson.{i}", f"第{i}课上神", l["upper_branch"])
        for i, l in enumerate(lessons, 1)
    ]
    targets += [
        (f"transmission.{p}", label, b)
        for p, label, b in zip(
            ("initial", "middle", "final"), ("初传", "中传", "末传"), transmissions
        )
    ]
    calendar_branches = dict(
        year=year_branch, month=month_branch, day=day_ganzhi[1], hour=hour_branch
    )
    for (role, ref), label in zip(
        calendar_branches.items(), ("年支", "月支", "日支", "时支")
    ):
        for identifier, target_label, target in targets:
            add(f"contact.{role}.{identifier}", target_label, label, target, ref)
    return dict(
        ruleset_id="tanyuan_branch_relations_v1",
        source_title="大六壬探原·论合、破、害、刑、冲（支位条件）",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[91, 92, 95, 96, 97],
        day_ganzhi=day_ganzhi,
        calendar_branches=calendar_branches,
        month_general_branch=month_general_branch,
        sky_by_earth=dict(sky_by_earth),
        lesson_branches=[
            dict(
                index=i, lower_branch=l["lower_branch"], upper_branch=l["upper_branch"]
            )
            for i, l in enumerate(lessons, 1)
        ],
        transmission_branches=dict(zip(("initial", "middle", "final"), transmissions)),
        rows=rows,
        comprehensive_judgement=None,
        complete_classical_conformance=False,
        scope="按所选原页并列同支、六合、六冲、六害、六破及两个方向的刑；寅亥破合、巳申刑合另列原名，不以一项取消其他关系。首课仅比较日干寄宫支，不以该支五行替代日干贼克；伏吟循刑与九宗门取传算法保留。十二位、四课、三传配对及年月日时接触共47条是同盘位置比较，不是47条独立原典课例。六破采用印刷配对，不另造日阴阳算法；未裁定被引大全异说、救制优先、合化或综合吉凶，不据合独断成局。",
    )
