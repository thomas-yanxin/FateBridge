"""Year-branch cycles and Ming-source comparisons for the natal cycles."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal, TypedDict, cast

from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import EARTHLY_BRANCHES

YEAR_CYCLE_SOURCE = "iztro 2.5.8 decorativeStar"
SUIQIAN = tuple("岁建 晦气 丧门 贯索 官符 小耗 大耗 龙德 白虎 天德 吊客 病符".split())
JIANGQIAN = tuple("将星 攀鞍 岁驿 息神 华盖 劫煞 灾煞 天煞 指背 咸池 月煞 亡神".split())

_YearBranchBasis = Literal["natal_lunar_year_branch", "target_lunar_year_branch"]


class _YearCyclePosition(TypedDict):
    name: str
    branch: str


class _YearCycle(TypedDict):
    system_id: str
    start_branch: str
    positions: list[_YearCyclePosition]


class YearBranchCycles(TypedDict):
    anchor_basis: _YearBranchBasis
    year_branch: str
    direction: Literal["forward"]
    source: str
    suiqian: _YearCycle
    jiangqian: _YearCycle


def year_branch_cycles(
    year_branch: str, *, anchor_basis: _YearBranchBasis
) -> YearBranchCycles:
    """Rotate iztro's default labels from an already-resolved lunar year branch."""
    year_index = EARTHLY_BRANCHES.index(year_branch)
    # 子辰申、丑巳酉、寅午戌、卯未亥 share their 三合帝旺 branch.
    jiangxing_index = (0, 9, 6, 3)[year_index % 4]

    def rotate(start: int, labels: tuple[str, ...], system_id: str) -> _YearCycle:
        return {
            "system_id": system_id,
            "start_branch": EARTHLY_BRANCHES[start],
            "positions": [
                {"name": name, "branch": EARTHLY_BRANCHES[(start + offset) % 12]}
                for offset, name in enumerate(labels)
            ],
        }

    return {
        "anchor_basis": anchor_basis,
        "year_branch": year_branch,
        "direction": "forward",
        "source": YEAR_CYCLE_SOURCE,
        "suiqian": rotate(year_index, SUIQIAN, "iztro_2_5_8_suiqian_default"),
        "jiangqian": rotate(jiangxing_index, JIANGQIAN, "iztro_2_5_8_jiangqian"),
    }


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-cycles.json")
            .read_text(encoding="utf-8")
        ),
    )


def _positions(sequence: list[str], start: str, sign: int) -> dict[str, str]:
    branches = "子丑寅卯辰巳午未申酉戌亥"
    return {
        branches[(branches.index(start) + sign * i) % 12]: name
        for i, name in enumerate(sequence)
    }


def cycle_source_evidence(
    palaces: list[dict[str, Any]],
    cycle_rules: dict[str, Any],
    *,
    element: str,
    year_stem: str,
    gender: str,
    rule_profile: str,
) -> dict[str, Any]:
    source = _source()
    canonical = normalize_gender(gender)
    known = canonical in {"男", "女"}
    cs_signs = [1 if canonical == "男" else -1] if known else [1, -1]
    bs_forward = (year_stem in "甲丙戊庚壬") == (canonical == "男")
    bs_signs = [1 if bs_forward else -1] if known else [1, -1]
    cs_start = source["changsheng"]["starts_by_element"][element]
    bs_start = source["lucun"]["starts_by_stem"][year_stem]
    cs_maps = [
        _positions(source["changsheng"]["sequence_modern"], cs_start, s)
        for s in cs_signs
    ]
    bs_maps = [
        _positions(source["boshi"]["sequence_modern"], bs_start, s) for s in bs_signs
    ]
    rows: dict[str, dict[str, Any]] = {"changsheng": {}, "boshi": {}}
    for palace in palaces:
        branch = palace["ganzhi"][1]
        for prefix, key, maps in (
            ("changsheng", "changsheng12", cs_maps),
            ("boshi", "boshi12", bs_maps),
        ):
            candidates = list(dict.fromkeys(m[branch] for m in maps))
            rows[prefix][branch] = {
                "actual": palace[key],
                "candidates": candidates,
                "match": palace[key] == candidates[0] if len(candidates) == 1 else None,
            }

    def header(
        prefix: str, key: str, start: str, label: str, signs: list[int]
    ) -> dict[str, Any]:
        starts = [p["ganzhi"][1] for p in palaces if p[key] == label]
        direction = ("顺行" if signs[0] == 1 else "逆行") if known else None
        return {
            "source_start": start,
            "actual_start_branches": starts,
            "reported_start": cycle_rules[prefix + "_start"],
            "start_match": starts == [start]
            and cycle_rules[prefix + "_start"] == start,
            "source_direction": direction,
            "actual_direction": cycle_rules[prefix + "_direction"],
            "direction_match": (
                cycle_rules[prefix + "_direction"] == direction if known else None
            ),
        }

    return {
        "method_id": source["id"],
        "version": source["version"],
        "source": source["source_url"],
        "printed_volume": source["printed_volume"],
        "source_frames": {"changsheng": 78, "boshi": 77, "lucun": 76},
        "inputs": {
            "bureau_element": element,
            "natal_year_stem": year_stem,
            "gender": canonical,
        },
        "scope": "cycle_labels_given_bureau_stem_gender_not_calendar_or_whole_book",
        "changsheng": header("changsheng", "changsheng12", cs_start, "长生", cs_signs),
        "boshi": header("boshi", "boshi12", bs_start, "博士", bs_signs),
        "positions": rows,
        "source_rule_applied": {
            "changsheng": rule_profile == "quanshu_v2_excerpt",
            "boshi": True,
        },
        "source_name_mapping": {
            "博士层蜚廉": "飞廉",
            "明刊大耗": "大耗",
            "明刊官府": "官府",
        },
        "unknown_gender_policy": "retain_only_labels_shared_by_both_directions",
        "manual_reader_count": source["manual_reader_count"],
        "whole_book_conformance_claimed": False,
    }
