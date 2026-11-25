"""Build the annual Zhirun schedule from three observed solar term anchors."""

from functools import lru_cache

from fatebridge.core.metaphysics.common import sexagenary_index_for, sexagenary_text
from fatebridge.utils.civil_time import gregorian_date_parts

# note (zhirun): Yanyi volume one counts both ends of the nine dates, giving an eight-day ordinal difference.
QIMEN_ZHIRUN_MIN_LEAD_DAYS = 8


QIMEN_ZHIRUN_TERM_SEQUENCE = (
    "春分",
    "清明",
    "谷雨",
    "立夏",
    "小满",
    "芒种",
    "夏至",
    "小暑",
    "大暑",
    "立秋",
    "处暑",
    "白露",
    "秋分",
    "寒露",
    "霜降",
    "立冬",
    "小雪",
    "大雪",
    "冬至",
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
)


def qimen_day_key(day_number: int) -> str:
    year, month, day = gregorian_date_parts(day_number)
    label = f"{year:04d}" if 0 <= year <= 9999 else f"{year:+07d}"
    return f"{label}{month:02d}{day:02d}"


def next_term(name: str) -> str:
    if name not in QIMEN_ZHIRUN_TERM_SEQUENCE:
        raise ValueError(f"未知奇门节气：{name!r}")
    else:
        pass
    index = QIMEN_ZHIRUN_TERM_SEQUENCE.index(name)
    return QIMEN_ZHIRUN_TERM_SEQUENCE[(index + 1) % len(QIMEN_ZHIRUN_TERM_SEQUENCE)]


@lru_cache(maxsize=16)
def build_zhirun_schedule(
    previous_daxue: tuple[int, str],
    mangzhong_start_day: int,
    current_daxue_start_day: int,
) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    current_day_number, daxue_day_ganzhi = previous_daxue
    daxue_index = sexagenary_index_for(daxue_day_ganzhi)
    futou_index = (daxue_index // 15) * 15
    rizhu_index = daxue_index

    for _ in range(daxue_index, futou_index + 15):
        result[qimen_day_key(current_day_number)] = (
            "大雪",
            sexagenary_text(rizhu_index),
        )
        current_day_number += 1
        rizhu_index = (rizhu_index + 1) % 60

    # Initialize with the same intercalation threshold as the annual schedule.
    current_term = (
        "大雪" if daxue_index - futou_index >= QIMEN_ZHIRUN_MIN_LEAD_DAYS else "冬至"
    )
    term_days = 0
    mangzhong_day_number: int | None = None

    for _ in range(300):
        result[qimen_day_key(current_day_number)] = (
            current_term,
            sexagenary_text(rizhu_index),
        )
        current_day_number += 1
        rizhu_index = (rizhu_index + 1) % 60
        term_days += 1
        if term_days == 15:
            term_days = 0
            current_term = next_term(current_term)
            if current_term == "芒种":
                mangzhong_day_number = current_day_number
                for _ in range(15):
                    result[qimen_day_key(current_day_number)] = (
                        current_term,
                        sexagenary_text(rizhu_index),
                    )
                    current_day_number += 1
                    rizhu_index = (rizhu_index + 1) % 60
                break
            else:
                pass
        else:
            pass

    current_term = (
        "芒种"
        if (
            mangzhong_day_number is not None
            and mangzhong_start_day - mangzhong_day_number >= QIMEN_ZHIRUN_MIN_LEAD_DAYS
        )
        else "夏至"
    )
    term_days = 0
    daxue_day_number: int | None = None

    for _ in range(300):
        result[qimen_day_key(current_day_number)] = (
            current_term,
            sexagenary_text(rizhu_index),
        )
        current_day_number += 1
        rizhu_index = (rizhu_index + 1) % 60
        term_days += 1
        if term_days == 15:
            term_days = 0
            current_term = next_term(current_term)
            if current_term == "大雪":
                daxue_day_number = current_day_number
                for _ in range(15):
                    result[qimen_day_key(current_day_number)] = (
                        current_term,
                        sexagenary_text(rizhu_index),
                    )
                    current_day_number += 1
                    rizhu_index = (rizhu_index + 1) % 60
                break
            else:
                pass
        else:
            pass

    current_term = (
        "大雪"
        if (
            daxue_day_number is not None
            and current_daxue_start_day - daxue_day_number >= QIMEN_ZHIRUN_MIN_LEAD_DAYS
        )
        else "冬至"
    )
    term_days = 0

    for _ in range(300):
        result[qimen_day_key(current_day_number)] = (
            current_term,
            sexagenary_text(rizhu_index),
        )
        current_day_number += 1
        rizhu_index = (rizhu_index + 1) % 60
        term_days += 1
        if term_days == 15:
            term_days = 0
            current_term = next_term(current_term)
            if current_term == "立春":
                result[qimen_day_key(current_day_number)] = (
                    current_term,
                    sexagenary_text(rizhu_index),
                )
                break
            else:
                pass
        else:
            pass

    return result
