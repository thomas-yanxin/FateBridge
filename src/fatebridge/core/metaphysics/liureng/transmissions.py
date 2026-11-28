"""Nine-method Liu Ren transmissions, 64-lesson patterns and transmission relations."""

from __future__ import annotations

from typing import Any, Literal

from fatebridge.core.metaphysics.common import (
    GUI_REN_SEQUENCE,
    liuqin_against_day,
)
from fatebridge.core.metaphysics.liureng.stars import (
    GOD_ELEMENTS,
    STEM_HOUSES,
    life_stage_cycle,
    nominal_seasonal_evidence,
)
from fatebridge.core.metaphysics.ren_calendar import (
    liuren_annotation_note,
    xun_dun_stems,
)
from fatebridge.core.metaphysics.ren_gods import GuirenProfile, noble_start
from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    HEAVENLY_STEMS,
    SEXAGENARY_INDEX,
    branch_element_text,
    kongwang_for_ganzhi,
    rotate_sequence,
    stem_element_text,
    xun_head_for_ganzhi,
)

ShehaiMethod = Literal["depth_first", "meng_zhong_first"]
PUNISHMENT = dict(zip("寅巳申丑戌未子卯辰午酉亥", "巳申寅戌未丑卯子辰午酉亥"))

TRINES = (("寅午戌", "火"), ("申子辰", "水"), ("巳酉丑", "金"), ("亥卯未", "木"))
TRINE_NAMES = {"火": "炎上", "水": "润下", "金": "从革", "木": "曲直"}

ORDERED_PATTERNS = (
    ("zhuolun", "斫轮", "卯戌巳"),
    ("zhuyin", "铸印", "巳戌卯"),
    ("xuangai", "轩盖", "午卯子"),
)

RULE_NAMES = (
    ("birth_to_tomb", "初生末墓"),
    ("tomb_to_birth", "初墓末生"),
    ("final_controls_initial", "末克初"),
    ("control_chain", "干初中末递克"),
    ("all_branch_empty", "三传支神皆旬空"),
    ("initial_middle_empty", "初中空而末实"),
    ("middle_final_empty", "中末空而初实"),
    ("chao_zhi", "朝枝格条件"),
    ("chao_ri", "朝日格条件"),
)

STAGE_PAIRS = (
    ("S01", "退龄", "长生", "青龙"),
    ("S02", "洁己", "沐浴", "玄武"),
    ("S03", "凶服", "冠带", "白虎"),
    ("S04", "衣禄", "临官", "太常"),
    ("S05", "崇位", "帝旺", "贵人"),
    ("S06", "荒淫", "衰", "天后"),
    ("S07", "久患", "病", "勾陈"),
    ("S08", "暗死", "死", "太阴"),
    ("S09", "禁系", "墓", "天空"),
    ("S10", "决绝", "绝", "朱雀"),
    ("S11", "孕童", "胎", "六合"),
    ("S12", "异产", "养", "螣蛇"),
)
GOD_PAIRS = tuple(
    (f"G{i:02}", name, god)
    for i, (name, god) in enumerate(
        zip(
            (
                "干贵",
                "恐惧",
                "文书",
                "交合",
                "争讼",
                "喜庆",
                "朝天",
                "灾伤",
                "宴会",
                "逃脱",
                "暗昧",
                "干妇",
            ),
            GUI_REN_SEQUENCE,
        ),
        1,
    )
)


def _shift(branch: str, offset: int) -> str:
    return EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(branch) + offset) % 12]


def _controls(left: str, right: str) -> bool:
    return ELEMENT_CONTROLS[left] == right


def _unique(lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_upper: dict[str, dict[str, Any]] = {}
    for lesson in lessons:
        by_upper.setdefault(lesson["upper_branch"], lesson)
    return list(by_upper.values())


def harm_walk(
    lesson: dict[str, Any],
    day_stem: str,
    sky: dict[str, str],
    *,
    include_terminal: bool = False,
) -> dict[str, Any]:
    """Walk earthly branches from earth[upper] to upper, counting 正五行 + 寄干 harms."""
    earth = {upper: lower for lower, upper in sky.items()}
    upper = lesson["upper_branch"]
    element = branch_element_text(upper)
    lower_element = (
        stem_element_text(day_stem)
        if lesson["index"] == 1
        else branch_element_text(lesson["lower_branch"])
    )
    thief = _controls(lower_element, element)

    def _step_for(pos: str) -> dict[str, Any]:
        contributions: list[dict[str, Any]] = [
            {
                "kind": "branch",
                "token": pos,
                "element": branch_element_text(pos),
            }
        ] + [
            {"kind": "lodged_stem", "token": stem, "element": stem_element_text(stem)}
            for stem, house in STEM_HOUSES.items()
            if house == pos
        ]
        for item in contributions:
            item["counts_as_harm"] = (
                _controls(item["element"], element)
                if thief
                else _controls(element, item["element"])
            )
        return {"earth_branch": pos, "contributions": contributions}

    steps: list[dict[str, Any]] = []
    position = earth[upper]
    while position != upper:
        steps.append(_step_for(position))
        position = _shift(position, 1)
    if include_terminal:
        steps.append(_step_for(upper))
    return {
        "lesson_index": lesson["index"],
        "upper_branch": upper,
        "upper_element": element,
        "starting_earth_branch": earth[upper],
        "direction": "受克" if thief else "施克",
        "steps": steps,
        "harm_count": sum(
            item["counts_as_harm"] for step in steps for item in step["contributions"]
        ),
        "terminal_home_counted": include_terminal,
    }


def select_transmissions(
    day_stem: str,
    day_branch: str,
    sky: dict[str, str],
    lessons: list[dict[str, Any]],
    *,
    shehai_method: ShehaiMethod = "depth_first",
    harm_include_terminal: bool = False,
) -> tuple[str, str, str, list[str], int | None]:
    """Return styles, derivation, three gods, and the actual source lesson."""
    if shehai_method not in ("depth_first", "meng_zhong_first"):
        raise ValueError("shehai_method 仅支持 depth_first 或 meng_zhong_first")
    earth = {upper: lower for lower, upper in sky.items()}
    yang = HEAVENLY_STEMS.index(day_stem) % 2 == 0
    stem_element = stem_element_text(day_stem)
    gan_upper, _, zhi_upper, zhi_yin = (l["upper_branch"] for l in lessons)
    is_fuyin = zhi_upper == day_branch
    is_fanyin = zhi_upper == _shift(day_branch, 6)

    def follow(initial: str) -> list[str]:
        middle = sky[initial]
        return [initial, middle, sky[middle]]

    def same_polarity(lesson: dict[str, Any]) -> bool:
        return (EARTHLY_BRANCHES.index(lesson["upper_branch"]) % 2 == 0) == yang

    def _meng_zhong_step(
        cands: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], str | None]:
        for group, detail in (("寅巳申亥", "见机"), ("子卯午酉", "察微")):
            match = [l for l in cands if earth[l["upper_branch"]] in group]
            if len(match) == 1:
                return match, detail
            if match:
                return match, None
        return cands, None

    def _depth_step(
        cands: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], str | None]:
        walks = [
            harm_walk(lesson, day_stem, sky, include_terminal=harm_include_terminal)
            for lesson in cands
        ]
        depths = [(lesson, walk["harm_count"]) for lesson, walk in zip(cands, walks)]
        deepest = max(value for _, value in depths)
        matched = [l for l, value in depths if value == deepest]
        return matched, ("涉害" if len(matched) == 1 else None)

    def choose(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
        candidates = _unique(candidates)
        if len(candidates) == 1:
            return candidates[0], "贼克"
        preferred = [l for l in candidates if same_polarity(l)]
        if len(preferred) == 1:
            return preferred[0], "比用"
        candidates = preferred or candidates

        if shehai_method == "meng_zhong_first":
            candidates, hit = _meng_zhong_step(candidates)
            if hit is not None:
                return candidates[0], hit
            candidates, hit = _depth_step(candidates)
            if hit is not None:
                return candidates[0], hit
        else:
            candidates, hit = _depth_step(candidates)
            if hit is not None:
                return candidates[0], hit
            candidates, hit = _meng_zhong_step(candidates)
            if hit is not None:
                return candidates[0], hit

        # 返吟复等 (缀瑕): on 戊辰/戊戌 shift=6, L1=亥/戊(巳) and L2=巳/亥 tie on 孟 and harm=4;
        # 《大六壬720课》/《指南》/《粹言》 select L2=巳 (['巳','亥','巳']).
        if is_fanyin and {l["index"] for l in candidates} == {1, 2}:
            selected = next(l for l in candidates if l["index"] == 2)
        else:
            order = lessons[:2] + lessons[2:] if yang else lessons[2:] + lessons[:2]
            selected = next(l for l in order if l in candidates)
        return selected, "复等"

    thieves = _unique([l for l in lessons if l["upper_lower_relation"] == "下贼上"])
    killers = _unique([l for l in lessons if l["upper_lower_relation"] == "上克下"])
    candidates = thieves or killers

    if is_fuyin:
        stem_start = yang or day_stem in "乙癸"
        initial = gan_upper if stem_start else zhi_upper
        middle = PUNISHMENT[initial]
        if middle == initial:
            middle = zhi_upper if stem_start else gan_upper
        final = PUNISHMENT[middle]
        if final in (initial, middle):
            final = _shift(middle, 6)
        return (
            "伏吟",
            "自任" if yang else "自信",
            "伏吟循刑",
            [initial, middle, final],
            lessons[0 if stem_start else 2]["index"],
        )

    if candidates:
        selected_lesson, detail = choose(candidates)
        initial = selected_lesson["upper_branch"]
        style = "重审" if thieves else "元首"
        if detail == "贼克":
            detail = style
        elif detail in ("涉害", "见机", "察微", "复等"):
            style = "涉害"
        else:
            style, detail = "比用", "知一"
        if is_fanyin:
            return "返吟", detail, "返吟贼克", follow(initial), selected_lesson["index"]
        return (
            style,
            detail,
            "贼克循盘" if detail in ("重审", "元首") else detail,
            follow(initial),
            selected_lesson["index"],
        )

    if is_fanyin:
        horse = next(
            _shift(day_branch, offset + 6)
            for offset in (0, 4, 8)
            if _shift(day_branch, offset) in "寅巳申亥"
        )
        return "返吟", "无依", "返吟无依", [horse, zhi_upper, gan_upper], None

    is_bazhuan = day_stem + day_branch in {"甲寅", "庚申", "丁未", "己未"}
    if not is_bazhuan:
        remote = [
            l
            for l in lessons[1:]
            if _controls(branch_element_text(l["upper_branch"]), stem_element)
        ]
        detail = "蒿矢"
        if not remote:
            remote = [
                l
                for l in lessons[1:]
                if _controls(stem_element, branch_element_text(l["upper_branch"]))
            ]
            detail = "弹射"
        if remote:
            selected_lesson, _ = choose(remote)
            initial = selected_lesson["upper_branch"]
            return (
                "遥克",
                detail,
                "遥克" + detail,
                follow(initial),
                selected_lesson["index"],
            )

    count = len({l["upper_branch"] for l in lessons})
    if count == 4:
        if yang:
            return "昴星", "虎视", "昴星虎视", [sky["酉"], zhi_upper, gan_upper], None
        return (
            "昴星",
            "冬蛇掩目",
            "昴星冬蛇掩目",
            [earth["酉"], gan_upper, zhi_upper],
            None,
        )
    if count == 3:
        initial = (
            sky[STEM_HOUSES[HEAVENLY_STEMS[(HEAVENLY_STEMS.index(day_stem) + 5) % 10]]]
            if yang
            else _shift(day_branch, 4)
        )
        return "别责", "别责", "别责", [initial, gan_upper, gan_upper], None
    if is_bazhuan:
        initial = _shift(gan_upper, 2) if yang else _shift(zhi_yin, -2)
        return "八专", "八专", "八专", [initial, gan_upper, gan_upper], None
    raise ValueError("四课不满足九宗门取传条件")


def classify_transmission_pattern(
    *,
    day_ganzhi: str,
    style: str,
    detail: str,
    method: str,
    lessons: list[dict[str, Any]],
    transmissions: list[str],
    selected_lesson: int | None,
) -> dict[str, Any]:
    thieves = [r["index"] for r in lessons if r["upper_lower_relation"] == "下贼上"]
    killers = [r["index"] for r in lessons if r["upper_lower_relation"] == "上克下"]
    initial, middle, final = transmissions
    yang = day_ganzhi[0] in "甲丙戊庚壬"
    initial_self = PUNISHMENT[initial] == initial
    closing_punishment = PUNISHMENT[middle] in (initial, middle)
    final_detail = detail
    final_method = method

    def direct_label() -> str:
        if detail in ("重审", "元首"):
            return (
                "始入"
                if len(thieves) == 1 and not killers
                else "重审" if thieves else "元首"
            )
        if detail == "知一":
            return "比用" if thieves else "知一"
        return "缀瑕" if detail == "复等" else detail

    if style == "伏吟":
        if day_ganzhi[0] == "癸":
            labels = ["不虞", "元首"]
        elif initial_self or closing_punishment:
            labels = ["杜传"] + (["始入"] if day_ganzhi[0] == "乙" else [])
        else:
            labels = ["自任" if yang else "自信"]
        final_detail = labels[0]
        reason = f"伏吟初{initial}中{middle}末{final}，初传自刑{'是' if initial_self else '否'}，中传之刑回初/中{'是' if closing_punishment else '否'}。"
    elif style == "返吟":
        if thieves or killers:
            subordinate = direct_label()
            labels = ["无依", subordinate]
            final_detail = detail if detail == "复等" else subordinate
            reason = f"返吟见贼克（下贼上{thieves}、上克下{killers}），取第{selected_lesson}课{initial}发用。"
        else:
            secondary = (
                "八专" if day_ganzhi in ("甲寅", "庚申", "丁未", "己未") else "井栏射"
            )
            labels = ["无亲", secondary]
            final_detail, final_method = "无亲", "返吟无亲"
            reason = f"返吟四课无贼克，从日支驿马{initial}发用。"
    elif style in ("重审", "元首", "比用", "涉害"):
        labels = [direct_label()]
        final_detail = detail if detail == "复等" else labels[0]
        if style == "比用":
            final_method = labels[0]
        reason = f"下贼上{thieves}、上克下{killers}，选第{selected_lesson}课{initial}发用（{labels[0]}）。"
    elif style == "八专":
        labels = ["八专"] + (["独足"] if len(set(transmissions)) == 1 else [])
        final_detail = "独足" if len(labels) == 2 else "八专"
        reason = f"八专三传{initial}{middle}{final}。"
    else:
        labels = [detail]
        reason = f"按{style}{detail}取三传{initial}{middle}{final}。"

    # Classical 64-lesson / 毕法赋 structural labels derived solely from board symbols.
    extra_names: list[str] = []
    idx = [EARTHLY_BRANCHES.index(b) for b in transmissions]
    steps = [(b - a) % 12 for a, b in zip(idx, idx[1:])]
    if steps[0] == steps[1]:
        if steps[0] == 1:
            extra_names.append("进连茹")
        elif steps[0] == 11:
            extra_names.append("退连茹")
        elif steps[0] in (2, 10):
            extra_names.append("间传")
    for members, elem in TRINES:
        if set(transmissions) == set(members):
            extra_names.append(f"{TRINE_NAMES[elem]}局")
            break
    for _, name, order in ORDERED_PATTERNS:
        if transmissions == list(order):
            extra_names.append(name)
    if all(b in "寅巳申亥" for b in transmissions):
        extra_names.append("玄胎")
    if all(b in "子午卯酉" for b in transmissions):
        extra_names.append("四仲")
    if all(b in "辰戌丑未" for b in transmissions):
        extra_names.append("稼穑")
    if initial in ("辰", "戌") and lessons[0]["lower_branch"] in ("辰", "戌"):
        extra_names.append("斩关")
    if len(thieves) >= 3 or len(killers) >= 3:
        extra_names.append("度厄")
    dun = xun_dun_stems(day_ganzhi)
    dun_set = {dun.get(b) for b in transmissions if b in dun}
    for wonder in ("甲戊庚", "乙丙丁", "壬癸辛"):
        if set(wonder) <= dun_set:
            extra_names.append("三奇")
            break
    if xun_head_for_ganzhi(day_ganzhi)[1] in transmissions:
        extra_names.append("六仪")
    empty = set(kongwang_for_ganzhi(day_ganzhi)[:2])
    if all(b in empty for b in transmissions):
        extra_names.append("全空")
    elif initial in empty and middle in empty:
        extra_names.append("初中空")
    if (
        len(lessons) == 4
        and len({l["upper_branch"] for l in lessons}) <= 2
        and style == "别责"
    ):
        extra_names.append("芜淫")
    if set(transmissions) == {"酉"}:
        extra_names.append("一体")

    note = liuren_annotation_note(day_ganzhi, lessons[0]["upper_branch"])
    return {
        "ruleset_id": "tanyuan_jiuzong_names_v1",
        "source_section": "九宗门 / 六十四课格",
        "labels": labels,
        "named_patterns": extra_names,
        "detail": final_detail,
        "transmission_method": final_method,
        "lower_thief_lessons": thieves,
        "upper_killer_lessons": killers,
        "initial_self_punishment": initial_self if style == "伏吟" else None,
        "closing_punishment": closing_punishment if style == "伏吟" else None,
        "selected_lesson": selected_lesson,
        "basis": reason,
        "source_note": note,
    }


def ordered_transmission_patterns(branches: list[str]) -> dict[str, Any]:
    if (
        not isinstance(branches, list)
        or len(branches) != 3
        or any(
            not isinstance(b, str) or len(b) != 1 or b not in EARTHLY_BRANCHES
            for b in branches
        )
    ):
        raise ValueError("传序课体需要按初中末排列的三个有效地支")
    evaluations = [
        dict(
            id=key,
            name=name,
            required_branches=list(order),
            matched=branches == list(order),
        )
        for key, name, order in ORDERED_PATTERNS
    ]
    return dict(
        ruleset_id="tanyuan_ordered_transmission_patterns_v1",
        source_title="大六壬探原·课体纲要",
        branches=list(branches),
        evaluations=evaluations,
        matched_ids=[r["id"] for r in evaluations if r["matched"]],
        complete_classical_conformance=False,
    )


def transmission_progression(day_ganzhi: str, branches: list[str]) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("三传进退需要有效日干支")
    if (
        not isinstance(branches, list)
        or len(branches) != 3
        or any(
            not isinstance(b, str) or len(b) != 1 or b not in EARTHLY_BRANCHES
            for b in branches
        )
    ):
        raise ValueError("三传进退需要按初中末排列的三个地支")
    indices = [EARTHLY_BRANCHES.index(b) for b in branches]
    steps = [(b - a) % 12 for a, b in zip(indices, indices[1:])]
    step = steps[0] if steps[0] == steps[1] else None
    kind = "连茹" if step in (1, 11) else "间断" if step in (2, 10) else None
    direction = ("进" if step in (1, 2) else "退") if kind else None
    empty = kongwang_for_ganzhi(day_ganzhi)[:2]
    flags = [b in empty for b in branches]
    reading = None
    conditional = direction
    if kind == "连茹":
        if flags[0]:
            reading, conditional = "初空进退受阻", None
        elif flags[2]:
            reading = "末空以退论" if direction == "进" else "末空以进言"
            conditional = "退" if direction == "进" else "进"
        else:
            reading = "按支序进读" if direction == "进" else "按支序退读"
    elif kind == "间断":
        if any(flags):
            reading, conditional = "见空不拘原进退说", None
        else:
            reading = "前进多阻" if direction == "进" else "后退有妨"
    return dict(
        ruleset_id="tanyuan_transmission_progression_v1",
        source_title="大六壬探原·三传连茹",
        day_ganzhi=day_ganzhi,
        branches=list(branches),
        steps=steps,
        kind=kind,
        structure_matched=kind is not None,
        sequence_direction=direction,
        empty_branches=list(empty),
        branch_xun_kong=flags,
        raw_branch_empty_conditional_reading=reading,
        raw_branch_empty_conditional_direction=conditional,
        effective_direction=None,
        comprehensive_judgement=None,
        complete_classical_conformance=False,
    )


def pair_layout_necessity(day_stem: str, stage: str, god: str) -> dict[str, Any]:
    cycle = life_stage_cycle(day_stem)
    if stage not in cycle.values() or god not in GUI_REN_SEQUENCE:
        raise ValueError("配将必要条件需要有效十二运与天将")
    required_branch = next(b for b, s in cycle.items() if s == stage)
    rank = GUI_REN_SEQUENCE.index(god)
    candidates = set()
    for profile in ("liuren_common_v1", "tanyuan_xieji_v1"):
        for daylight in (False, True):
            start = EARTHLY_BRANCHES.index(noble_start(day_stem, daylight, profile))
            for direction in (1, -1):
                candidates.add(EARTHLY_BRANCHES[(start + direction * rank) % 12])
    return dict(
        required_stage_branch=required_branch,
        possible_god_branches=[b for b in EARTHLY_BRANCHES if b in candidates],
        compatible_in_any_supported_noble_layout=required_branch in candidates,
    )


def course_conditions(day_ganzhi: str, transmissions: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(day_ganzhi, str) or day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("课体条件需要有效占日干支")
    if not isinstance(transmissions, dict):
        raise ValueError("课体条件需要实际三传")
    rows: list[dict[str, Any]] = []
    for position in ("initial", "middle", "final"):
        r = transmissions.get(position)
        if (
            not isinstance(r, dict)
            or r.get("branch") not in EARTHLY_BRANCHES
            or r.get("earth_branch") not in EARTHLY_BRANCHES
            or r.get("god") not in GUI_REN_SEQUENCE
        ):
            raise ValueError("课体条件需要三传支神、承座及天将")
        rows.append(r)
    branches = [r["branch"] for r in rows]
    initial = rows[0]
    stage = life_stage_cycle(day_ganzhi[0])[branches[0]]
    head = xun_head_for_ganzhi(day_ganzhi)[1]
    tail = EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(head) + 9) % 12]
    stage_rows = [
        dict(
            id=i,
            name=n,
            required_stage=s,
            required_god=g,
            stage_matches=stage == s,
            god_matches=initial["god"] == g,
            matched=stage == s and initial["god"] == g,
            **pair_layout_necessity(day_ganzhi[0], s, g),
        )
        for i, n, s, g in STAGE_PAIRS
    ]
    god_rows = [
        dict(id=i, name=n, required_god=g, matched=initial["god"] == g)
        for i, n, g in GOD_PAIRS
    ]
    structures = [
        dict(
            id=i,
            name=name,
            condition=condition,
            checks=[dict(id=k, matched=v) for k, v in checks],
            matched=all(v for _, v in checks),
        )
        for i, name, condition, checks in (
            (
                "B01",
                "斩关",
                "辰戌临干枝发用",
                [
                    ("initial_is_chen_xu", branches[0] in ("辰", "戌")),
                    (
                        "seat_is_day_stem_house_or_day_branch",
                        initial["earth_branch"]
                        in (STEM_HOUSES[day_ganzhi[0]], day_ganzhi[1]),
                    ),
                ],
            ),
            (
                "B02",
                "一体",
                "三传酉酉酉",
                [("ordered_triple_is_you_you_you", branches == ["酉"] * 3)],
            ),
            (
                "B03",
                "始终",
                "初传属旬首末传属旬尾",
                [
                    ("initial_is_day_xun_head", branches[0] == head),
                    ("final_is_same_day_xun_tail", branches[2] == tail),
                ],
            ),
        )
    ]
    return dict(
        ruleset_id="tanyuan_course_conditions_v1",
        source_title="大六壬探原·课体纲要",
        day_ganzhi=day_ganzhi,
        initial_branch=branches[0],
        initial_earth_branch=initial["earth_branch"],
        initial_god=initial["god"],
        initial_day_stem_stage=stage,
        day_xun_head=head,
        day_xun_tail=tail,
        transmission_branches=branches,
        stage_god_pairs=stage_rows,
        god_pairs=god_rows,
        structural_clauses=structures,
        matched_ids=[
            r["id"] for r in stage_rows + god_rows + structures if r["matched"]
        ],
        comprehensive_judgement=None,
        complete_classical_conformance=False,
    )


def phase_relation(left: str, right: str) -> str:
    if left == right:
        return "比和"
    if ELEMENT_GENERATES[left] == right:
        return "生"
    if ELEMENT_GENERATES[right] == left:
        return "受生"
    return "克" if ELEMENT_CONTROLS[left] == right else "受克"


def transmission_relations(
    *,
    day_ganzhi: str,
    lessons: list[dict[str, Any]],
    transmissions: dict[str, Any],
    month_branch: str | None = None,
) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("三传关系需要有效日干支")
    day = stem_element_text(day_ganzhi[0])
    empty = kongwang_for_ganzhi(day_ganzhi)[:2]
    stages = life_stage_cycle(day_ganzhi[0])
    rows = []
    for position in ("initial", "middle", "final"):
        item = transmissions[position]
        branch, god, earth = item["branch"], item["god"], item["earth_branch"]
        if (
            branch not in EARTHLY_BRANCHES
            or earth not in EARTHLY_BRANCHES
            or god not in GOD_ELEMENTS
        ):
            raise ValueError("三传关系的支神、地盘或天将无效")
        element, god_element = branch_element_text(branch), GOD_ELEMENTS[god]
        relation = phase_relation(god_element, element)
        rows.append(
            dict(
                position=position,
                branch=branch,
                element=element,
                god=god,
                god_element=god_element,
                god_to_spirit=relation,
                war=(
                    "外战"
                    if relation == "克"
                    else "内战" if relation == "受克" else None
                ),
                earth_branch=earth,
                earth_element=branch_element_text(earth),
                spirit_to_seat=phase_relation(element, branch_element_text(earth)),
                day_relation=liuqin_against_day(day, element),
                day_stem_life_stage=stages[branch],
                xun_kong=branch in empty,
            )
        )
    a, b, c = rows
    upper = {int(l["index"]): l["upper_branch"] for l in lessons}
    if set(upper) != {1, 2, 3, 4} or len(lessons) != 4:
        raise ValueError("三传关系需要完整且不重复的四课")
    branches = [r["branch"] for r in rows]
    flags = {
        "birth_to_tomb": a["day_stem_life_stage"] == "长生"
        and c["day_stem_life_stage"] == "墓",
        "tomb_to_birth": a["day_stem_life_stage"] == "墓"
        and c["day_stem_life_stage"] == "长生",
        "final_controls_initial": ELEMENT_CONTROLS[c["element"]] == a["element"],
        "control_chain": ELEMENT_CONTROLS[day] == a["element"]
        and ELEMENT_CONTROLS[a["element"]] == b["element"]
        and ELEMENT_CONTROLS[b["element"]] == c["element"],
        "all_branch_empty": all(r["xun_kong"] for r in rows),
        "initial_middle_empty": a["xun_kong"] and b["xun_kong"] and not c["xun_kong"],
        "middle_final_empty": b["xun_kong"] and c["xun_kong"] and not a["xun_kong"],
        "chao_zhi": a["branch"] == upper[1] and c["branch"] == upper[3],
        "chao_ri": a["branch"] == upper[3] and c["branch"] == upper[1],
    }
    trines = []
    for members, element in TRINES:
        seen = [v for v in members if v in branches]
        complete = len(seen) == 3
        trines.append(
            dict(
                branches=list(members),
                present_branches=seen,
                missing_branches=[v for v in members if v not in branches],
                nominal_element=element,
                branches_complete=complete,
                nominal_day_relation=(
                    liuqin_against_day(day, element) if complete else None
                ),
                transformation_confirmed=None,
            )
        )
        if month_branch is not None:
            trines[-1]["nominal_seasonal_evidence"] = (
                nominal_seasonal_evidence(month_branch, element) if complete else None
            )
    return dict(
        ruleset_id="liuren_tanyuan_transmission_relations_v1",
        day_ganzhi=day_ganzhi,
        day_element=day,
        rows=rows,
        rules=[dict(id=i, name=n, matched=flags[i]) for i, n in RULE_NAMES],
        matched_rule_ids=[i for i, _ in RULE_NAMES if flags[i]],
        origin_destinations_coincide=upper[1] == upper[3],
        trines=trines,
        named_structures=ordered_transmission_patterns(branches),
        course_conditions=course_conditions(day_ganzhi, transmissions),
        all_transmissions_in_lesson_uppers=set(branches) <= set(upper.values()),
        all_transmissions_in_day_branch_uppers=set(branches) <= {upper[1], upper[3]},
        two_branch_empty=sum(r["xun_kong"] for r in rows) == 2,
        solid_transmission_has_sky_god=any(
            not r["xun_kong"] and r["god"] == "天空" for r in rows
        ),
        any_transmission_has_sky_god=any(r["god"] == "天空" for r in rows),
        comprehensive_judgement=None,
        complete_classical_conformance=False,
    )
