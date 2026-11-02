"""Projection-aware same-board constraints for 类神之阴."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import StrictBool, model_validator

from .output_base import PartialOutput
from .output_liuren_branches import compare_present_branches
from .output_liuren_emptiness import Branch
from .output_liuren_seasonal import God, Power


class LiurenGodYinRow(PartialOutput):
    god: Optional[God] = None
    riding_branch: Optional[Branch] = None
    riding_earth_branch: Optional[Branch] = None
    yin_branch: Optional[Branch] = None
    yin_earth_branch: Optional[Branch] = None
    derivation: Optional[Literal["opposite_noble_start", "upper_of_riding_branch"]] = (
        None
    )
    lesson_indices: Optional[List[int]] = None
    transmission_positions: Optional[List[Literal["initial", "middle", "final"]]] = None
    in_natal_upper: Optional[StrictBool] = None
    in_annual_upper: Optional[StrictBool] = None
    appears_in_roles: Optional[StrictBool] = None
    yin_branch_xun_kong: Optional[StrictBool] = None
    nominal_seasonal_power: Optional[Power] = None
    nominal_wang_xiang: Optional[StrictBool] = None
    effective_emptiness: None = None
    ri_chen_de_he_sheng_adjudicated: None = None
    comprehensive_eligibility: None = None


class LiurenGodYin(PartialOutput):
    ruleset_id: Optional[Literal["tanyuan_category_spirit_yin_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[int]] = None
    day_ganzhi: Optional[str] = None
    month_branch: Optional[Branch] = None
    is_diurnal: Optional[StrictBool] = None
    guiren_profile: Optional[Literal["liuren_common_v1", "tanyuan_xieji_v1"]] = None
    sky_by_earth: Optional[Dict[Branch, Branch]] = None
    god_by_sky: Optional[Dict[Branch, God]] = None
    lesson_uppers: Optional[List[Branch]] = None
    transmission_branches: Optional[List[Branch]] = None
    year_fate_uppers: Optional[Dict[Literal["natal", "annual"], Optional[Branch]]] = (
        None
    )
    seasonal_profile: Optional[Literal["declared_seasonal_month_branches_v1"]] = None
    rows: Optional[List[LiurenGodYinRow]] = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def no_false_conformance(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and value.get("complete_classical_conformance") is not None
            and value["complete_classical_conformance"] is not False
        ):
            raise ValueError("类神阴神查法不认证完整原典")
        return value

    @model_validator(mode="after")
    def values_follow_this_context(self) -> "LiurenGodYin":
        value = self.model_dump(exclude_unset=True)
        if self.rows is not None and len(self.rows) != 12:
            raise ValueError("类神阴神须保留十二天将队列")
        if self.lesson_uppers is not None and len(self.lesson_uppers) != 4:
            raise ValueError("类神阴神四课依据需要四个位置")
        if (
            self.transmission_branches is not None
            and len(self.transmission_branches) != 3
        ):
            raise ValueError("类神阴神三传依据需要三个位置")
        if context_available(value):
            compare_present_branches(value, rebuild(value))
        return self


INPUTS = (
    "day_ganzhi",
    "month_branch",
    "is_diurnal",
    "guiren_profile",
    "sky_by_earth",
    "god_by_sky",
    "lesson_uppers",
    "transmission_branches",
    "year_fate_uppers",
)


def context_available(value: dict[str, Any]) -> bool:
    from .metaphysics.common import EARTHLY_BRANCHES

    return (
        all(key in value and value[key] is not None for key in INPUTS)
        and set(value["sky_by_earth"]) == set(EARTHLY_BRANCHES)
        and set(value["god_by_sky"]) == set(EARTHLY_BRANCHES)
        and set(value["year_fate_uppers"]) == {"natal", "annual"}
    )


def rebuild(value: dict[str, Any]) -> dict[str, Any]:
    from .metaphysics.liureng_god_yin import god_yin_spirits

    return god_yin_spirits(**{key: value[key] for key in INPUTS})


def get(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def align_god_yin(board: Any, pillars: Any = None, runyear: Any = None) -> None:
    value = get(board, "god_yin")
    if value is None:
        return
    if pillars is not None:
        stem, branch = get(get(pillars, "day"), "stem"), get(
            get(pillars, "day"), "branch"
        )
        if stem and branch and get(value, "day_ganzhi") not in (None, stem + branch):
            raise ValueError("类神阴神与同次日干支不一致")
        month = get(get(pillars, "month"), "branch")
        if month and get(value, "month_branch") not in (None, month):
            raise ValueError("类神阴神季节条件与同次月建不一致")
    meta = get(board, "meta")
    for own, other in [
        ("guiren_profile", "guiren_profile"),
        ("is_diurnal", "is_diurnal"),
    ]:
        actual, expected = get(value, own), get(meta, other)
        if actual is not None and expected is not None and actual != expected:
            raise ValueError("类神阴神与所选贵人配置或昼夜不一致")
    sky, gods = get(value, "sky_by_earth"), get(value, "god_by_sky")
    for row in get(board, "twelve_board") or []:
        earth, upper, god = (get(row, k) for k in ["earth_branch", "sky_branch", "god"])
        if (
            sky is not None
            and earth in sky
            and upper is not None
            and sky[earth] != upper
        ):
            raise ValueError("类神阴神与本课天地盘不一致")
        if (
            gods is not None
            and upper in gods
            and god is not None
            and gods[upper] != god
        ):
            raise ValueError("类神阴神与本课天将盘不一致")
    lessons = get(value, "lesson_uppers")
    if lessons is not None:
        for row in get(board, "four_lessons") or []:
            index, upper = get(row, "index"), get(row, "upper_branch")
            if index is not None and upper is not None and lessons[index - 1] != upper:
                raise ValueError("类神阴神与本课四课不一致")
    transmissions = get(value, "transmission_branches")
    if transmissions is not None:
        for i, p in enumerate(["initial", "middle", "final"]):
            upper = get(get(get(board, "three_transmissions"), p), "branch")
            if upper is not None and upper != transmissions[i]:
                raise ValueError("类神阴神与本课三传不一致")
    if runyear is not None and get(value, "year_fate_uppers") is not None:
        roles = get(value, "year_fate_uppers")
        for role in ["natal", "annual"]:
            if role not in roles:
                continue
            item = get(get(runyear, "year_fate"), role)
            if item is None:
                continue
            expected = get(item, "sky_branch")
            present = (
                "sky_branch" in item
                if isinstance(item, dict)
                else "sky_branch" in getattr(item, "model_fields_set", set())
            )
            if not present:
                continue
            if roles.get(role) != expected:
                raise ValueError("类神阴神与同次年命上神不一致")


def require_complete_god_yin(board: Any) -> None:
    from .metaphysics.liureng_god_yin import RULE_ID, god_yin_trace

    value = get(board, "god_yin")
    if not isinstance(value, dict) or not context_available(value):
        raise ValueError("完整六壬须保留类神阴神原始依据")
    expected = rebuild(value)
    if value != expected:
        raise ValueError("完整六壬类神阴神须保留全部可空条件及十二天将")
    align_god_yin(board)
    traces = [t for t in get(board, "rule_trace") or [] if get(t, "rule_id") == RULE_ID]
    if len(traces) != 1 or traces[0] != god_yin_trace(expected):
        raise ValueError("完整六壬须保留唯一且一致的类神阴神轨迹")
