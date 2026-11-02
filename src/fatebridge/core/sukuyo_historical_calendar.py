"""Named NAOJ historical month-start reference with retained source variants.

Gregorian reference labels and fixed UTC+09 are explicit conventions. They do
not reconstruct historical local clocks or certify the early chronology.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fatebridge.core.sukuyo_dayan_advance import (
    comparison_lines,
    month_comparison,
    research_scope,
    scope_lines,
)
from fatebridge.core.sukuyo_dayan_reconstruction import (
    reconstruct_new_moon,
    reconstruction_lines,
)
from fatebridge.core.sukuyo_naoj_adjustments import (
    adjustment_lines,
    month_adjustment_reference,
)
from fatebridge.core.sukuyo_sandaikaku import month_reference as sandaikaku_reference
from fatebridge.core.sukuyo_sandaikaku import reference_lines as sandaikaku_lines
from fatebridge.core.sukuyo_shogonji import header_reading, month_header_reference
from fatebridge.core.sukuyo_shogonji_daily import (
    daily_annotation_reading,
    daily_annotation_reference,
)
from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_japanese_historical_v1.json"
LINEAGE_SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_calendar_lineage.json"
)
REFORM_MONTH = date(1872, 12, 30).toordinal()
DAY_CYCLE = tuple(
    "甲乙丙丁戊己庚辛壬癸"[n % 10] + "子丑寅卯辰巳午未申酉戌亥"[n % 12]
    for n in range(60)
)


@dataclass(frozen=True)
class _Table:
    starts: tuple[int, ...]
    rows: tuple[tuple[int, int, bool, int], ...]
    first: date
    last: date
    sha256: str
    metadata_json: str
    query_hashes: tuple[str, ...]
    difference_starts: tuple[int, ...]
    differences_json: tuple[str, ...]


@lru_cache(maxsize=4)
def _table(path: Path) -> _Table:
    record = load_source(path)
    bundle = record.data
    starts, rows = [], []
    previous_end = None
    previous_label = None
    for ordinal, year, month, leap, length in bundle["months"]:
        if (
            any(type(value) is not int for value in (ordinal, year, month, length))
            or type(leap) is not bool
            or not 0 <= year <= 1872
            or not 1 <= month <= 12
            or (
                length not in (29, 30) and not (ordinal == REFORM_MONTH and length == 2)
            )
        ):
            raise ValueError("Invalid NAOJ historical reference month")
        if previous_end is not None and ordinal != previous_end:
            raise ValueError("NAOJ historical month periods are not contiguous")
        if previous_label is not None:
            py, pm, pl = previous_label
            expected = (py + 1, 1) if pm == 12 else (py, pm + 1)
            if (leap and (pl or (year, month) != (py, pm))) or (
                not leap and (year, month) != expected
            ):
                raise ValueError("NAOJ historical lunar month sequence changed")
        starts.append(ordinal)
        rows.append((year, month, leap, length))
        previous_end = ordinal + length
        previous_label = (year, month, leap)
    first, last = map(date.fromisoformat, bundle["supported_range_inclusive"])
    if (
        first != date(1, 1, 1)
        or last != date(1872, 12, 31)
        or not starts
        or starts[0] > first.toordinal()
        or starts[0] + rows[0][3] <= first.toordinal()
        or previous_end != last.toordinal() + 1
        or sum(length for year, month, leap, length in rows)
        - (first.toordinal() - starts[0])
        != bundle["reference_day_count"]
    ):
        raise ValueError("NAOJ historical table does not cover its declared domain")
    query_hashes = bundle["source_query_response_sha256"]
    if set(query_hashes) != {str(year) for year in range(1873)} or any(
        not re.fullmatch(r"[0-9a-f]{64}", value) for value in query_hashes.values()
    ):
        raise ValueError("Historical source query fingerprints are incomplete")
    anchor = bundle["day_cycle_anchor"]
    if (
        not isinstance(anchor, dict)
        or set(anchor)
        != {
            "civil_ordinal",
            "day_ganzhi",
            "source_lunar_year_query",
            "source_response_sha256",
        }
        or type(anchor["civil_ordinal"]) is not int
        or anchor["civil_ordinal"] != starts[0]
        or anchor["day_ganzhi"] not in DAY_CYCLE
        or type(anchor["source_lunar_year_query"]) is not int
        or anchor["source_lunar_year_query"] != rows[0][0]
        or anchor["source_response_sha256"] != query_hashes[str(rows[0][0])]
    ):
        raise ValueError("Historical day-cycle anchor is not bound to its source month")
    differences = bundle["cross_source_disagreement_intervals"]
    difference_starts, serialized = [], []
    previous_end = 0
    for row in differences:
        begin, end = map(date.fromisoformat, (row["start"], row["end_inclusive"]))
        if (
            begin.toordinal() <= previous_end
            or not first <= begin <= end <= last
            or row["days"] != (end - begin).days + 1
        ):
            raise ValueError(
                "Historical source-variant intervals overlap or exceed the domain"
            )
        difference_starts.append(begin.toordinal())
        serialized.append(json.dumps(row, ensure_ascii=False))
        previous_end = end.toordinal()
    metadata = {
        key: value
        for key, value in bundle.items()
        if key
        not in {
            "months",
            "source_query_response_sha256",
            "cross_source_disagreement_intervals",
        }
    }
    metadata["retained_disagreement_interval_count"] = len(differences)
    return _Table(
        tuple(starts),
        tuple(rows),
        first,
        last,
        record.sha256,
        json.dumps(metadata, ensure_ascii=False),
        tuple(query_hashes[str(year)] for year in range(1873)),
        tuple(difference_starts),
        tuple(serialized),
    )


def supported_range() -> tuple[date, date]:
    table = _table(SOURCE)
    return table.first, table.last


def reference_metadata() -> dict[str, Any]:
    table = _table(SOURCE)
    return {
        **json.loads(table.metadata_json),
        "source_bundle_sha256": table.sha256,
        "source_independence_reference": source_independence_reference(),
    }


def source_independence_reference() -> dict[str, Any]:
    """Carry the actual declared overlap, without claiming identical editions."""
    loaded = load_source(LINEAGE_SOURCE)
    data = loaded.data
    rows = data["provider_statements"]
    if len(rows) != 2 or {row["provider"] for row in rows} != {"NAOJ", "HuTime"}:
        raise ValueError("历日来源关系须保留两家提供方的具名说明")
    shared = sorted(
        set(rows[0]["selected_bibliographic_titles"])
        & set(rows[1]["selected_bibliographic_titles"])
    )
    if shared != data["shared_bibliographic_titles"]:
        raise ValueError("共同书目未绑定两家提供方的实际声明")
    return {**data, "source_bundle_sha256": loaded.sha256}


def _fields(table: _Table, civil: date) -> tuple[int, int, int, bool, int]:
    if not table.first <= civil <= table.last:
        raise ValueError(
            f"NAOJ日本历史参考仅支持{table.first}至{table.last}；不补其他历法或延长被改历截断的月份"
        )
    index = bisect_right(table.starts, civil.toordinal()) - 1
    year, month, leap, _ = table.rows[index]
    return year, month, civil.toordinal() - table.starts[index] + 1, leap, index


def lunar_fields(civil: date) -> tuple[int, int, int, bool]:
    year, month, day, leap, _ = _fields(_table(SOURCE), civil)
    return year, month, day, leap


def compatibility_reference_notes(
    contexts: list[dict[str, Any]], names: list[str]
) -> str:
    """Retain each computed branch's historical conditions in native prose."""
    lines = [
        "采用NAOJ冻结月首及前推公历标签、固定UTC+09参考日期；未复原历史地方钟时或实际颁历。原典配宿为本次回推查表，不表示该年代已行用本经。"
    ]
    seen_sources: set[str] = set()
    for context, name in zip(contexts, names):
        for branch in context.get("calendar_candidates") or [context]:
            source = branch["calendar_reference"]
            source_id = source["source_bundle_sha256"]
            if source_id not in seen_sources:
                seen_sources.add(source_id)
                start, end = source["supported_range_inclusive"]
                origins = source["source_provenance"]
                early = next(r for r in origins if "lunar_year_end" in r)
                later = next(r for r in origins if "lunar_year_begin" in r)
                lineage = source["source_independence_reference"]
                shared_titles = "、".join(lineage["shared_bibliographic_titles"])
                lines.append(
                    f"本冻结历表支持前推公历{start}至{end}，阴历纪年{early['lunar_year_end']}年及以前为仪凤历平朔回推，"
                    f"{later['lunar_year_begin']}年起仍是推算并按历史资料校订的参考。"
                    f"全表保留跨来源分歧{source['cross_source_disagreement_dates']}日、"
                    f"{source['retained_disagreement_interval_count']}个区间；两提供方的方法说明均列《{shared_titles}》，"
                    "两来源部分共用历史文献仅指这项已声明的共同书目，不证明具体版本或逐条依赖相同，也未完成全范围独立核验。"
                )
            label = f"{name}的参考日期{branch['calendar_date']}"
            if source.get("edo_calendar_method_reference") is not None:
                from fatebridge.core.sukuyo_edo_calendar import reading_lines

                lines.append(label + "：")
                lines.extend(reading_lines(source["edo_calendar_method_reference"]))
            cycle = source["day_ganzhi_reference"]
            anchor = cycle["source_anchor"]
            lines.append(
                f"{label}的参考日干支为{cycle['name']}，锚点为民用日序{anchor['civil_ordinal']}的{anchor['day_ganzhi']}，"
                f"相隔{cycle['elapsed_civil_days']}个民用日按六十循环递推；按固定UTC+09民用午夜换日，未作为八字日柱或古代日界。"
                f"锚点的阴历年查询{anchor['source_lunar_year_query']}是来源上下文，不开放公历年零出生输入。"
            )
            if source.get("early_weekday_documentary_comparison"):
                from fatebridge.core.sukuyo_koya_preface import (
                    dated_weekday_reading_lines,
                )

                lines.append(label + "：")
                lines.extend(
                    dated_weekday_reading_lines(
                        source["early_weekday_documentary_comparison"]
                    )
                )
            if source.get("early_weekday_editorial_comparison"):
                from fatebridge.core.sukuyo_koya_preface import (
                    editorial_weekday_reading_lines,
                )

                lines.append(label + "：")
                lines.extend(
                    editorial_weekday_reading_lines(
                        source["early_weekday_editorial_comparison"]
                    )
                )
            if source.get("manuscript_month_header"):
                lines.extend(
                    header_reading(
                        source["manuscript_month_header"],
                        branch.get("profile_calculation"),
                    )
                )
            if source.get("manuscript_daily_annotations"):
                lines.append(label + "：")
                lines.extend(
                    daily_annotation_reading(source["manuscript_daily_annotations"])
                )
            research = source.get("dayan_advance_research_comparison")
            adjustment = source.get("published_calendar_adjustment_reference")
            if adjustment is not None:
                lines.append(label + "：")
                lines.extend(adjustment_lines(adjustment))
            if research is not None:
                lines.append(label + "：")
                lines.extend(comparison_lines(research))
            nominal_moon = source.get("dayan_nominal_new_moon_model")
            if nominal_moon is not None:
                lines.append(label + "：")
                lines.extend(reconstruction_lines(nominal_moon))
            research_context = source.get("dayan_advance_research_scope")
            if research_context is not None:
                lines.extend(scope_lines(research_context, research))
            edict = source.get("sandaikaku_edict_reference")
            if edict is not None or research_context is not None:
                lines.extend(sandaikaku_lines(edict))
            if (
                source["date_provenance"]
                == "naoj_reconstructed_gihou_mean_new_moons_not_contemporary_observation"
            ):
                lines.append(f"{label}属仪凤历平朔回推，非当年实测或已证实颁历。")
            if source["month_truncated_by_calendar_reform"]:
                lines.append(f"{label}所在旧历十二月因明治改历截为两天。")
            comparison = source.get("cross_source_comparison")
            if comparison:
                primary, control = (
                    comparison["reference_fields"],
                    comparison["control_fields"],
                )

                def printed(fields: list[Any]) -> str:
                    return f"{fields[0]}年{'闰' if fields[3] else ''}{fields[1]}月{fields[2]}日"

                lines.append(
                    f"{label}按NAOJ为{printed(primary)}，HuTime1001.1为{printed(control)}，与所选NAOJ参考不同；分歧保留且未代入主宿，共同书目及其适用限制另列。"
                )
            else:
                lines.append(
                    f"{label}在NAOJ／HuTime1001.1既有对照中未列跨来源分歧记录；"
                    "不等于已获独立一致性验证，也未凭空判定这两家此日发生来源冲突。"
                )
    return "".join(lines)


def date_reference(civil: date) -> dict[str, Any]:
    table = _table(SOURCE)
    year, month, day, leap, index = _fields(table, civil)
    params = {
        "type": "2",
        "gengo": "a000",
        "year": str(year),
        "month": "1",
        "day": "1",
        "jg": "1",
        "div": "1",
        "divu": "3",
        "len": "400",
        "lenu": "3",
        "gen": "1",
        "csv": "CSV",
    }
    metadata = {**json.loads(table.metadata_json), "source_bundle_sha256": table.sha256}
    lineage = source_independence_reference()
    anchor = metadata["day_cycle_anchor"]
    elapsed = civil.toordinal() - anchor["civil_ordinal"]
    ganzhi = DAY_CYCLE[(DAY_CYCLE.index(anchor["day_ganzhi"]) + elapsed) % 60]
    comparison = None
    variant_index = bisect_right(table.difference_starts, civil.toordinal()) - 1
    if variant_index >= 0:
        variant = json.loads(table.differences_json[variant_index])
        begin = date.fromisoformat(variant["start"])
        if civil <= date.fromisoformat(variant["end_inclusive"]):
            alternative = variant["hutime_first_fields"]
            if alternative is not None:
                alternative[2] += (civil - begin).days
            comparison = {
                "reference_provider": "NAOJ",
                "control_provider": "HuTime 1001.1",
                "reference_fields": [year, month, day, leap],
                "control_fields": alternative,
                "control_applied_to_primary": False,
                "partly_shared_historical_source_corpus": bool(
                    lineage["shared_bibliographic_titles"]
                ),
                "scope": "Separate publisher/implementation control; retained disagreement is not resolved by replacing the selected NAOJ facts.",
            }
    result = {
        **metadata,
        "source_independence_reference": lineage,
        "date_source_uri": metadata["source_url"] + "?" + urlencode(params),
        "source_response_sha256": table.query_hashes[year],
        "source_month_start_ordinal": table.starts[index],
        "source_month_length_days": table.rows[index][3],
        "day_ganzhi_reference": {
            "name": ganzhi,
            "method_id": "naoj_printed_anchor_plus_civil_ordinal_delta_mod60_v1",
            "source_anchor": anchor,
            "elapsed_civil_days": elapsed,
            "reference_boundary": "fixed_utc09_civil_midnight",
            "historical_day_boundary_accepted": False,
            "bazi_day_pillar_evaluated": False,
        },
        "month_truncated_by_calendar_reform": table.starts[index] == REFORM_MONTH,
        "date_provenance": (
            "naoj_reconstructed_gihou_mean_new_moons_not_contemporary_observation"
            if year <= 453
            else "naoj_calculated_and_historically_corrected_japanese_calendar_reference"
        ),
        "printed_lunar_year": year,
        "lunar_year_is_gregorian_era_year": False,
        "calendar_reference_timezone": "UTC+09:00",
        "historical_local_time_reconstruction": False,
        "cross_source_comparison": comparison,
        "published_calendar_adjustment_reference": month_adjustment_reference(
            year,
            month,
            leap,
            table.starts[index],
            DAY_CYCLE[
                (
                    DAY_CYCLE.index(anchor["day_ganzhi"])
                    + table.starts[index]
                    - anchor["civil_ordinal"]
                )
                % 60
            ],
        ),
        "sandaikaku_edict_reference": sandaikaku_reference(year, month, leap),
        "dayan_advance_research_scope": (
            research_scope() if 764 <= year <= 861 else None
        ),
        "dayan_nominal_new_moon_model": (
            reconstruct_new_moon(table.starts[index], year)
            if 764 <= year <= 861
            else None
        ),
        "dayan_advance_research_comparison": month_comparison(
            year,
            month,
            leap,
            host_month_start_index=(
                DAY_CYCLE.index(anchor["day_ganzhi"])
                + table.starts[index]
                - anchor["civil_ordinal"]
            )
            % 60,
        ),
    }
    from fatebridge.core.sukuyo_edo_calendar import calendar_method_reference

    edo = calendar_method_reference(year, month, leap)
    if edo is not None:
        result["edo_calendar_method_reference"] = edo
    from fatebridge.core.sukuyo_koya_preface import (
        dated_weekday_reference,
        editorial_weekday_reference,
    )

    documentary = dated_weekday_reference(civil, (year, month, day, leap), result)
    if documentary is not None:
        result["early_weekday_documentary_comparison"] = documentary
    editorial = editorial_weekday_reference(civil, (year, month, day, leap), result)
    if editorial is not None:
        result["early_weekday_editorial_comparison"] = editorial
    header = month_header_reference(year, month, leap, day)
    if header is not None:
        result["manuscript_month_header"] = header
    daily = daily_annotation_reference(year, month, leap, day)
    if daily is not None:
        result["manuscript_daily_annotations"] = daily
    return result
