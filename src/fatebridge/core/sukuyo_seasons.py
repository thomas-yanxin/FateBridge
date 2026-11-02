"""Read complete named seasonal counts without inventing a physical clock."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA_DIR / "sukuyo_seasons.json"


def seasonal_reference(rizang: dict[str, Any]) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    if data["source_files"]["T13n0397.xml"]["sha256"] != rizang["source_sha256"]:
        raise ValueError("季节昼夜对照与日藏具名版本不一致，须重新核验")
    t1299 = load_source(DATA_DIR / "sukuyo_t1299_days.json").data
    if data["source_files"]["T21n1299.xml"]["sha256"] != t1299["source_sha256"]:
        raise ValueError("季节昼夜对照与T1299具名版本不一致，须重新核验")
    comparative = load_source(DATA_DIR / "sukuyo_comparative_time_units.json").data
    witnesses = [r for r in comparative["witnesses"] if r["id"] == "T25n1509"]
    if (
        len(witnesses) != 1
        or data["source_files"]["T25n1509.xml"]["sha256"]
        != witnesses[0]["source_sha256"]
    ):
        raise ValueError("季节昼夜对照与大智度论具名版本不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def seasonal_reference_lines(reference: dict[str, Any]) -> list[str]:
    months = (
        "",
        "正",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "十一",
        "十二",
    )
    rows = reference["all12_season_rows"]
    counts = "、".join(
        f"{months[r['textual_month']]}月{r['day_count']}／{r['night_count']}"
        for r in rows
    )
    shadows = "、".join(
        f"{months[r['textual_month']]}月{r['noon_shadow_literal']}" for r in rows
    )
    return [
        "日藏全年季节原录：按昼／夜的原文字段‘时’计，"
        f"{counts}；十二组各合三十是逐项算术核对。"
        "八月的十五／十五来自原有叙述段，不是补造八月三十个逐日宿槽。"
        "二月、八月等长，五月昼数最大、十一月夜数最大；"
        "所选各段没有据此给出春秋分的现代事件日期。",
        f"同段日午影长原录为{shadows}。"
        "十一、十二月均作十二脚迹，未按平滑曲线或月序改字；"
        "脚迹不是已核定的现代长度，也未据影长反推观测纬度或晷表高度。",
        "同章另录三十摸呼律多为一日夜；月段各自标‘时’，"
        "和数相同不单独证明两种字样已经逐项等同或可换成现代四十八分钟。"
        "没有把三十当现代三十小时，也未用昼夜比例计算固定日出、平明或太阳高度。",
        "季节与月名须分开：日藏五月合女满、昼十八夜十二，"
        "T1299原注女月对应唐六月；大智度论所选五月至也记昼十八夜十二，"
        "十一月至夜十八昼十二。相同数月标签与时数是文本关系，未认证同一实际日期；"
        "不能只凭望宿名或季节数字选一个统一月移。"
        "T1299所选主文另有二月春分朔，景风的月名注另层保留。"
        "这些材料未定统一纪月、绝对年、置闰、现代钟界、桧尾前后半或闰小月补配优先，"
        "不移动当前历日、主宿、候选或双向关系。",
    ]
