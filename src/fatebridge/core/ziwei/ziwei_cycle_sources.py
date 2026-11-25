"""Cycle comparisons against a Ming collation, with unresolved directions kept."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

from fatebridge.utils.birth_input import normalize_gender


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
