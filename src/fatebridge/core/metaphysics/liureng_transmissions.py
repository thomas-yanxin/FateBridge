"""Nine-method Liu Ren transmissions over an already resolved sky board.

Calendar and 贵人 conventions belong to the caller. Positioning the first
lesson at a stem's 寄宫 does not change that stem's element. Candidates are
deduplicated by upper god before 比用/涉害; 六合/六害 are not transmission
methods. The formulas are checked against independent daliurenpython classes
and textbook-style special-board cases (see the correctness audit).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ...utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
from .common import ELEMENT_CONTROLS, branch_element_text, stem_element_text

STEM_HOUSES = dict(zip(HEAVENLY_STEMS, "寅辰巳未巳未申戌亥丑"))
PUNISHMENT = dict(zip("寅巳申丑戌未子卯辰午酉亥", "巳申寅戌未丑卯子辰午酉亥"))


def _shift(branch: str, offset: int) -> str:
    return EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(branch) + offset) % 12]


def _controls(left: str, right: str) -> bool:
    return ELEMENT_CONTROLS[left] == right


def _unique(lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_upper: Dict[str, Dict[str, Any]] = {}
    for lesson in lessons:
        by_upper.setdefault(lesson["upper_branch"], lesson)
    return list(by_upper.values())


def harm_walk(
    lesson: Dict[str, Any], day_stem: str, sky: Dict[str, str]
) -> Dict[str, Any]:
    """Expose the existing 正五行/寄干 walk without adopting another endpoint.

    The terminal home is excluded by the current algorithm. Including its
    lodged stem changes ten counts and one fine name across the 720 boards;
    the printed aggregate conflict is preserved rather than scored away.
    """
    earth = {upper: lower for lower, upper in sky.items()}
    upper = lesson["upper_branch"]
    element = branch_element_text(upper)
    lower_element = (
        stem_element_text(day_stem)
        if lesson["index"] == 1
        else branch_element_text(lesson["lower_branch"])
    )
    thief = _controls(lower_element, element)
    steps: List[Dict[str, Any]] = []
    position = earth[upper]
    while position != upper:
        contributions: List[Dict[str, Any]] = [
            {
                "kind": "branch",
                "token": position,
                "element": branch_element_text(position),
            }
        ] + [
            {"kind": "lodged_stem", "token": stem, "element": stem_element_text(stem)}
            for stem, house in STEM_HOUSES.items()
            if house == position
        ]
        for item in contributions:
            item["counts_as_harm"] = (
                _controls(item["element"], element)
                if thief
                else _controls(element, item["element"])
            )
        steps.append({"earth_branch": position, "contributions": contributions})
        position = _shift(position, 1)
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
        "terminal_home_counted": False,
    }


def select_transmissions(
    day_stem: str,
    day_branch: str,
    sky: Dict[str, str],
    lessons: List[Dict[str, Any]],
    *,
    trace: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, str, str, List[str], Optional[int]]:
    """Return styles, derivation, three gods, and the actual source lesson.

    The source index is None when the initial god is derived outside the
    four lessons. Duplicate upper gods do not identify a source lesson.
    """
    earth = {upper: lower for lower, upper in sky.items()}
    yang = HEAVENLY_STEMS.index(day_stem) % 2 == 0
    stem_element = stem_element_text(day_stem)
    gan_upper, _, zhi_upper, zhi_yin = (l["upper_branch"] for l in lessons)

    def follow(initial: str) -> List[str]:
        middle = sky[initial]
        return [initial, middle, sky[middle]]

    def same_polarity(lesson: Dict[str, Any]) -> bool:
        return (EARTHLY_BRANCHES.index(lesson["upper_branch"]) % 2 == 0) == yang

    def choose(candidates: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], str]:
        candidates = _unique(candidates)
        if trace is not None:
            trace.append(
                {
                    "rule_id": "liuren.direct_or_remote_candidates",
                    "source_section": "贼克 / 比用 / 遥克",
                    "result": {
                        "lessons": [l["index"] for l in candidates],
                        "uppers": [l["upper_branch"] for l in candidates],
                    },
                }
            )
        if len(candidates) == 1:
            return candidates[0], "贼克"
        preferred = [l for l in candidates if same_polarity(l)]
        if trace is not None:
            trace.append(
                {
                    "rule_id": "liuren.polarity",
                    "source_section": "比用法",
                    "result": {"preferred_lessons": [l["index"] for l in preferred]},
                }
            )
        if len(preferred) == 1:
            return preferred[0], "比用"
        candidates = preferred or candidates

        walks = [harm_walk(lesson, day_stem, sky) for lesson in candidates]
        depths = [
            (lesson, walk["harm_count"]) for lesson, walk in zip(candidates, walks)
        ]
        if trace is not None:
            trace.append(
                {
                    "rule_id": "liuren.harm_paths",
                    "source_section": "探原·涉害·正五行及十干寄宫",
                    "result": {
                        "candidates": walks,
                        "scope": "当前算法逐站列正五行及十干寄宫，不用地支藏干；终本家寄干异法未据单条表注裁定，不代表全书认证。",
                    },
                }
            )
            trace.append(
                {
                    "rule_id": "liuren.harm_depth",
                    "source_section": "涉害法",
                    "result": {str(l["index"]): value for l, value in depths},
                }
            )
        deepest = max(value for _, value in depths)
        candidates = [l for l, value in depths if value == deepest]
        if len(candidates) == 1:
            return candidates[0], "涉害"
        # When depths tie, prefer a god resting on 孟, then 仲. Count the
        # earthly position, not the upper god's own branch.
        for group, detail in (("寅巳申亥", "见机"), ("子卯午酉", "察微")):
            match = [l for l in candidates if earth[l["upper_branch"]] in group]
            if len(match) == 1:
                return match[0], detail
            if match:
                candidates = match
                break
        # More than one 孟 must not silently become the first 见机. In the
        # attested 戊辰/戊戌 examples the remaining tie is 复等 (缀瑕).
        order = lessons[:2] + lessons[2:] if yang else lessons[2:] + lessons[:2]
        selected = next(l for l in order if l in candidates)
        if trace is not None:
            trace.append(
                {
                    "rule_id": "liuren.harm_tie",
                    "source_section": "涉害法·复等（缀瑕）",
                    "result": {
                        "remaining_lessons": [l["index"] for l in candidates],
                        "selected_lesson": selected["index"],
                        "day_polarity": "阳" if yang else "阴",
                    },
                }
            )
        return selected, "复等"

    thieves = _unique([l for l in lessons if l["upper_lower_relation"] == "下贼上"])
    killers = _unique([l for l in lessons if l["upper_lower_relation"] == "上克下"])
    candidates = thieves or killers
    is_fuyin = zhi_upper == day_branch
    is_fanyin = zhi_upper == _shift(day_branch, 6)

    if is_fuyin:
        # 乙/癸 first lessons have a genuine upper/lower clash even though
        # the sky board is stationary; these days also start at the stem god.
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
