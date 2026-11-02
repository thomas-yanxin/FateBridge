"""A complete named research table compared with an explicitly selected host.

Printed author decisions remain separate from a mechanical threshold, from the
old book column, and from an independently established historical calendar.
"""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_left
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_shoku766 import month_witness_comparison, witness_lines
from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_dayan_advance_2022.json"
HOST_SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_japanese_historical_v1.json"
)
ROW_PROJECTION_SHA256 = (
    "3e614444f30cca15e7f288a59f8df58ba7de41bfa31d3ab22d1957a43044fd08"
)
DAY_CYCLE = tuple(
    "甲乙丙丁戊己庚辛壬癸"[n % 10] + "子丑寅卯辰巳午未申酉戌亥"[n % 12]
    for n in range(60)
)


def validate_bundle(data: dict[str, Any]) -> None:
    rows = data["rows"]
    projection = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if (
        data["complete_numeric_row_projection_sha256"] != ROW_PROJECTION_SHA256
        or hashlib.sha256(projection).hexdigest() != ROW_PROJECTION_SHA256
        or len(rows) != 327
        or [r["row_number"] for r in rows] != list(range(1, 328))
    ):
        raise ValueError("大衍所选327行数值与原始源预期的绑定已改变")
    if (
        data["units"]["day_units"] != 3040
        or data["source_reference"]["version_literal"] != "2022/12/27版"
        or data["source_reference"]["original_column_is_current_frozen_naoj_provider"]
        is not False
        or data["evaluation_policy"]["dash_means_unknown_not_nonadvance"] is not True
        or data["evaluation_policy"][
            "author_advance_uses_literal_decision_not_threshold"
        ]
        is not True
        or data["evaluation_policy"]["cyclic_difference_is_not_an_absolute_date_shift"]
        is not True
        or data["evaluation_policy"]["applied_to_selected_host_calendar_or_mansion"]
        is not False
        or data["evaluation_policy"]["hinoo_half_or_leap_short_precedence_established"]
        is not False
        or data["source_reference"]["parentheses_and_asterisk_interpretation_accepted"]
        is not False
    ):
        raise ValueError("大衍所选单位、版本或未知条件不得改为统一进朔法")


@dataclass(frozen=True)
class _Table:
    keys: tuple[tuple[int, int, bool], ...]
    row_json: tuple[str, ...]
    metadata_json: str
    sha256: str


@lru_cache(maxsize=4)
def _table(path: Path) -> _Table:
    loaded = load_source(path)
    data = loaded.data
    validate_bundle(data)
    ordered = sorted(
        data["rows"],
        key=lambda r: (r["lunar_year"], r["lunar_month"], r["is_leap_month"]),
    )
    keys = tuple(
        (r["lunar_year"], r["lunar_month"], r["is_leap_month"]) for r in ordered
    )
    if len(set(keys)) != len(keys):
        raise ValueError("大衍具名行的普通月与闰月键不得重复或合并")
    return _Table(
        keys,
        tuple(json.dumps(r, ensure_ascii=False) for r in ordered),
        json.dumps({k: v for k, v in data.items() if k != "rows"}, ensure_ascii=False),
        loaded.sha256,
    )


@lru_cache(maxsize=4)
def _scope_json(source_path: Path, host_path: Path) -> str:
    table = _table(source_path)
    host_source = load_source(host_path)
    host = host_source.data
    anchor = host["day_cycle_anchor"]
    starts = {
        (year, month, leap): (
            DAY_CYCLE.index(anchor["day_ganzhi"]) + ordinal - anchor["civil_ordinal"]
        )
        % 60
        for ordinal, year, month, leap, _length in host["months"]
    }
    states: dict[str, list[int]] = {"same": [], "different": [], "unknown": []}
    for key, raw in zip(table.keys, table.row_json, strict=True):
        row = json.loads(raw)
        literal = row["author_proposed_decision_literal"]
        selected = starts[key]  # A missing host row must not reduce the denominator.
        inferred = (
            None
            if literal == "-"
            else (
                row["computed_new_moon_day_cycle_index"] + int(literal.startswith("進"))
            )
            % 60
        )
        state = (
            "unknown"
            if inferred is None
            else "same" if inferred == selected else "different"
        )
        states[state].append(row["row_number"])
    return json.dumps(
        {
            "research_source_bundle_sha256": table.sha256,
            "host_source_bundle_sha256": host_source.sha256,
            "complete_selected_research_rows": len(table.keys),
            "same_direction_rows": sorted(states["same"]),
            "different_direction_rows": sorted(states["different"]),
            "unknown_direction_rows": sorted(states["unknown"]),
            "selected_image_witness_month_keys": [[766, 2, False]],
            "selected_image_witness_key_scope": (
                "The two Shoku766 witnesses only; Sandaikaku quoted/transmitted "
                "document dates have separate binding roles in sandaikaku_edict_reference, "
                "not another independently verified month-start calendar."
            ),
            "all_original_records_independently_collated": False,
            "historical_calendar_adjudicated": False,
            "prediction_efficacy_established": False,
            "real_samples": json.loads(table.metadata_json)["evaluation_policy"][
                "real_samples"
            ],
        },
        ensure_ascii=False,
    )


def research_scope() -> dict[str, Any]:
    """Give the complete fixed-host comparison, including every failed/unknown row."""
    result: dict[str, Any] = json.loads(_scope_json(SOURCE, HOST_SOURCE))
    return result


def scope_lines(scope: dict[str, Any], selected: dict[str, Any] | None) -> list[str]:
    lines = [
        f"完整具名研究选表{scope['complete_selected_research_rows']}行与当前固定NAOJ月首的方向对照仍为"
        f"{len(scope['same_direction_rows'])}相合、"
        f"{len(scope['different_direction_rows'])}不同、"
        f"{len(scope['unknown_direction_rows'])}未知；全部分歧和未知仍保留，"
        "这些数量不是历法或现实预测准确率，也未因此完成全表原记录校勘。"
        f"本组证据的真实预测样本数为{scope['real_samples']}，现实预测效力未建立。"
    ]
    if selected is None:
        lines.append(
            "本次所选月未列该研究选行，dayan_advance_research_comparison为空；"
            "没有本月所选原书影像校勘，不沿用766年二月的甲午／丙午作为本月结论。"
            "已有NAOJ历日和配宿仍可按所选配置解释，未列不等于否定其他史料。"
        )
    elif selected.get("selected_original_witness_comparison") is None:
        lines.append(
            "本次所选月没有766年二月那组原书影像校勘，"
            "selected_original_witness_comparison为空；当前研究选行仍按实际字段交付，"
            "不将别月甲午／丙午校订或条件月首用于本月，也不外推闰月补配或统一进朔公式。"
        )
    return lines


def month_comparison(
    year: int,
    month: int,
    leap: bool,
    *,
    host_month_start_index: int,
) -> dict[str, Any] | None:
    """Compare a source-derived cyclic label, without inventing a civil date."""
    if (
        type(year) is not int
        or type(month) is not int
        or not 1 <= month <= 12
        or type(leap) is not bool
        or type(host_month_start_index) is not int
        or not 0 <= host_month_start_index < 60
    ):
        raise ValueError("具名月首比较须使用明确月键及0至59的月首干支序号")
    table = _table(SOURCE)
    key = (year, month, leap)
    index = bisect_left(table.keys, key)
    if index == len(table.keys) or table.keys[index] != key:
        return None
    row = json.loads(table.row_json[index])
    literal = row["author_proposed_decision_literal"]
    shift = None if literal == "-" else int(literal.startswith("進"))
    proposal = (
        None
        if shift is None
        else (row["computed_new_moon_day_cycle_index"] + shift) % 60
    )
    limit = row["assumed_limit_units"]
    threshold = None if limit is None else row["computed_new_moon_remainder"] >= limit
    agrees = None if proposal is None else proposal == host_month_start_index
    return {
        **json.loads(table.metadata_json),
        "source_bundle_sha256": table.sha256,
        "selected_row": row,
        "host_month_start_index": host_month_start_index,
        "host_month_start_ganzhi": DAY_CYCLE[host_month_start_index],
        "author_proposed_day_shift_from_literal": shift,
        "author_direction_has_star_qualifier": "*" in literal,
        "inferred_author_month_start_index": proposal,
        "inferred_author_month_start_ganzhi": (
            None if proposal is None else DAY_CYCLE[proposal]
        ),
        "matches_author_direction_inference": agrees,
        "comparison_state": (
            "author_proposal_unknown"
            if agrees is None
            else "same_cyclic_label" if agrees else "different_cyclic_label"
        ),
        "source_proposal_minus_host_cyclic_days": (
            None
            if proposal is None
            else (proposal - host_month_start_index + 30) % 60 - 30
        ),
        "mechanical_ge_assumed_limit": threshold,
        "author_direction_differs_from_ge_assumed_limit": (
            None if shift is None or threshold is None else bool(shift) != threshold
        ),
        "proposed_absolute_civil_date": None,
        "physical_new_moon_recomputed": False,
        "selected_host_calendar_rewritten": False,
        "mansion_or_hinoo_priority_recomputed": False,
        "cited_original_records_independently_collated": False,
        "selected_original_witness_comparison": month_witness_comparison(
            year, month, leap, host_month_start_index=host_month_start_index
        ),
    }


def comparison_lines(result: dict[str, Any]) -> list[str]:
    row = result["selected_row"]
    key = f"{row['lunar_year']}年{'闰' if row['is_leap_month'] else ''}{row['lunar_month']}月"
    literal = row["author_proposed_decision_literal"]
    limit = row["assumed_limit_units"]
    parts = [
        f"竹迫忍2022/12/27版大衍进朔更新表第{row['row_number']}行"
        f"（PDF第{row['pdf_page']}页）另作具名研究对照：{key}，"
        f"作者表列计算定朔干支{row['computed_new_moon_day_ganzhi_literal']}"
        f"、大余{row['computed_new_moon_day_cycle_index']}、小余{row['computed_new_moon_remainder']}；"
        f"原典栏为{row['original_table_decision_literal']}，作者进退栏为{literal}。"
        "原典栏不是当前NAOJ的同义字段，括号与星号原样保留。"
    ]
    if result["author_proposed_day_shift_from_literal"] is None:
        parts.append(
            "本行作者进退栏留横杠，记为未给结论，未补成不进；"
            f"当前NAOJ月首干支{result['host_month_start_ganzhi']}仍单列，"
            "作者方向所推月首干支与是否相合均留空。"
        )
    else:
        parts.append(
            f"只按作者{'带星号的' if result['author_direction_has_star_qualifier'] else '明确的'}"
            f"{'进一日' if result['author_proposed_day_shift_from_literal'] else '不进'}字面方向，"
            f"将表列大余按六十循环推得月首干支{result['inferred_author_month_start_ganzhi']}；"
            f"当前NAOJ月首干支为{result['host_month_start_ganzhi']}，两者"
            f"{'相合' if result['matches_author_direction_inference'] else '不同'}。"
            "这是表列方向的条件推得，不是另一次观测或实际民用日期校定。"
        )
    if limit is None:
        parts.append("本行想定进朔限未列，未套默认限值。")
    else:
        parts.append(
            f"该行想定限{limit}按大衍一日3040分比较，"
            f"小余{'达到' if result['mechanical_ge_assumed_limit'] else '未达到'}此限；"
            + (
                "不能据此替横杠补定作者进退。"
                if result["author_proposed_day_shift_from_literal"] is None
                else (
                    "机械限值判断与作者方向不同，已保留该例外，未用阈值覆盖作者栏。"
                    if result["author_direction_differs_from_ge_assumed_limit"]
                    else "本行机械限值判断与作者方向相合，不外推为所有月份的统一公式。"
                )
            )
        )
    witness = result.get("selected_original_witness_comparison")
    parts.append(
        "这里只比较所选研究的月首干支，模六十差不认证实际日期差。"
        + (
            "本行两部所选影像的底本异文与校订另列，所引原记录未全部校勘；"
            if witness is not None
            else "作者所引原始记录未独立校勘；"
        )
        + "327行也不是764至861年全部月份；"
        "未改写当前历日、主宿、前月大小或闰小月先后。"
        "大衍3040分不与宣明8400分混算，也未由进朔限确立T1299平明、桧尾半日或现实预测效力。"
    )
    if witness is not None:
        parts.extend(witness_lines(witness))
    return parts
