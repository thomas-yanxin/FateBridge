"""Independent snapshot-to-structured-motion fidelity checks, no engine import."""

import math
import re

LABELS = {
    "native_longitude_speed": "原生日速",
    "light_time_correction": "光行时链式修正",
    "spatial_aberration_correction": "空间光行差修正",
    "lunar_source_remainder_correction": "月球固定框架源导数余项",
    "sidereal_origin_wrap_correction": "恒星黄道原点整圈差分修正",
    "rotation_correction": "黄道旋转导数修正",
    "analytic_frame_correction": "日期框架解析导数修正",
    "position_derivative_correction": "完整视位置导数余项",
}
NUMBER = r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"


def verify(result):
    chart = result["chart"]
    text = result["snapshot_text"]
    section = text.split("[天象瞬时黄经运动]\n")
    if len(section) != 2:
        raise ValueError("Motion snapshot section absent or duplicated")
    section = section[1].split("\n[", 1)[0]
    rows = []
    for obj in chart["chart"]["objects"]:
        motion = obj["motion"]
        lines = [s for s in section.splitlines() if s.startswith(obj["id"] + " / ")]
        if len(lines) != 1:
            raise ValueError("Motion object absent or duplicated: " + obj["id"])
        line = lines[0]
        actual = list(map(float, re.findall(NUMBER + r" 度/日", line)))
        rate = motion["longitude_speed"]
        fields = [k for k in LABELS if k in motion]
        expected_count = (rate is not None) + len(fields)
        if len(actual) != expected_count:
            raise ValueError(
                f"Motion decomposition missing/extra term for {obj['id']}: {len(actual)} != {expected_count}"
            )
        if motion["unit"] != "degree_per_day":
            raise ValueError("Structured motion unit changed")
        if rate is None:
            if motion["direction"] != "not_computed" or "未计算" not in line:
                raise ValueError("Unknown rate misrepresented")
        else:
            if not math.isfinite(rate) or actual[0] != rate:
                raise ValueError("Displayed rate differs")
            direction, label = (
                ("direct", "瞬时顺行")
                if rate > 0
                else (
                    ("retrograde", "瞬时逆行")
                    if rate < 0
                    else ("zero_instantaneous_rate", "瞬时零日速")
                )
            )
            if motion["direction"] != direction or label not in line:
                raise ValueError("Unrounded rate sign misrepresented")
        for field in fields:
            matches = re.findall(
                re.escape(LABELS[field]) + " " + NUMBER + r" 度/日", line
            )
            if len(matches) != 1 or float(matches[0]) != motion[field]:
                raise ValueError("Stored term absent, duplicated or changed: " + field)
        for field in LABELS.keys() - set(fields):
            if LABELS[field] in line:
                raise ValueError("Uncomputed term invented: " + field)
        if "native_longitude_speed" in fields:
            total = math.fsum(motion[k] for k in fields)
            allowance = 8 * math.ulp(max(abs(motion[k]) for k in fields))
            if abs(total - rate) > allowance:
                raise ValueError("Structured decomposition does not sum to final rate")
        rows.append(
            {
                "body": obj["id"],
                "represented_terms": fields,
                "direction": motion["direction"],
                "status": "faithful",
            }
        )
    return rows
