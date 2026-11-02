"""Defaults for analysis dates using the shared execution clock."""

from typing import Optional, Tuple


def get_current_analysis_date(
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    timezone_name: Optional[str] = None,
) -> Tuple[int, int]:
    """获取当前分析日期

    Args:
        analysis_year: 指定的分析年份
        analysis_month: 指定的分析月份

    Returns:
        (年份, 月份) 元组
    """
    # Keep the calendar dependency local so importing date defaults does not
    # eagerly load the calendar engine.
    from ..core.almanac import current_local_datetime

    current_date = current_local_datetime(timezone_name)

    if analysis_year is None:
        analysis_year = current_date.year
    if analysis_month is None:
        analysis_month = current_date.month

    return analysis_year, analysis_month
