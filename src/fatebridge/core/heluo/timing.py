"""Consolidated Heluo small-image timing, modern Gregorian year mapping, and source clock arithmetic."""

from __future__ import annotations

import json
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import _solar_terms_for_context_year
from fatebridge.core.heluo.chart import _flip_line, _ying, assess_nayin_relation, da_yun
from fatebridge.core.heluo.texts import GAN, ZHI, lines_to_gua, yao_text
from fatebridge.core.zhouyi import classical_hexagram
from fatebridge.utils.errors import NumerologySourceError

RULESET_ID = "heluo_xiaoxiang_nlc_sequence_v1"
CLOCK_RULESET_ID = "heluo_wenming_baike_clock_v1"
CLOCK_SOURCE_PATH = Path(__file__).resolve().parents[2] / "data/heluo/clock-v1.json"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
LONG_BRANCHES = ("寅", "申", "巳", "亥")
CYCLE = tuple(GAN[i % 10] + ZHI[i % 12] for i in range(60))


class HeluoYearContextError(ValueError):
    """A chart's selected pillar year disagrees with its supplied Ganzhi."""


@lru_cache(maxsize=1)
def _clock_source() -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(CLOCK_SOURCE_PATH.read_bytes())
        expected = dict(
            day_ke=100,
            twelve_base_total_ke=96,
            extra_branch_ke=9,
            nominal_year_days=360,
            printed_year_days=365,
            extra_month_shi=5,
            months=12,
            extra_year_shi=60,
            daily_extra_ke=1,
            daily_extra_fen=7,
            block_nominal_days=6,
            block_extra_shi=1,
        )
        if (
            data["ruleset_id"] != CLOCK_RULESET_ID
            or data["version"] != "1.0.0"
            or data["source_pdf_pages"] != [41]
            or data["extra_branches_in_printed_order"] != list(LONG_BRANCHES)
            or data["source_fen_per_ke"] is not None
            or any(
                type(data[k]) is not int or data[k] != n for k, n in expected.items()
            )
        ):
            raise ValueError("所选百刻原句或未定分制被改写。")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_clock_source") from exc
    return data


def _ratio(value: Fraction) -> dict[str, int]:
    return dict(numerator=value.numerator, denominator=value.denominator)


def source_branch_partition(*, origin_branch: str) -> list[dict[str, Any]]:
    source = _clock_source()
    if (
        not isinstance(origin_branch, str)
        or len(origin_branch) != 1
        or origin_branch not in BRANCHES
    ):
        raise ValueError("须明确指定有效时支原点；不默认子初或子正。")
    start = BRANCHES.index(origin_branch)
    rows = []
    cursor = 0
    for i in range(12):
        branch = BRANCHES[(start + i) % 12]
        length = (
            source["extra_branch_ke"]
            if branch in LONG_BRANCHES
            else source["twelve_base_total_ke"] // 12
        )
        rows.append(
            dict(
                branch=branch, start_ke=cursor, end_ke=cursor + length, length_ke=length
            )
        )
        cursor += length
    if cursor != source["day_ke"]:
        raise NumerologySourceError("invalid_heluo_clock_source")
    return rows


def source_branch_at_ke(value: int | Fraction, *, origin_branch: str) -> dict[str, Any]:
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValueError("源刻须为整数或精确Fraction，不能用布尔或浮点近似。")
    value = Fraction(value)
    source = _clock_source()
    if not 0 <= value < source["day_ke"]:
        raise ValueError("单周期源刻须在[0,100)；下一周期不能静默折回。")
    for row in source_branch_partition(origin_branch=origin_branch):
        if row["start_ke"] <= value < row["end_ke"]:
            return {
                "origin_branch": origin_branch,
                "source_ke": _ratio(value),
                "branch": row["branch"],
                "branch_start_ke": row["start_ke"],
                "branch_end_ke": row["end_ke"],
                "offset_in_branch_ke": _ratio(value - row["start_ke"]),
            }
    raise NumerologySourceError("invalid_heluo_clock_source")


def compare_daily_extra(*, fen_per_ke: int) -> dict[str, Any]:
    if type(fen_per_ke) is not int or fen_per_ke <= 0:
        raise ValueError("须明确指定正整数分/刻尺度。")
    source = _clock_source()
    daily = Fraction(source["daily_extra_ke"]) + Fraction(
        source["daily_extra_fen"], fen_per_ke
    )
    expected = Fraction(
        (source["printed_year_days"] - source["nominal_year_days"]) * source["day_ke"],
        source["nominal_year_days"],
    )
    return {
        "fen_per_ke": fen_per_ke,
        "daily_extra_ke": _ratio(daily),
        "year_extra_ke": _ratio(daily * source["nominal_year_days"]),
        "equal_shi_year_extra_ke": _ratio(expected * source["nominal_year_days"]),
        "matches_equal_shi_year_closure": daily == expected,
    }


def source_six_day_blocks(*, origin_branch: str, blocks: int) -> list[dict[str, Any]]:
    if type(blocks) is not int or blocks <= 0:
        raise ValueError("块数须为正整数。")
    if origin_branch not in BRANCHES:
        raise ValueError("须明确指定有效时支原点。")
    source = _clock_source()
    start = BRANCHES.index(origin_branch)
    return [
        {
            "block_index": idx + 1,
            "nominal_day_start": idx * source["block_nominal_days"],
            "nominal_day_end": (idx + 1) * source["block_nominal_days"],
            "origin_branch": BRANCHES[(start + idx) % 12],
        }
        for idx in range(blocks)
    ]


def source_clock_evidence() -> dict[str, Any]:
    source = _clock_source()
    ordinary = source["twelve_base_total_ke"] // 12
    expected_extra = Fraction(
        (source["printed_year_days"] - source["nominal_year_days"]) * source["day_ke"],
        source["nominal_year_days"],
    )
    required = Fraction(
        source["daily_extra_fen"], expected_extra - source["daily_extra_ke"]
    )
    return {
        "ruleset_id": source["ruleset_id"],
        "version": source["version"],
        "source_title": source["source_title"],
        "review_status": source["review_status"],
        "source_pdf_pages": source["source_pdf_pages"][:],
        "day_ke": source["day_ke"],
        "base_ke": source["twelve_base_total_ke"],
        "extra_ke": source["day_ke"] - source["twelve_base_total_ke"],
        "branch_lengths": [
            dict(
                branch=b,
                length_ke=source["extra_branch_ke"] if b in LONG_BRANCHES else ordinary,
            )
            for b in BRANCHES
        ],
        "extra_branches_in_printed_order": list(LONG_BRANCHES),
        "physical_origin_branch": None,
        "daily_extra_literal": dict(
            ke=source["daily_extra_ke"], fen=source["daily_extra_fen"], fen_per_ke=None
        ),
        "annual_extra_literal": dict(
            nominal_days=source["nominal_year_days"],
            printed_days=source["printed_year_days"],
            monthly_extra_shi=source["extra_month_shi"],
            months=source["months"],
            annual_extra_shi=source["extra_year_shi"],
        ),
        "branch_shift_projection": dict(
            year_blocks=source["nominal_year_days"] // source["block_nominal_days"],
            extra_shi=source["extra_year_shi"],
            extra_ke=(source["extra_year_shi"] // 12) * source["day_ke"],
            total_source_days=_ratio(
                Fraction(source["nominal_year_days"])
                + Fraction(source["extra_year_shi"], 12)
            ),
            origin_basis="full_cycles_total_invariant; no_physical_origin_selected",
            branch_start_only=True,
            derived_only=True,
            source_fen_scale_selected=False,
            daily_internal_distribution_resolved=False,
        ),
        "equal_shi_projection": dict(
            extra_ke_per_nominal_day=_ratio(expected_extra),
            fen_per_ke_required_for_numeric_closure=_ratio(required),
            derived_only=True,
            source_fen_scale_verified=False,
        ),
        "physical_clock_applied": False,
        "calendar_mapping_complete": False,
    }


def attach_clock_evidence(
    evidence: dict[str, Any], profile: dict[str, Any], context: dict[str, Any]
) -> None:
    del context
    evidence["rulesets"].append(
        {
            "ruleset_id": profile["ruleset_id"],
            "version": profile["version"],
            "source_title": profile["source_title"],
            "source_status": profile["review_status"],
        }
    )


def year_context(chart: dict[str, Any], birth_ganzhi: str) -> dict[str, Any]:
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


def _row(before: list[int], changed_pos: int | None, pos: int) -> dict[str, Any]:
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


def monthly_sequence(annual_lines: list[int], annual_pos: int) -> list[dict[str, Any]]:
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


def annual_timeline(
    chart: dict[str, Any], birth_ganzhi: str, *, compact: bool = False
) -> list[dict[str, Any]]:
    year_context(chart, birth_ganzhi)
    periods = da_yun(chart["xian"], chart["hou"], chart["cycleYear"])
    result = []
    birth_index = CYCLE.index(birth_ganzhi)
    for index, period in enumerate(periods["all"]):
        start_index = (birth_index + period["ageStart"] - 1) % 60
        start_yang = start_index % 2 == 0
        for row in annual_sequence(period["lines"], period["pos"], start_yang):
            age = period["ageStart"] + row["ordinal_in_period"] - 1
            gz = CYCLE[(birth_index + age - 1) % 60]
            if compact:
                result.append(
                    {
                        "year_label": chart["cycleYear"] + age - 1,
                        "ganzhi": gz,
                        "gua": row["gua"],
                        "pos": row["pos"],
                    }
                )
            else:
                result.append(
                    {
                        **row,
                        "age": age,
                        "year_label": chart["cycleYear"] + age - 1,
                        "ganzhi": gz,
                        "phase": "xian" if index < 6 else "hou",
                        "period_index": index + 1,
                        "period_pos": period["pos"],
                        "period_start_yang": start_yang,
                    }
                )
    return result


def _selected_annual_from_chart(
    chart: dict[str, Any], birth_ganzhi: str, target_year: int
) -> dict[str, Any]:
    """Compute full annual row for ``target_year`` in a single pass."""
    year_context(chart, birth_ganzhi)
    periods = da_yun(chart["xian"], chart["hou"], chart["cycleYear"])
    birth_index = CYCLE.index(birth_ganzhi)
    min_y = chart["cycleYear"]
    max_y = chart["cycleYear"] + sum(p["years"] for p in periods["all"]) - 1
    if not min_y <= target_year <= max_y:
        raise ValueError(f"analysis_year超出本次两卦年序范围{min_y}至{max_y}；不外推。")
    for index, period in enumerate(periods["all"]):
        end_y = chart["cycleYear"] + period["ageEnd"] - 1
        start_y = chart["cycleYear"] + period["ageStart"] - 1
        if not start_y <= target_year <= end_y:
            continue
        start_index = (birth_index + period["ageStart"] - 1) % 60
        start_yang = start_index % 2 == 0
        for row in annual_sequence(period["lines"], period["pos"], start_yang):
            age = period["ageStart"] + row["ordinal_in_period"] - 1
            y_label = chart["cycleYear"] + age - 1
            if y_label == target_year:
                return {
                    **row,
                    "age": age,
                    "year_label": y_label,
                    "ganzhi": CYCLE[(birth_index + age - 1) % 60],
                    "phase": "xian" if index < 6 else "hou",
                    "period_index": index + 1,
                    "period_pos": period["pos"],
                    "period_start_yang": start_yang,
                }
    raise ValueError("analysis_year超出本次两卦年序范围；不外推。")


def _selected_text(row: dict[str, Any], scope: str) -> dict[str, Any]:
    reference = classical_hexagram("".join(str(v) for v in row["lines"]))
    raw = yao_text(row["gua"], row["pos"]) or {}
    compact_commentary = {
        k: raw[k] for k in ("yaoci", "xiang", "detail", "shige") if k in raw
    }
    return {
        "scope": scope,
        "gua": row["gua"],
        "pos": row["pos"],
        "corpus_key": f"{row['gua']}.yao.{row['pos']}",
        "heluo_commentary": compact_commentary,
        "zhouyi_verse": deepcopy(reference["yaoci"][row["pos"] - 1]),
    }


def _gregorian_lichun_bounds(year: int, zone: str) -> dict[str, Any]:
    """Lazily compute exact Lichun start/end bounds for a modern Gregorian analysis_year."""
    start = _solar_terms_for_context_year(year, zone, year, term_index=2)[0]
    end = _solar_terms_for_context_year(year + 1, zone, year + 1, term_index=2)[0]
    return {
        "gregorian_year": year,
        "timezone": zone,
        "lichun_start_at": start.calendar.isoformat(),
        "lichun_end_at": end.calendar.isoformat(),
    }


def build_heluo_timing(
    chart: dict[str, Any],
    birth_ganzhi: str,
    *,
    analysis_year: int | None = None,
    month_index: int | None = None,
    day_index: int | None = None,
    timezone: str = "+08:00",
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

    compact_rows = annual_timeline(chart, birth_ganzhi, compact=True)
    result: dict[str, Any] = {
        "ruleset_id": RULESET_ID,
        "year_context": year_context(chart, birth_ganzhi),
        "annual_rows": compact_rows,
        "selected_annual": None,
        "monthly_rows": [],
        "selected_month": None,
        "daily_template": [],
        "selected_day": None,
        "selected_texts": [],
    }
    if analysis_year is None:
        return result

    annual = _selected_annual_from_chart(chart, birth_ganzhi, analysis_year)
    annual_payload = {
        k: annual[k]
        for k in (
            "age",
            "year_label",
            "ganzhi",
            "gua",
            "pos",
            "changed_pos",
            "phase",
            "period_index",
        )
    }
    annual_payload["nayin_fortune"] = assess_nayin_relation(
        birth_ganzhi, annual["ganzhi"]
    )
    if 1700 <= analysis_year <= 2500:
        annual_payload["gregorian_bounds"] = _gregorian_lichun_bounds(
            analysis_year, timezone
        )
    result["selected_annual"] = annual_payload
    result["selected_texts"].append(_selected_text(annual, "annual"))
    months = monthly_sequence(annual["lines"], annual["pos"])
    result["monthly_rows"] = [
        {k: m[k] for k in ("month_index", "gua", "pos", "changed_pos")} for m in months
    ]
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
