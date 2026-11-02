"""Published provider adjustments, distinct from a newly computed calendar.

All monthly rows of the captured NAOJ page are retained. Its solar adjustments
and early two-calendar comparison are catalogued separately, never guessed
into month bindings. A listed correction is not applied a second time.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_naoj_adjustments.json"
CANONICAL_SHA256 = "91eecac3e94bd9069fd7e5ed2046d0295d987cd4a070971c9ed5f929a9f9e0fd"


@lru_cache(maxsize=None)
def _source(path: Path) -> tuple[str, dict[tuple[int, int, bool], tuple[str, ...]]]:
    """Index one process source snapshot; return only detached public records."""
    loaded = load_source(path)
    data = loaded.data
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != CANONICAL_SHA256:
        raise ValueError("NAOJ公开校订目录已改变，须重新核验完整来源与月键")
    header = {
        "ruleset_id": data["id"],
        "source_bundle_sha256": loaded.sha256,
        "source": data["source"],
        "date_convention_source": data["date_convention_source"],
        "complete_published_table_counts": data["counts"],
        "scope": data["scope"],
    }
    index: dict[tuple[int, int, bool], tuple[str, ...]] = {}
    for row in data["monthly_rows"]:
        key = tuple(row["after_month_key"])
        index[key] = index.get(key, ()) + (json.dumps(row, ensure_ascii=False),)
    return json.dumps(header, ensure_ascii=False), index


def month_adjustment_reference(
    year: int, month: int, leap: bool, host_start_ordinal: int, host_start_ganzhi: str
) -> dict[str, Any]:
    header, index = _source(SOURCE)
    key = [year, month, leap]
    rows = []
    for text in index.get((year, month, leap), ()):
        row = json.loads(text)
        after = row["after_start"]
        date_matches = (
            None if after is None else after["civil_ordinal"] == host_start_ordinal
        )
        cycle_matches = (
            None if after is None else after["ganzhi_literal"] == host_start_ganzhi
        )
        rows.append(
            {
                **row,
                "selected_host_start_ordinal": host_start_ordinal,
                "selected_host_start_ganzhi": host_start_ganzhi,
                "published_after_date_matches_selected_host": date_matches,
                "published_after_cycle_matches_selected_host": cycle_matches,
                "binding_state": (
                    "published_label_only_no_civil_start_in_row"
                    if after is None
                    else (
                        "same_published_post_adjustment_date_and_cycle"
                        if date_matches and cycle_matches
                        else "published_post_adjustment_disagrees_with_selected_host"
                    )
                ),
            }
        )
    return {
        **json.loads(header),
        "selected_post_adjustment_month_key": key,
        "selected_month_is_listed": bool(rows),
        "selected_month_records": rows,
    }


def adjustment_lines(reference: dict[str, Any]) -> list[str]:
    counts = reference["complete_published_table_counts"]
    year, month, leap = reference["selected_post_adjustment_month_key"]
    month_label = f"{year}年{'闰' if leap else ''}{month}月"
    rows = reference["selected_month_records"]
    lines = [
        f"NAOJ公开校订目录按本次校订后的{month_label}匹配{len(rows)}条。"
        f"完整来源共{counts['all_nonheader_published_table_rows']}条表格记录，"
        f"其中{counts['monthly_adjustment_rows']}条为月校订、"
        f"{counts['solar_adjustment_rows']}条为节气校订、"
        f"{counts['early_two_calendar_comparison_rows']}条为早期两历比较；"
        "后两类未猜绑到本月，目录未列也不证明本月从未校订。"
        "这是同一宿主提供方已公开的校订说明，不是新取得原始颁历、另一组独立史料或本次重新执行校订。"
        "提供方数据库声明默认西历在1582年10月15日含当日起用格里历，之前用儒略历；"
        "本目录日期按该约定解释并另核对宿主，目录表本身未另写这项历制声明。"
        "本月未列条目时也不能把其他条目的原印日期一律当成儒略历或一律当成格里历。"
    ]
    for row in rows:
        cells = row["literal_cells"]
        literal = (
            "；".join(cells[1:3])
            if row["kind"] == "month_start_adjustment"
            else cells[1]
        )
        lines.append(
            f"{row['id']}出版方原列：{literal}；参照《{row['reference_literal']}》，"
            f"备注为{row['reason_literal'] or '空白'}。"
        )
        if row["after_start"] is None:
            lines.append(
                "此条改的是月名或闰标记，没有在这一条另印月首西历；不从相邻条目补造该条月首。"
            )
            continue
        before, after = row["before_start"], row["after_start"]

        def describe(value: dict[str, Any]) -> str:
            calendar = (
                "儒略历" if value["calendar_convention"] == "julian" else "格里历"
            )
            fields = "/".join(str(v) for v in value["printed_civil_fields"])
            return (
                f"{calendar}{fields}对应前推格里历{value['proleptic_gregorian_date']}"
            )

        lines.append(
            "按提供方数据库声明的默认西历约定解释本表日期："
            f"{describe(before)}，{describe(after)}。此表本身未另写历制声明，"
            "该约定与本次宿主日期的对应另作核对，不把原印西历直接当作前推格里历。"
        )
        if row["binding_state"] == "same_published_post_adjustment_date_and_cycle":
            lines.append(
                "此条校订后月首日序及干支均与本次宿主相合；没有再平移一次历日或配宿。"
            )
        else:
            lines.append(
                "此条校订后日期或干支与本次宿主有分歧，完整保留，不覆盖当前历日或配宿。"
            )
    lines.append(
        "这些月名、朔日或节气校订没有认证古代平明、桧尾半日和闰小月补配优先，也不计现实预测样本。"
    )
    return lines
