"""Liuyao cast and rod-divination output contracts."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import Hexagram, MeihuaSeed


class SixyaoLine(PartialOutput):
    changed_branch: str | None = None
    changed_liuqin: str | None = None
    is_fuyin_line: bool | None = None
    branch: str | None = None
    change: bool | None = None
    element: str | None = None
    god: str | None = None
    liuqin: str | None = None
    liushen: str | None = None
    name: str | None = None
    position: int | None = None
    shi_ying: str | None = None
    value: int | None = None


class SixyaoTimeRuleset(PartialOutput):
    ruleset_id: str | None = None
    year_boundary: str | None = None
    source_url: str | None = None
    seed: MeihuaSeed | None = None


class SixyaoCoinToss(PartialOutput):
    position: int | None = None
    name: str | None = None
    sum: int | None = None
    yao: str | None = None
    symbol: str | None = None
    moving: bool | None = None


class SixyaoCast(PartialOutput):
    method: str | None = None
    source: str | None = None
    seed: int | None = None
    coin_source: str | None = None
    tosses: list[SixyaoCoinToss] | None = None
    time_ruleset: SixyaoTimeRuleset | None = None


class SixyaoHexagramInfo(PartialOutput):
    changed_palace: str | None = None
    changed_palace_element: str | None = None
    changed_position: str | None = None
    current_palace: str | None = None
    current_palace_element: str | None = None
    current_position: str | None = None
    shi_line: int | None = None
    ying_line: int | None = None


class SixyaoDescription(PartialOutput):
    code: str | None = None
    name: str | None = None
    卦辞: str | None = None
    象曰: str | None = None
    raw: Hexagram | None = None


class SixyaoFlags(PartialOutput):
    liuchong_base: bool | None = None
    liuchong_changed: bool | None = None
    liuhe_base: bool | None = None
    liuhe_changed: bool | None = None


class Tongshefa(PartialOutput):
    baseLeft: Hexagram | None = None
    baseRight: Hexagram | None = None
    mutualLeft: Hexagram | None = None
    mutualRight: Hexagram | None = None
    relation: str | None = None
    main_relation: str | None = None
    left_elem: str | None = None
    right_elem: str | None = None
