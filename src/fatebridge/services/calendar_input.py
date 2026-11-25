"""Calendar date parsing."""

from datetime import datetime

from fatebridge.utils.errors import ParameterError


def _parse_calendar_datetime(date_text: str, time_text: str) -> datetime:
    normalized_date = (date_text or "").strip().replace("/", "-")
    normalized_time = (time_text or "").strip()
    try:
        date = datetime.strptime(normalized_date, "%Y-%m-%d").date()
    except ValueError:
        message = "date 须为有效日期，格式为 YYYY-MM-DD。"
        raise ParameterError(
            message,
            [{"path": "date", "code": "invalid_calendar_date", "message": message}],
        ) from None
    try:
        time_format = "%H:%M:%S" if normalized_time.count(":") == 2 else "%H:%M"
        time = datetime.strptime(normalized_time, time_format).time()
    except ValueError:
        message = "time 须为有效的 24 小时时间，格式为 HH:MM[:SS]。"
        raise ParameterError(
            message,
            [{"path": "time", "code": "invalid_calendar_time", "message": message}],
        ) from None
    return datetime.combine(date, time)
