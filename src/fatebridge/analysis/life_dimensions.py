#!/usr/bin/env python3
"""
生命维度评分模块

根据本命四柱与当前时柱（流时/流日/流月/流年/大运）之间的十神交互关系，
计算用户在五个生命维度上的当前分值（0-100 区间）：

- love (爱情)
- wealth (财富)
- career (事业)
- learning (学习)
- relationship (人际)

分值是本模块按固定权重生成的文化参考指标，不是现实成功概率。
已知零计数与其他计数使用同一连续标度；未知性别的爱情维度为null。

十神 → 维度映射（gender-aware）：
- 比肩 / 劫财  →  人际
- 食神 / 伤官  →  学习 (0.6) + 人际 (±0.2，伤官减)
- 正财 / 偏财  →  财富；男性额外 → 爱情 (0.6)
- 正官 / 七杀  →  事业；女性额外 → 爱情 (0.6)
- 正印 / 偏印  →  学习
"""

from __future__ import annotations

import math
from typing import Dict, Mapping, Optional, Tuple

from ..core.method_contracts import LIFE_DIMENSION_INDEX
from ..utils.data import BRANCH_HIDDEN_STEMS, TenGod, get_ten_god, normalize_gender

PillarMap = Mapping[str, Tuple[str, str]]
"""柱位映射: {label: (stem, branch)}, 例如 {"year": ("丙", "午")}"""

DIMENSION_KEYS = ("love", "wealth", "career", "learning", "relationship")
LIFE_DIMENSION_METHOD = LIFE_DIMENSION_INDEX.method_id

# 各时间层柱在当前时刻的影响权重
# （本命柱固定为 1.0，下表只覆盖时间柱）
_TEMPORAL_LAYER_WEIGHTS: Dict[str, float] = {
    "dayun": 1.0,  # 大运：十年一变，强影响
    "liunian": 1.0,  # 流年：当年趋势
    "liuyue": 0.8,  # 流月
    "liuri": 0.7,  # 流日
    "liushi": 0.5,  # 流时
}


class LifeDimensionAnalysis:
    """生命维度分值计算"""

    @staticmethod
    def calculate_life_dimensions(
        birth_pillars: PillarMap,
        current_pillars: Optional[PillarMap] = None,
        gender: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        """
        计算五维生命维度分值。

        Args:
            birth_pillars: 本命四柱 ``{"year": (stem, branch), "month": (...),
                "day": (...), "hour": (...)}``。其中 ``day`` 必须存在（用于取日主）。
            current_pillars: 当前时间各层柱，子集即可，可选键
                ``"dayun" / "liunian" / "liuyue" / "liuri" / "liushi"``。
                None 或空字典时只使用本命基线。
            gender: ``"male" / "female" / "男" / "女"`` 等。未知时爱情维度为空。

        Returns:
            ``{"love": float, "wealth": float, "career": float,
              "learning": float, "relationship": float}``，已计算值在0–100之间。
        """
        if "day" not in birth_pillars:
            raise ValueError("birth_pillars 必须包含 'day' 柱以确定日主")

        day_stem = birth_pillars["day"][0]

        ten_god_counts = LifeDimensionAnalysis._collect_ten_god_counts(
            day_stem=day_stem,
            birth_pillars=birth_pillars,
            current_pillars=current_pillars or {},
        )

        raw = LifeDimensionAnalysis._map_ten_gods_to_dimensions(
            ten_god_counts=ten_god_counts,
            gender=gender,
        )

        return {
            key: (
                None
                if key == "love" and normalize_gender(gender) not in {"male", "female"}
                else round(LifeDimensionAnalysis._normalize_to_score(raw[key]), 1)
            )
            for key in DIMENSION_KEYS
        }

    @staticmethod
    def _collect_ten_god_counts(
        *,
        day_stem: str,
        birth_pillars: PillarMap,
        current_pillars: PillarMap,
    ) -> Dict[TenGod, float]:
        counts: Dict[TenGod, float] = {tg: 0.0 for tg in TenGod}

        # 本命四柱（除日干自身外的天干 + 所有地支藏干）
        for label, pillar in birth_pillars.items():
            stem, branch = pillar
            if label != "day":
                LifeDimensionAnalysis._accumulate(counts, day_stem, stem, weight=1.0)
            for hidden_stem in BRANCH_HIDDEN_STEMS.get(branch, []):
                LifeDimensionAnalysis._accumulate(
                    counts, day_stem, hidden_stem, weight=0.5
                )

        # 当前各时间层柱
        for label, pillar in current_pillars.items():
            weight = _TEMPORAL_LAYER_WEIGHTS.get(label, 0.5)
            stem, branch = pillar
            LifeDimensionAnalysis._accumulate(counts, day_stem, stem, weight=weight)
            for hidden_stem in BRANCH_HIDDEN_STEMS.get(branch, []):
                LifeDimensionAnalysis._accumulate(
                    counts, day_stem, hidden_stem, weight=weight * 0.5
                )

        return counts

    @staticmethod
    def _accumulate(
        counts: Dict[TenGod, float],
        day_stem: str,
        other_stem: str,
        *,
        weight: float,
    ) -> None:
        ten_god = get_ten_god(day_stem, other_stem)
        counts[ten_god] += weight

    @staticmethod
    def _map_ten_gods_to_dimensions(
        *,
        ten_god_counts: Dict[TenGod, float],
        gender: Optional[str],
    ) -> Dict[str, float]:
        raw = {key: 0.0 for key in DIMENSION_KEYS}

        compare = ten_god_counts[TenGod.COMPARE] + ten_god_counts[TenGod.ROB_WEALTH]
        food = ten_god_counts[TenGod.FOOD_GOD]
        hurt = ten_god_counts[TenGod.HURT_OFFICER]
        wealth = (
            ten_god_counts[TenGod.POSITIVE_WEALTH]
            + ten_god_counts[TenGod.PARTIAL_WEALTH]
        )
        officer = (
            ten_god_counts[TenGod.POSITIVE_OFFICER]
            + ten_god_counts[TenGod.SEVEN_KILLER]
        )
        seal = (
            ten_god_counts[TenGod.POSITIVE_SEAL] + ten_god_counts[TenGod.PARTIAL_SEAL]
        )

        # 比肩/劫财 → 人际
        raw["relationship"] += compare

        # 食神 提升学习与人际；伤官 提升学习但损人际
        raw["learning"] += (food + hurt) * 0.6
        raw["relationship"] += food * 0.2 - hurt * 0.2

        # 财星 → 财富 (男性附加 → 爱情)
        raw["wealth"] += wealth
        # 官杀 → 事业 (女性附加 → 爱情)
        raw["career"] += officer
        # 印星 → 学习
        raw["learning"] += seal

        norm_gender = normalize_gender(gender)
        if norm_gender == "male":
            raw["love"] += wealth * 0.6
        elif norm_gender == "female":
            raw["love"] += officer * 0.6
        # 未知性别的爱情维度由调用处保留为null，不把它当作零计数。

        return raw

    @staticmethod
    def _normalize_to_score(raw_value: float) -> float:
        """
        将原始十神计数映射到 0-100 区间。

        已知计数统一沿用以raw=3.0为中位的tanh标度；缺失在调用处单独处理。
        """
        centered = raw_value - 3.0
        score = 50.0 + 50.0 * math.tanh(centered / 3.0)
        # 软夹紧到 [0, 100]
        return max(0.0, min(100.0, score))
