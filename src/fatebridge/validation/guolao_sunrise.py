"""Source-table parsing and descriptive audits; no astronomical pass threshold."""

from __future__ import annotations

import json
import re
from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_sunrise import DATA, FIELDS, load_table

DIGITS = dict(zip("零〇０一二三四五六七八九", "000123456789"))
UNITS = {"十": 10, "百": 100, "千": 1000, "萬": 10000}


def chinese_integer(value: str) -> int:
    if not value or value == "初":
        return 0
    if all(c in DIGITS for c in value):
        return int("".join(DIGITS[c] for c in value))
    total = pending = 0
    last_unit = 100000
    digit_seen = False
    for c in value:
        if c in DIGITS:
            if digit_seen and pending:
                raise ValueError("未标明位值的连续小字，不将其吞入整数")
            pending, digit_seen = int(DIGITS[c]), True
        elif c in UNITS and UNITS[c] < last_unit:
            total += (pending or 1) * UNITS[c]
            pending, digit_seen, last_unit = 0, False, UNITS[c]
        else:
            raise ValueError("未识别的原表整数，不能猜补")
    return total + pending


def parse_cell(raw: str, kind: str) -> F | None:
    # This named edition explicitly marks deleted text with （） and additions
    # with〔〕. Original glyphs remain in the pinned raw table, not overwritten.
    text = re.sub(r"<ref>.*?</ref>", "", raw, flags=re.S)
    text = re.sub(r"（.*?）", "", text)
    text = text.replace("〔", "").replace("〕", "")
    if not re.sub(r"<[^>]+>|\s", "", text):
        raise ValueError("空白格不是刊空或零，不补值")
    groups = re.findall(r"{{\*\|(.*?)}}", text)
    prefix = re.sub(r"<[^>]+>|\s", "", text.split("{{", 1)[0]).replace("度", "")
    if re.sub(r"<[^>]+>|\s", "", text) == "空":
        return None
    if any(len(g) != 2 or any(c not in DIGITS for c in g) for g in groups):
        raise ValueError("原表小字不是明确的两位数，不移位补零")
    trailing = re.sub(r"{{\*\|.*?}}|<[^>]+>|\s", "", text)
    if trailing != prefix:
        raise ValueError("小字或校记结构未完整解析")
    if kind == "rate":
        if len(groups) != 1:
            raise ValueError("刊差须保留完整分秒")
        return F(chinese_integer(prefix.removesuffix("分"))) + F(
            chinese_integer(groups[0]), 100
        )
    if kind == "night":
        if groups and len(groups) != 2:
            raise ValueError("半夜分须保留整数与秒栏")
        return F(chinese_integer(prefix)) + (
            chinese_integer(groups[0]) + F(chinese_integer(groups[1]), 100)
            if groups
            else F()
        )
    if kind != "angle" or len(groups) > 2:
        raise ValueError("未识别的源字段类型")
    return F(chinese_integer(prefix)) + sum(
        (F(chinese_integer(g), 100 ** (i + 1)) for i, g in enumerate(groups)), F()
    )


def parse_digital_table(raw_table: str) -> dict[str, Any]:
    raw_rows = re.findall(r"<tr>(.*?)</tr>", raw_table, flags=re.S)
    if len(raw_rows) != 94:
        raise ValueError("须完整保留表头及93个源位置，不丢空格")
    titles = re.findall(r"<td[^>]*>(.*?)</td>", raw_rows[0], flags=re.S)
    titles = [re.sub(r"<[^>]+>|\s", "", t) for t in titles]
    if titles != [
        "黃道積度",
        "內外度",
        "內外差",
        "冬至前後去極",
        "夏至前後去極",
        "冬晝夏夜",
        "夏晝冬夜",
        "晝夜差",
    ]:
        raise ValueError("具名原表列序改变，不按数字形似猜列")
    rows = []
    for index, raw in enumerate(raw_rows[1:]):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", raw, flags=re.S)
        if len(cells) != 8:
            raise ValueError("须保留全部八个原格，不拼接缺列")
        values = [
            parse_cell(cells[i], kind)
            for i, kind in [
                (0, "angle"),
                (1, "angle"),
                (2, "rate"),
                (5, "night"),
                (6, "night"),
                (7, "rate"),
            ]
        ]
        if [i for i, v in enumerate(values) if v is None] != (
            [1, 2, 5] if index == 92 else []
        ):
            raise ValueError("仅表尾三格刊空，其他未知格不能填值")
        rows.append(
            {
                k: str(v) if v is not None else None
                for k, v in zip(FIELDS, values, strict=True)
            }
        )
    return {
        "rows": rows,
        "target_fields": list(FIELDS),
        "polar_distance_columns_not_semantically_parsed": True,
        "digital_critical_marks_interpretation": "deleted_parentheses_removed_added_brackets_kept_only_for_this_named_edition",
        "source_raw_glyphs_overwritten": False,
    }


def audit_sunrise_tables() -> dict[str, Any]:
    data = json.loads(DATA.read_bytes())
    tables = {k: load_table(k) for k in data["profiles"]}
    differences = []
    a, b = data["profiles"]["gujin37_siku"], data["profiles"]["yuanshi55_digital"]
    for index, (one, two) in enumerate(zip(a["rows"], b["rows"], strict=True)):
        for field in FIELDS:
            x = F(one[field]) if one[field] is not None else None
            y = F(two[field]) if two[field] is not None else None
            if x != y:
                differences.append(
                    {
                        "index": index,
                        "field": field,
                        "gujin37_siku_exact": str(x) if x is not None else None,
                        "yuanshi55_digital_exact": str(y) if y is not None else None,
                    }
                )
    return {
        "model_id": "guolao_source_sunrise_tables_audit_v1",
        "profiles": {k: t.audit() for k, t in tables.items()},
        "witness_differences": differences,
        "source_row_count_is_accuracy_score": False,
        "automatic_daily_midnight_sun_and_global_fold_restored": False,
        "cross_witness_best_fit_selection": False,
        "modern_astronomical_truth_comparison": None,
        "real_career_subjects_forecasts_outcomes_added": 0,
    }
