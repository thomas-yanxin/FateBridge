"""Published solar-term targets, transcribed from HKO table 1.

https://www.hko.gov.hk/sc/gts/time/24solarterms.htm
"""

HKO_TERM_LONGITUDES = {
    "春分": 0,
    "清明": 15,
    "谷雨": 30,
    "立夏": 45,
    "小满": 60,
    "芒种": 75,
    "夏至": 90,
    "小暑": 105,
    "大暑": 120,
    "立秋": 135,
    "处暑": 150,
    "白露": 165,
    "秋分": 180,
    "寒露": 195,
    "霜降": 210,
    "立冬": 225,
    "小雪": 240,
    "大雪": 255,
    "冬至": 270,
    "小寒": 285,
    "大寒": 300,
    "立春": 315,
    "雨水": 330,
    "惊蛰": 345,
}


import math
from datetime import date
from pathlib import Path

from fatebridge.core.ephemeris_runtime import ephemeris_call, swe


def canonical_c_first_post(case):
    """Keep the original C midpoint/bracket/residuals; independently prove hi."""
    target = HKO_TERM_LONGITUDES[case["term"]]
    assert target == case["target_degrees"]

    def residual(jd):
        _, preflight = ephemeris_call("calc", jd, swe.SUN, swe.FLG_MOSEPH)
        point, flags = ephemeris_call("calc", jd, swe.SUN, swe.FLG_SWIEPH)
        assert preflight == swe.FLG_MOSEPH and flags == swe.FLG_SWIEPH
        return point[0] - target

    lo, hi = (date(1800, 1, d).toordinal() + 1721424.5 for d in case["initial_tt_days"])
    assert residual(lo) < 0 <= residual(hi)
    for _ in range(80):
        mid = (lo + hi) / 2
        if mid in (lo, hi):
            break
        if residual(mid) < 0:
            lo = mid
        else:
            hi = mid
    assert math.nextafter(lo, math.inf) == hi
    assert [lo, hi] == case["expected_bracket_tt"]
    assert (lo + hi) / 2 == case["expected_jd_tt"]
    left, right = residual(lo), residual(hi)
    assert left < 0 <= right
    # Preserve even the exact +540 wrapper used by the immutable C reference.
    assert [(v + 540) % 360 - 180 for v in (left, right)] == case["canonical_residuals"]
    for slot, expected in enumerate(case["file_windows"]):
        path, start, end, edition = ephemeris_call("get_current_file_data", slot)
        assert {
            "slot": slot,
            "filename": Path(path).name,
            "start_jd_tt": start,
            "end_jd_tt": end,
            "de_number": edition,
        } == expected
    return hi
