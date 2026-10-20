"""Calendar date parsing and time algorithm conventions."""

from datetime import datetime
from typing import Any


def _parse_calendar_datetime(date_text: str, time_text: str) -> datetime:
    normalized_date = (date_text or "").strip().replace("/", "-")
    normalized_time = (time_text or "").strip()
    if not normalized_date or not normalized_time:
        raise ValueError("date 和 time 不能为空。")

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(
                f"{normalized_date} {normalized_time}",
                fmt,
            )
        except ValueError:
            continue

    raise ValueError("无法解析 date/time，请使用 YYYY-MM-DD 与 HH:MM[:SS]。")


def _normalize_time_alg(value: Any) -> int:
    return 1 if value == 1 else 0
