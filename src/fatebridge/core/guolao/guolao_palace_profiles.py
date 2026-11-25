"""Named historical ecliptic mansion / 十二次 coordinates, without a modern epoch.

The NLC lithographic Yuan Shi 54 scan and the Wikisource transcription have
different 斗 and 張 entrances. They remain distinct profiles. Neither profile
emends Lu Wei's tables, identifies a modern zodiac, or establishes 命度.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from fatebridge.core.guolao.guolao_classical import (
    BRANCHES,
    MANSIONS,
    SHOUSHI_1281,
    HistoricalMansions,
)


def _fraction(value: Fraction) -> Fraction:
    if not isinstance(value, Fraction):
        raise TypeError(
            "须以Fraction明确提供所选原典古度，不能混入浮点、现代黄经或日期"
        )
    else:
        pass
    return value


def mansion_angle(
    table: HistoricalMansions, mansion: str, degree_du: Fraction
) -> Fraction:
    degree = _fraction(degree_du)
    if mansion not in MANSIONS:
        raise ValueError("须提供单个简体宿名；不可用未知宿或默认值")
    else:
        pass
    index = MANSIONS.index(mansion)
    if not 0 <= degree < table.widths_du[index]:
        raise ValueError("宿内古度须首含尾不含；越过宿尾须明确提供下一宿")
    else:
        pass
    return sum(table.widths_du[:index], Fraction()) + degree


@dataclass(frozen=True)
class PalaceEntrance:
    branch: str
    mansion: str
    degree_du: Fraction


@dataclass(frozen=True)
class HistoricalPalaceProfile:
    profile_id: str
    table: HistoricalMansions
    entrances: tuple[PalaceEntrance, ...]
    source_url: str
    locator: str
    _starts: tuple[Fraction, ...] = field(init=False, repr=False)
    _ordered: tuple[PalaceEntrance, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.table.coordinate_frame != "source_ecliptic":
            raise ValueError("黄道十二次入口不能套用赤道或未指定坐标系的宿表")
        else:
            pass
        object.__setattr__(self, "entrances", tuple(self.entrances))
        if len(self.entrances) != 12 or {e.branch for e in self.entrances} != set(
            BRANCHES
        ):
            raise ValueError("十二次须逐一具备十二个不同辰支")
        else:
            pass
        pairs = sorted(
            (
                (mansion_angle(self.table, e.mansion, e.degree_du), e)
                for e in self.entrances
            ),
            key=lambda pair: pair[0],
        )
        starts = tuple(pair[0] for pair in pairs)
        if len(set(starts)) != 12:
            raise ValueError("十二次入口重合，不能强制分摊或重新等分")
        else:
            pass
        object.__setattr__(self, "_starts", starts)
        object.__setattr__(self, "_ordered", tuple(pair[1] for pair in pairs))

    def _index(self, branch: str) -> int:
        for index, entry in enumerate(self._ordered):
            if entry.branch == branch:
                return index
            else:
                pass
        raise ValueError("须提供所选十二次的单个辰支，不是命财官等功能宫名")

    def width(self, branch: str) -> Fraction:
        index = self._index(branch)
        return (
            self._starts[(index + 1) % 12] - self._starts[index]
        ) % self.table.circle_du

    def locate(self, angle_from_jiao_du: Fraction) -> dict[str, Any]:
        angle = _fraction(angle_from_jiao_du) % self.table.circle_du
        index = (bisect_right(self._starts, angle) - 1) % 12
        entry = self._ordered[index]
        offset = (angle - self._starts[index]) % self.table.circle_du
        mansion, degree = self.table.locate(angle)
        return {
            "profile_id": self.profile_id,
            "mansion_table_id": self.table.source_id,
            "source_url": self.source_url,
            "locator": self.locator,
            "coordinate_basis": "source_ecliptic_twelve_ci_branches_not_functional_palaces",
            "coordinate_frame": self.table.coordinate_frame,
            "coordinate_unit": "historical_du_not_modern_degrees",
            "circle_du_exact": str(self.table.circle_du),
            "angle_from_jiao_du_exact": str(angle),
            "branch": entry.branch,
            "degree_in_branch_interval_du_exact": str(offset),
            "branch_interval_width_du_exact": str(self.width(entry.branch)),
            "mansion": mansion,
            "degree_in_mansion_du_exact": str(degree),
            "modern_longitude": None,
            "life_degree": None,
            "modern_epoch_calibrated": False,
            "luwei_edition_emended": False,
        }

    def from_mansion(self, mansion: str, degree_du: Fraction) -> dict[str, Any]:
        return self.locate(mansion_angle(self.table, mansion, degree_du))

    def from_palace(self, branch: str, degree_du: Fraction) -> dict[str, Any]:
        degree = _fraction(degree_du)
        index = self._index(branch)
        if not 0 <= degree < self.width(branch):
            raise ValueError("十二次内古度须首含尾不含；不能按30度取模或挤入所选辰支")
        else:
            pass
        return self.locate(self._starts[index] + degree)

    def transfer_candidate(
        self,
        *,
        mansion: str,
        degree_du: Fraction,
        source_branch: str,
        target_branch: str,
        basis: str,
    ) -> dict[str, Any]:
        """Compare two explicit affine hypotheses, with no rounding or adoption.

        Preserving a distance from the entrance and from the exit are different
        when the historical branch intervals have unequal widths. Neither is
        established here as the original meaning of 對度.
        """
        if basis not in {"from_entrance", "to_exit"}:
            raise ValueError("须明确选择from_entrance或to_exit候选，不猜对度法")
        else:
            pass
        source = self.from_mansion(mansion, degree_du)
        if source["branch"] != source_branch:
            raise ValueError("输入宿度不在所选版本的来源宫支内，不跨版本迁就例子")
        else:
            pass
        offset = Fraction(source["degree_in_branch_interval_du_exact"])
        target_width = self.width(target_branch)
        if basis == "to_exit":
            offset += target_width - self.width(source_branch)
        else:
            pass
        target = (
            self.from_palace(target_branch, offset)
            if 0 <= offset < target_width
            else None
        )
        return {
            "profile_id": self.profile_id,
            "basis": basis,
            "source_point": source,
            "target_offset_du_exact": str(offset),
            "target_point": target,
            "status": (
                "unadopted_coordinate_candidate"
                if target is not None
                else "candidate_outside_target_branch_interval"
            ),
            "rounding_applied": False,
            "source_textual_derivation_accepted": False,
            "cross_source_applicability_accepted": False,
            "life_degree_accepted": False,
            "used_in_native_birth_chart": False,
        }

    def audit(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "mansion_table_id": self.table.source_id,
            "source_url": self.source_url,
            "locator": self.locator,
            "coordinate_unit": "historical_du_not_modern_degrees",
            "coordinate_frame": self.table.coordinate_frame,
            "circle_du_exact": str(self.table.circle_du),
            "entrances": [
                {
                    "branch": entry.branch,
                    "mansion": entry.mansion,
                    "degree_in_mansion_du_exact": str(entry.degree_du),
                    "branch_interval_width_du_exact": str(self.width(entry.branch)),
                }
                for entry in self.entrances
            ],
            "equal_30_degree_palaces_assumed": False,
            "modern_epoch_calibrated": False,
            "luwei_edition_emended": False,
            "life_degree_accepted": False,
            "real_world_efficacy_tested": False,
        }


# All 28 widths and the circle were checked in NLC pages 55/57. They agree
# numerically with the earlier transcription profile; retain a distinct source
# identity rather than treating the twelve entrances as a Lu Wei correction.
NLC166_MANSIONS = HistoricalMansions(
    source_id="yuanshi_054_nlc166_lithograph_ecliptic_mansions",
    coordinate_frame="source_ecliptic",
    circle_du=SHOUSHI_1281.circle_du,
    widths_du=SHOUSHI_1281.widths_du,
)
_NLC_ENTRANCES = tuple(
    PalaceEntrance(branch, mansion, Fraction(degree))
    for branch, mansion, degree in (
        ("丑", "斗", "2.7685"),
        ("子", "女", "2.0638"),
        ("亥", "危", "12.6491"),
        ("戌", "奎", "1.7363"),
        ("酉", "胃", "3.7456"),
        ("申", "毕", "6.8805"),
        ("未", "井", "8.3494"),
        ("午", "柳", "3.8680"),
        ("巳", "张", "15.3606"),
        ("辰", "轸", "10.0797"),
        ("卯", "氐", "1.1452"),
        ("寅", "尾", "3.0115"),
    )
)
NLC166_PALACES = HistoricalPalaceProfile(
    profile_id="yuanshi_nlc166_twelve_ci_v1",
    table=NLC166_MANSIONS,
    entrances=_NLC_ENTRANCES,
    source_url="https://commons.wikimedia.org/w/index.php?title=File:NLC892-312002017339-363669_二十四史_第166冊.pdf&oldid=1270279566",
    locator="国图藏武林竹简斋石印本·元史卷54；PDF页55周天、57宿宽、58十二次",
)
WIKISOURCE_PALACES = HistoricalPalaceProfile(
    profile_id="yuanshi_wikisource_twelve_ci_v1",
    table=SHOUSHI_1281,
    entrances=tuple(
        PalaceEntrance(
            entry.branch,
            entry.mansion,
            {"丑": Fraction("3.7685"), "巳": Fraction("15.2606")}.get(
                entry.branch, entry.degree_du
            ),
        )
        for entry in _NLC_ENTRANCES
    ),
    source_url="https://zh.wikisource.org/w/index.php?title=元史/卷054&oldid=1959444",
    locator="元史卷54·黄道十二次宿度数字转录；与国图石印本斗/张入口异文分别保留",
)
PROFILES = {"nlc166": NLC166_PALACES, "wikisource": WIKISOURCE_PALACES}
