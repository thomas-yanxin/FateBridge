"""Independent, source-specific natal star brightness tables."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Dict, List, Literal, Optional, Tuple, TypedDict

from fatebridge.core.ziwei.ziwei_rulesets import (
    DEFAULT_ZIWEI_PROFILE,
    IZTRO_SOURCE,
    QUANSHU_BRIGHTNESS_CONFLICT,
    validate_rule_profile,
)
from fatebridge.utils.data import EARTHLY_BRANCHES, ZIWEI_BRANCH_SEQUENCE
from fatebridge.utils.errors import ParameterError

ZiweiBrightnessSource = Literal[
    "rule_profile",
    "iztro_2_5_8",
    "quanshu_v2_selected_table",
    "ziwei_doushu_qs",
    "ziwei_doushu_xd1",
    "ziwei_doushu_zz",
    "ziwei_doushu_xd2",
]
BRIGHTNESS_SOURCE_DESCRIPTION = (
    "本命庙旺表。rule_profile（默认）沿用基础盘式。iztro_2_5_8 取软件原表，"
    "quanshu_v2_selected_table 取《紫微斗数全书》卷二转录的十二宫表。"
    "ziwei_doushu_qs、ziwei_doushu_xd1、ziwei_doushu_zz、ziwei_doushu_xd2 "
    "取 Renhuai123/ziwei-doushu 固定版本软件对照表。空格为 null，不跨表补值。"
    "安星、历法、四化及运限起法仍按各自规则。"
)
_SEVEN_GRADES = tuple("庙旺得利平不陷")
_FIVE_GRADES = tuple("庙旺平闲陷")
_COMPATIBILITY_VARIANTS = {
    "ziwei_doushu_qs": "QS",
    "ziwei_doushu_xd1": "XD1",
    "ziwei_doushu_zz": "ZZ",
    "ziwei_doushu_xd2": "XD2",
}

_MUTAGEN_SUFFIXES: Tuple[str, ...] = ("化禄", "化权", "化科", "化忌")

# star name -> 12 brightness values (寅-indexed); None = not applicable.
ZIWEI_STAR_BRIGHTNESS: Dict[str, List[Optional[str]]] = {
    # --- 14 主星 ---
    "紫微": ["旺", "旺", "得", "旺", "庙", "庙", "旺", "旺", "得", "旺", "平", "庙"],
    "天机": ["得", "旺", "利", "平", "庙", "陷", "得", "旺", "利", "平", "庙", "陷"],
    "太阳": ["旺", "庙", "旺", "旺", "旺", "得", "得", "陷", "不", "陷", "陷", "不"],
    "武曲": ["得", "利", "庙", "平", "旺", "庙", "得", "利", "庙", "平", "旺", "庙"],
    "天同": ["利", "平", "平", "庙", "陷", "不", "旺", "平", "平", "庙", "旺", "不"],
    "廉贞": ["庙", "平", "利", "陷", "平", "利", "庙", "平", "利", "陷", "平", "利"],
    "天府": ["庙", "得", "庙", "得", "旺", "庙", "得", "旺", "庙", "得", "庙", "庙"],
    "太阴": ["旺", "陷", "陷", "陷", "不", "不", "利", "不", "旺", "庙", "庙", "庙"],
    "贪狼": ["平", "利", "庙", "陷", "旺", "庙", "平", "利", "庙", "陷", "旺", "庙"],
    "巨门": ["庙", "庙", "陷", "旺", "旺", "不", "庙", "庙", "陷", "旺", "旺", "不"],
    "天相": ["庙", "陷", "得", "得", "庙", "得", "庙", "陷", "得", "得", "庙", "庙"],
    "天梁": ["庙", "庙", "庙", "陷", "庙", "旺", "陷", "得", "庙", "陷", "庙", "旺"],
    "七杀": ["庙", "旺", "庙", "平", "旺", "庙", "庙", "庙", "庙", "平", "旺", "庙"],
    "破军": ["得", "陷", "旺", "平", "庙", "旺", "得", "陷", "旺", "平", "庙", "旺"],
    # --- 辅煞星 with brightness ---
    "文昌": ["陷", "利", "得", "庙", "陷", "利", "得", "庙", "陷", "利", "得", "庙"],
    "文曲": ["平", "旺", "得", "庙", "陷", "旺", "得", "庙", "陷", "旺", "得", "庙"],
    "火星": ["庙", "利", "陷", "得", "庙", "利", "陷", "得", "庙", "利", "陷", "得"],
    "铃星": ["庙", "利", "陷", "得", "庙", "利", "陷", "得", "庙", "利", "陷", "得"],
    "擎羊": [None, "陷", "庙", None, "陷", "庙", None, "陷", "庙", None, "陷", "庙"],
    "陀罗": ["陷", None, "庙", "陷", None, "庙", "陷", None, "庙", "陷", None, "庙"],
}


class _BrightnessMetadata(TypedDict):
    id: str
    source_kind: str
    source_url: str
    version: str
    branch_order: List[str]
    grade_scale: List[str]
    aliases: Dict[str, str]
    blank_meaning: str


@dataclass(frozen=True)
class ZiweiBrightnessTable:
    _metadata: _BrightnessMetadata
    _branch_index: Dict[str, int]
    _rows: Dict[str, List[Optional[str]]]

    @property
    def id(self) -> str:
        return self._metadata["id"]

    def lookup(self, star: str, branch: str) -> Optional[str]:
        row = self._rows.get(self._metadata["aliases"].get(star, star))
        index = self._branch_index.get(branch)
        return row[index] if row is not None and index is not None else None

    def ruleset_fields(self, unresolved: List[str]) -> Dict[str, object]:
        return {
            "brightness_rule": self.id,
            "brightness_table": deepcopy(self._metadata),
            "unresolved": [
                note
                for note in unresolved
                if note != QUANSHU_BRIGHTNESS_CONFLICT
                or self.id == "quanshu_v2_selected_table"
            ],
        }


class _QuanshuBrightness(TypedDict):
    source: str
    branch_order: List[str]
    brightness: Dict[str, List[Optional[str]]]


class _CompatibilityBrightness(TypedDict):
    source: str
    revision: str
    branch_order: List[str]
    name_aliases: Dict[str, str]
    tables: Dict[str, Dict[str, List[Optional[str]]]]


@cache
def _compatibility_brightness() -> _CompatibilityBrightness:
    data: _CompatibilityBrightness = json.loads(
        files("fatebridge")
        .joinpath("data/classical/ziwei-doushu-brightness.json")
        .read_text(encoding="utf-8")
    )
    return data


@cache
def _brightness_table(table_id: str) -> ZiweiBrightnessTable:
    grades = _SEVEN_GRADES
    expected_branches = ZIWEI_BRANCH_SEQUENCE
    if table_id == "iztro_2_5_8":
        rows = ZIWEI_STAR_BRIGHTNESS
        branches = list(ZIWEI_BRANCH_SEQUENCE)
        source_kind = "software_implementation"
        source_url = f"{IZTRO_SOURCE.replace('/tree/', '/blob/')}/src/data/stars.ts"
        version = "2.5.8"
        aliases = {"qingyangMin": "擎羊"}
    elif table_id == "quanshu_v2_selected_table":
        classical: _QuanshuBrightness = json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-quanshu-v2-table.json")
            .read_text(encoding="utf-8")
        )
        rows = classical["brightness"]
        branches = classical["branch_order"]
        source_kind = "classical_transcription"
        source_url = classical["source"]
        version = "oldid=1963110"
        aliases = {}
    else:
        variant = _COMPATIBILITY_VARIANTS.get(table_id)
        if variant is None:
            raise ParameterError(
                f"不支持的紫微庙旺表：{table_id!r}",
                [
                    {
                        "path": "brightness_source",
                        "code": "unsupported_brightness_source",
                    }
                ],
            )
        compatibility = _compatibility_brightness()
        rows = compatibility["tables"][variant]
        branches = compatibility["branch_order"]
        expected_branches = EARTHLY_BRANCHES
        source_kind = "software_compatibility"
        source_url = compatibility["source"]
        version = compatibility["revision"]
        aliases = compatibility["name_aliases"]
        if variant in {"ZZ", "XD2"}:
            grades = _FIVE_GRADES
    if branches != expected_branches or any(
        len(row) != len(branches) for row in rows.values()
    ):
        raise ValueError(f"紫微庙旺表地支序或行宽错误：{table_id}")
    return ZiweiBrightnessTable(
        _metadata={
            "id": table_id,
            "source_kind": source_kind,
            "source_url": source_url,
            "version": version,
            "branch_order": branches,
            "grade_scale": list(grades),
            "aliases": aliases,
            "blank_meaning": "no_grade_recorded_for_star_and_branch_in_selected_table",
        },
        _branch_index={branch: index for index, branch in enumerate(branches)},
        _rows=rows,
    )


def brightness_table_for(
    rule_profile: str, brightness_source: ZiweiBrightnessSource
) -> ZiweiBrightnessTable:
    if brightness_source == "rule_profile":
        return _brightness_table(
            "quanshu_v2_selected_table"
            if rule_profile == "quanshu_v2_excerpt"
            else "iztro_2_5_8"
        )
    return _brightness_table(brightness_source)


def lookup_star_brightness(
    star: str,
    branch: str,
    *,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    brightness_source: ZiweiBrightnessSource = "rule_profile",
) -> Optional[str]:
    """Return the selected table's literal label, or None with no recorded cell."""
    validate_rule_profile(rule_profile)
    return brightness_table_for(rule_profile, brightness_source).lookup(star, branch)


def split_star_mutagen(star_label: str) -> Tuple[str, Optional[str]]:
    """Split a possibly mutagen-suffixed star label.

    ``"紫微化科"`` -> ``("紫微", "化科")``; ``"天府"`` -> ``("天府", None)``.
    """
    for suffix in _MUTAGEN_SUFFIXES:
        if star_label.endswith(suffix):
            return star_label[: -len(suffix)], suffix
    return star_label, None
