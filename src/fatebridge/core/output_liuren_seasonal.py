"""Projection-aware anchors for the same-board seasonal condition table."""

from typing import Any, Dict, List, Literal, Optional, cast

from pydantic import StrictBool, StrictInt, model_validator

from .output_base import PartialOutput
from .output_liuren_branches import compare_present_branches
from .output_liuren_emptiness import Branch

Element = Literal["木", "火", "土", "金", "水"]
Power = Literal["旺", "相", "休", "囚", "死"]
God = Literal[
    "贵人",
    "螣蛇",
    "朱雀",
    "六合",
    "勾陈",
    "青龙",
    "天空",
    "白虎",
    "太常",
    "玄武",
    "太阴",
    "天后",
]


class LiurenSeasonalRow(PartialOutput):
    earth_branch: Branch
    sky_branch: Branch
    sky_element: Element
    sky_seasonal_power: Power
    god: God
    god_element: Element
    god_seasonal_power: Power
    earth_element: Element
    earth_seasonal_power: Power
    sky_xun_kong: StrictBool
    sky_empty_seasonal_condition: Optional[Literal["真空条件", "半空条件"]]
    effective_empty_class: None

    @model_validator(mode="after")
    def inherent_and_raw_facts(self) -> "LiurenSeasonalRow":
        from .metaphysics.common import branch_element_text
        from .metaphysics.liureng_seasonal import GOD_ELEMENTS, empty_condition

        if (
            self.sky_element != branch_element_text(self.sky_branch)
            or self.earth_element != branch_element_text(self.earth_branch)
            or self.god_element != GOD_ELEMENTS[self.god]
        ):
            raise ValueError("季节条件的支神、天将或地盘固有五行不符")
        if self.sky_empty_seasonal_condition != empty_condition(
            self.sky_seasonal_power, self.sky_xun_kong
        ):
            raise ValueError("真半条件必须按本支五态及本空，不能套天将或日干")
        return self


class LiurenSeasonalEvidence(PartialOutput):
    ruleset_id: Optional[Literal["tanyuan_seasonal_month_conditions_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[StrictInt]] = None
    month_partition_profile: Optional[
        Literal["declared_seasonal_month_branches_v1"]
    ] = None
    month_partition_basis: Optional[str] = None
    day_ganzhi: Optional[str] = None
    month_branch: Optional[Branch] = None
    season_partition: Optional[Literal["春", "夏", "秋", "冬", "季月"]] = None
    phase_powers: Optional[Dict[Element, Power]] = None
    day_stem_element: Optional[Element] = None
    day_stem_seasonal_power: Optional[Power] = None
    empty_branches: Optional[List[Branch]] = None
    rows: Optional[List[LiurenSeasonalRow]] = None
    raw_true_condition_branches: Optional[List[Branch]] = None
    raw_half_condition_branches: Optional[List[Branch]] = None
    effective_empty_classification: None = None
    effective_true_half_adjudicated: Optional[Literal[False]] = None
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def strict_unresolved_flags(cls, value: Any) -> Any:
        if isinstance(value, dict):
            for key in [
                "effective_true_half_adjudicated",
                "complete_classical_conformance",
            ]:
                if value.get(key) is not None and value[key] is not False:
                    raise ValueError("季节条件不认证综合真半或全书，只允许布尔false")
        return value

    @model_validator(mode="after")
    def same_seasonal_facts(self) -> "LiurenSeasonalEvidence":
        from .metaphysics.common import (
            SEXAGENARY_INDEX,
            kongwang_for_ganzhi,
            stem_element_text,
        )
        from .metaphysics.liureng_seasonal import (
            BRANCHES,
            MONTH_PARTITION,
            POWERS,
            seasonal_evidence,
            seasonal_metadata,
        )

        present = self.model_dump(exclude_unset=True)
        for key, expected in seasonal_metadata().items():
            if key in present:
                compare_present_branches(present[key], expected)
        partition = (
            MONTH_PARTITION[self.month_branch]
            if self.month_branch is not None
            else self.season_partition
        )
        if (
            self.month_branch is not None
            and self.season_partition is not None
            and partition != self.season_partition
        ):
            raise ValueError("季节分组与本次月建支不符")
        known_powers = POWERS[partition] if partition is not None else self.phase_powers
        if self.phase_powers is not None and known_powers is not None:
            compare_present_branches(self.phase_powers, known_powers)
        day_element = self.day_stem_element
        if self.day_ganzhi is not None:
            if self.day_ganzhi not in SEXAGENARY_INDEX:
                raise ValueError("季节条件日干支无效")
            element = stem_element_text(self.day_ganzhi[0])
            day_element = cast(Element, element)
            if self.day_stem_element is not None and self.day_stem_element != element:
                raise ValueError("季节条件日干五行不符")
            if self.empty_branches is not None and self.empty_branches != list(
                kongwang_for_ganzhi(self.day_ganzhi)[:2]
            ):
                raise ValueError("季节条件旬空两支不符")
        if (
            day_element is not None
            and known_powers is not None
            and day_element in known_powers
            and self.day_stem_seasonal_power is not None
            and self.day_stem_seasonal_power != known_powers[day_element]
        ):
            raise ValueError("日干季节五态与同时返回的五态表不符")
        if self.empty_branches is not None and len(self.empty_branches) != 2:
            raise ValueError("季节条件须保留两支本空")
        if self.rows is not None:
            if (
                [r.earth_branch for r in self.rows] != list(BRANCHES)
                or len({r.sky_branch for r in self.rows}) != 12
                or len({r.god for r in self.rows}) != 12
            ):
                raise ValueError("季节条件须保留十二地盘顺序与完整支神天将")
            for row in self.rows:
                if known_powers is not None:
                    for element, power in [
                        (row.sky_element, row.sky_seasonal_power),
                        (row.god_element, row.god_seasonal_power),
                        (row.earth_element, row.earth_seasonal_power),
                    ]:
                        if element in known_powers and power != known_powers[element]:
                            raise ValueError("季节五态与同时返回的对象五行不符")
                if self.day_ganzhi is not None and row.sky_xun_kong != (
                    row.sky_branch in kongwang_for_ganzhi(self.day_ganzhi)[:2]
                ):
                    raise ValueError("季节条件支神本空与日干支不符")
            for field, condition in [
                ("raw_true_condition_branches", "真空条件"),
                ("raw_half_condition_branches", "半空条件"),
            ]:
                present = getattr(self, field)
                if present is not None and present != [
                    b
                    for b in BRANCHES
                    if any(
                        r.sky_branch == b
                        and r.sky_empty_seasonal_condition == condition
                        for r in self.rows
                    )
                ]:
                    raise ValueError("原始真半条件支清单与同时返回的十二位不符")
            if self.day_ganzhi is not None and self.month_branch is not None:
                expected = seasonal_evidence(
                    day_ganzhi=self.day_ganzhi,
                    month_branch=self.month_branch,
                    sky_by_earth={r.earth_branch: r.sky_branch for r in self.rows},
                    god_by_sky={r.sky_branch: r.god for r in self.rows},
                )
                compare_present_branches(self.model_dump(exclude_unset=True), expected)
        return self


def get(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def align_seasonal(board: Any, pillars: Any = None) -> None:
    value = get(board, "seasonal_evidence")
    if value is None:
        return
    day = get(value, "day_ganzhi")
    month = get(value, "month_branch")
    if pillars is not None:
        a, b = get(get(pillars, "day"), "stem"), get(get(pillars, "day"), "branch")
        if day is not None and a is not None and b is not None and day != a + b:
            raise ValueError("季节条件与同次日干支不符")
        own = get(get(pillars, "month"), "branch")
        if own is not None and month is not None and own != month:
            raise ValueError("季节条件必须用同次月建支")
    for name in ["emptiness_evidence", "branch_relations"]:
        item = get(board, name)
        if (
            day is not None
            and get(item, "day_ganzhi") is not None
            and day != get(item, "day_ganzhi")
        ):
            raise ValueError("季节条件日干支与本课不符")
        mb = (
            get(item, "month_building_branch")
            if name == "emptiness_evidence"
            else get(get(item, "calendar_branches"), "month")
        )
        if month is not None and mb is not None and month != mb:
            raise ValueError("季节条件月建与本课不符")
    rows = get(value, "rows")
    if rows is not None:
        by_earth = {get(r, "earth_branch"): r for r in rows}
        by_sky = {get(r, "sky_branch"): r for r in rows}
        for r in get(board, "twelve_board") or []:
            own = by_earth[get(r, "earth_branch")]
            if any(
                get(r, k) is not None and get(r, k) != get(own, k)
                for k in ["sky_branch", "god"]
            ):
                raise ValueError("季节条件必须沿用同次十二盘支神天将")
        for label in ["initial", "middle", "final"]:
            r = get(get(board, "three_transmissions"), label)
            branch = get(r, "branch")
            if branch is not None:
                own = by_sky[branch]
                if get(r, "god") is not None and get(r, "god") != get(own, "god"):
                    raise ValueError("季节条件与三传乘将不符")
                if get(r, "xun_kong") is not None and get(r, "xun_kong") != get(
                    own, "sky_xun_kong"
                ):
                    raise ValueError("季节条件与三传本空不符")


def require_complete_seasonal(board: dict[str, Any]) -> None:
    from .metaphysics.liureng_seasonal import seasonal_evidence, seasonal_trace

    if not isinstance(board, dict):
        raise ValueError("完整六壬输出缺少本课")
    value = board.get("seasonal_evidence")
    if not isinstance(value, dict):
        raise ValueError("完整六壬输出缺少季节条件")
    LiurenSeasonalEvidence.model_validate(value)
    if (
        value.get("day_ganzhi") is None
        or value.get("month_branch") is None
        or not isinstance(value.get("rows"), list)
    ):
        raise ValueError("完整六壬季节条件缺少同次输入")
    expected = seasonal_evidence(
        day_ganzhi=value["day_ganzhi"],
        month_branch=value["month_branch"],
        sky_by_earth={r["earth_branch"]: r["sky_branch"] for r in value["rows"]},
        god_by_sky={r["sky_branch"]: r["god"] for r in value["rows"]},
    )
    if value != expected:
        raise ValueError("完整六壬季节条件缺项或不符")
    align_seasonal(board)
    if [
        r
        for r in board.get("rule_trace", [])
        if r.get("rule_id") == "liuren.seasonal_conditions"
    ] != [seasonal_trace(expected)]:
        raise ValueError("季节条件轨迹缺项、重复或不符")
