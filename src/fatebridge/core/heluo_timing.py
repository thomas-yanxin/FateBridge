"""Heluo's small-image annual, monthly and daily *sequences*.

Reference: NLC416-13jh000625-42999, Shanghai Wenming Shuju printing,
volume one, PDF pages 37-40 (printed leaves 25-28). The six-day template
is not silently promoted to a modern Gregorian ephemeris: year boundaries,
intercalary days and the old extra-ke convention remain separate problems.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from fatebridge.core.heluo import _flip_line, _ying, da_yun, yao_name, yao_text
from fatebridge.core.heluo_clock import source_clock_evidence
from fatebridge.core.heluo_hexagrams import GAN, ZHI, lines_to_gua
from fatebridge.core.heluo_texts import (
    text_reading_notes_snapshot,
    text_status_snapshot,
)
from fatebridge.core.zhouyi import classical_hexagram

RULESET_ID = "heluo_xiaoxiang_nlc_sequence_v1"
SOURCE_URL = "https://upload.wikimedia.org/wikipedia/commons/4/4a/NLC416-13jh000625-42999_%E6%B2%B3%E6%B4%9B%E7%90%86%E6%95%B8.pdf"
SOURCE_SHA256 = "fd203ebcd4dc355dbb1ddd3cbee0a72051a2ca6f7a3e0945027690aac8de0b0c"
CYCLE = tuple(GAN[i % 10] + ZHI[i % 12] for i in range(60))


class HeluoYearContextError(ValueError):
    """A chart's selected pillar year disagrees with its supplied Ganzhi."""


def year_context(chart: dict, birth_ganzhi: str) -> dict[str, Any]:
    cycle_year = chart.get("cycleYear")
    if type(cycle_year) is not int or birth_ganzhi not in CYCLE:
        raise HeluoYearContextError("岁运需要已选干支年标签及有效出生年柱。")
    expected = CYCLE[(cycle_year - 4) % 60]
    if birth_ganzhi != expected:
        raise HeluoYearContextError(
            f"岁运年上下文不一致：所用年标签{cycle_year}应为{expected}，实际传入{birth_ganzhi}。"
        )
    return dict(
        cycle_year=cycle_year,
        birth_ganzhi=birth_ganzhi,
        expected_ganzhi=expected,
        matches=True,
        basis="selected_pillar_year_label; not_civil_birth_year_substitution",
    )


def _validate(lines: list[int], pos: int) -> None:
    if len(lines) != 6 or any(type(b) is not int or b not in (0, 1) for b in lines):
        raise ValueError("卦必须是自初爻至上爻的六个0/1整数。")
    if type(pos) is not int or not 1 <= pos <= 6:
        raise ValueError("爻位必须是1至6的整数。")


def _advance(pos: int, count: int = 1) -> int:
    return (pos - 1 + count) % 6 + 1


def _row(before: list[int], changed_pos: Optional[int], pos: int) -> dict[str, Any]:
    after = _flip_line(before, changed_pos) if changed_pos is not None else before[:]
    return {
        "gua": lines_to_gua(after)["name"],
        "lines": after,
        "pos": pos,
        "changed_pos": changed_pos,
        "input_lines": before[:],
    }


def annual_sequence(
    lines: list[int], period_pos: int, start_yang: bool
) -> list[dict[str, Any]]:
    """Six years for a yin line, nine for a yang line; new base per period.

    For a yang period: first year's line is unchanged only for a yang start;
    second year changes its responding line, third returns to the period line,
    then the six positions advance. Parity is that of this period's first year.
    """
    _validate(lines, period_pos)
    if type(start_yang) is not bool:
        raise ValueError("交运首年阴阳必须明确为布尔值。")
    yang_line = bool(lines[period_pos - 1])
    positions = (
        [period_pos, _ying(period_pos), period_pos]
        + [_advance(period_pos, i) for i in range(1, 7)]
        if yang_line
        else [_advance(period_pos, i) for i in range(6)]
    )
    result = []
    current = lines[:]
    for index, pos in enumerate(positions):
        changed = None if yang_line and start_yang and index == 0 else pos
        row = _row(current, changed, pos)
        row["ordinal_in_period"] = index + 1
        result.append(row)
        current = row["lines"][:]
    return result


def selected_timing_snapshot(timing: dict[str, Any]) -> str:
    """Render only selected, calculated sequences with their actual used line.

    No text branch or outcome is chosen here; a template index never becomes a
    civil date. The day row's used position can differ from its changed line.
    """
    if not timing.get("selected_annual"):
        return ""
    texts = ["[指定岁运卦序]"]
    for key, label, value_key, scope in (
        ("selected_annual", "年标签", "year_label", "annual"),
        ("selected_month", "月序", "month_index", "month_ordinal"),
        ("selected_day", "日定式序", "day_index", "day_template_ordinal"),
    ):
        row = timing.get(key)
        if row:
            texts.append(
                f"{label}{row[value_key]}：{row['gua']}，用爻{yao_name(row['lines'], row['pos'])}。"
            )
            selected = next(
                (
                    entry
                    for entry in timing.get("selected_texts", [])
                    if entry["scope"] == scope
                    and (entry["gua"], entry["pos"]) == (row["gua"], row["pos"])
                ),
                None,
            )
            if selected and selected.get("heluo_commentary"):
                text = selected["heluo_commentary"]
                texts.append(f"所用爻文校勘：{text_status_snapshot(text)}。")
                texts.extend(text_reading_notes_snapshot(text))
    texts.append("月序、日定式序尚未桥接实际日期；不据此给出公历或农历应期。")
    return "\n".join(texts)


def monthly_sequence(annual_lines: list[int], annual_pos: int) -> list[dict[str, Any]]:
    """Odd months advance from the annual position; each even is its odd's 應.

    Even-month transformations must not feed the following odd month.
    Indices are the text's ordinal months, not civil month numbers.
    """
    _validate(annual_lines, annual_pos)
    result = []
    current = annual_lines[:]
    for index in range(6):
        pos = _advance(annual_pos, index + 1)
        odd = _row(current, pos, pos)
        odd.update(
            {
                "month_index": index * 2 + 1,
                "parent_month_index": None,
                "rule_id": "odd_month_progressive",
            }
        )
        even = _row(odd["lines"], _ying(pos), _ying(pos))
        even.update(
            {
                "month_index": index * 2 + 2,
                "parent_month_index": index * 2 + 1,
                "rule_id": "even_month_from_corresponding_odd",
            }
        )
        result.extend([odd, even])
        current = odd["lines"][:]
    return result


def daily_template(month_lines: list[int], month_pos: int) -> list[dict[str, Any]]:
    """Five changes from the original month, each with six daily line positions.

    This returns ordinal slots 1..30 only. It does not implement the old extra-ke
    adjustment or assert that a solar/lunar/civil month contains thirty days.
    """
    _validate(month_lines, month_pos)
    result = []
    for block in range(5):
        changed = _advance(month_pos, block + 1)
        for day in range(6):
            row = _row(month_lines, changed, day + 1)
            row.update(
                {
                    "block_index": block + 1,
                    "day_index": block * 6 + day + 1,
                    "rule_id": "daily_block_from_original_month",
                }
            )
            result.append(row)
    return result


def annual_timeline(chart: dict, birth_ganzhi: str) -> list[dict[str, Any]]:
    year_context(chart, birth_ganzhi)
    periods = da_yun(chart["xian"], chart["hou"], chart["cycleYear"])
    result = []
    birth_index = CYCLE.index(birth_ganzhi)
    for index, period in enumerate(periods["all"]):
        start_index = (birth_index + period["ageStart"] - 1) % 60
        start_yang = start_index % 2 == 0
        for row in annual_sequence(period["lines"], period["pos"], start_yang):
            age = period["ageStart"] + row["ordinal_in_period"] - 1
            result.append(
                {
                    **row,
                    "age": age,
                    "year_label": chart["cycleYear"] + age - 1,
                    "ganzhi": CYCLE[(birth_index + age - 1) % 60],
                    "phase": "xian" if index < 6 else "hou",
                    "period_index": index + 1,
                    "period_pos": period["pos"],
                    "period_start_yang": start_yang,
                }
            )
    return result


def _selected_text(row: dict[str, Any], scope: str) -> dict[str, Any]:
    reference = classical_hexagram("".join(str(v) for v in row["lines"]))
    return {
        "scope": scope,
        "gua": row["gua"],
        "pos": row["pos"],
        "corpus_key": f"{row['gua']}.yao.{row['pos']}",
        "heluo_commentary": deepcopy(yao_text(row["gua"], row["pos"]) or {}),
        "zhouyi_verse": deepcopy(reference["yaoci"][row["pos"] - 1]),
        "zhouyi_source_url": reference["source_url"],
        "zhouyi_source_sha256": reference["source_wikitext_sha256"],
        "branch_selection": "no_automatic_xie_or_buxie_selection",
    }


def build_heluo_timing(
    chart: dict,
    birth_ganzhi: str,
    *,
    analysis_year: Optional[int] = None,
    month_index: Optional[int] = None,
    day_index: Optional[int] = None,
) -> dict[str, Any]:
    if month_index is not None and (
        type(month_index) is not int
        or not 1 <= month_index <= 12
        or analysis_year is None
    ):
        raise ValueError("month_index须为1至12，且必须指定analysis_year年标签。")
    if day_index is not None and (
        type(day_index) is not int or not 1 <= day_index <= 30 or month_index is None
    ):
        raise ValueError("day_index须为1至30的定式序号，且必须指定month_index。")
    if analysis_year is not None and type(analysis_year) is not int:
        raise ValueError("analysis_year必须是干支年对应的整数年标签。")
    rows = annual_timeline(chart, birth_ganzhi)
    result: dict[str, Any] = {
        "ruleset_id": RULESET_ID,
        "ruleset_version": "1.1.0",
        "source_title": "河洛理數（上海文明書局印行本）卷一",
        "source_url": SOURCE_URL,
        "source_pdf_sha256": SOURCE_SHA256,
        "source_pdf_pages": [37, 38, 39, 40],
        "scope": "collated_sequences_and_source_clock_arithmetic; full_calendar_mapping_pending",
        "year_context": year_context(chart, birth_ganzhi),
        "source_clock": source_clock_evidence(),
        "calendar_policy": {
            "year": "birth_pillar_year_label_plus_ordinal_age; exact_new_year_boundary_unresolved",
            "month": "ordinal_classical_month_1_to_12; not_Gregorian_month",
            "day": "ordinal_30_slot_template; not_Gregorian_or_lunar_day",
            "extra_ke_and_intercalation": "source_count_arithmetic_available; physical_epoch_fen_scale_and_intercalation_unresolved",
            "month_anchor": "active_annual_line_position_v1; alternate_natal_yuantang_reading_not_merged",
        },
        "annual_rows": rows,
        "selected_annual": None,
        "monthly_rows": [],
        "selected_month": None,
        "daily_template": [],
        "selected_day": None,
        "selected_texts": [],
        "prediction_validation": "not_validated",
    }
    if analysis_year is None:
        return result
    annual = next((r for r in rows if r["year_label"] == analysis_year), None)
    if annual is None:
        raise ValueError(
            f"analysis_year超出本次两卦年序范围{rows[0]['year_label']}至{rows[-1]['year_label']}；不外推。"
        )
    result["selected_annual"] = deepcopy(annual)
    result["selected_texts"].append(_selected_text(annual, "annual"))
    months = monthly_sequence(annual["lines"], annual["pos"])
    result["monthly_rows"] = months
    if month_index is None:
        return result
    month = months[month_index - 1]
    result["selected_month"] = deepcopy(month)
    result["selected_texts"].append(_selected_text(month, "month_ordinal"))
    days = daily_template(month["lines"], month["pos"])
    result["daily_template"] = days
    if day_index is not None:
        result["selected_day"] = deepcopy(days[day_index - 1])
        result["selected_texts"].append(
            _selected_text(days[day_index - 1], "day_template_ordinal")
        )
    return result
