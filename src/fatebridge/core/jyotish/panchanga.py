"""Fast five-limb Vedic Panchanga using Swiss Ephemeris BIT_HINDU_RISING (<0.3 ms)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.jyotish.vargas import longitude_ratio

TITHI_BASE = (
    ("Pratipada", "一"),
    ("Dwitiya", "二"),
    ("Tritiya", "三"),
    ("Chaturthi", "四"),
    ("Panchami", "五"),
    ("Shashthi", "六"),
    ("Saptami", "七"),
    ("Ashtami", "八"),
    ("Navami", "九"),
    ("Dashami", "十"),
    ("Ekadashi", "十一"),
    ("Dwadashi", "十二"),
    ("Trayodashi", "十三"),
    ("Chaturdashi", "十四"),
)
TITHI_LORDS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu")
YOGAS = (
    ("Vishkambha", "障碍"),
    ("Priti", "喜悦"),
    ("Ayushman", "长寿"),
    ("Saubhagya", "福运"),
    ("Shobhana", "明丽"),
    ("Atiganda", "大险"),
    ("Sukarma", "善业"),
    ("Dhriti", "坚忍"),
    ("Shula", "矛刺"),
    ("Ganda", "险阻"),
    ("Vriddhi", "增长"),
    ("Dhruva", "恒定"),
    ("Vyaghata", "击破"),
    ("Harshana", "欢欣"),
    ("Vajra", "金刚"),
    ("Siddhi", "成就"),
    ("Vyatipata", "灾变"),
    ("Variyan", "安乐"),
    ("Parigha", "门闩"),
    ("Shiva", "吉祥"),
    ("Siddha", "圆成"),
    ("Sadhya", "可达"),
    ("Shubha", "善美"),
    ("Shukla", "明净"),
    ("Brahma", "梵天"),
    ("Indra", "帝释"),
    ("Vaidhriti", "危持"),
)
MOVABLE_KARANAS = (
    ("Bava", "巴瓦"),
    ("Balava", "巴拉瓦"),
    ("Kaulava", "考拉瓦"),
    ("Taitila", "泰提拉"),
    ("Gara", "加拉"),
    ("Vanija", "瓦尼加"),
    ("Vishti", "维什提/跋陀罗"),
)
VARA_NAMES = (
    ("Ravivara", "Sunday", "日曜日", "Sun"),
    ("Somavara", "Monday", "月曜日", "Moon"),
    ("Mangalavara", "Tuesday", "火曜日", "Mars"),
    ("Budhavara", "Wednesday", "水曜日", "Mercury"),
    ("Guruvara", "Thursday", "木曜日", "Jupiter"),
    ("Shukravara", "Friday", "金曜日", "Venus"),
    ("Shanivara", "Saturday", "土曜日", "Saturn"),
)
WEEK = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
HORA_ORDER = ("Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars")


def _jd_ut1_to_utc_iso(jd_ut1: float) -> str | None:
    if runtime.swe is None or not math.isfinite(jd_ut1):
        return None
    y, m, d, h = runtime.swe.revjul(jd_ut1, runtime.swe.GREG_CAL)
    sec_total = h * 3600.0
    hour = int(sec_total // 3600)
    minute = int((sec_total % 3600) // 60)
    sec = int(sec_total % 60)
    micro = int(round((sec_total - int(sec_total)) * 1_000_000)) % 1_000_000
    try:
        dt = datetime(y, m, d, hour % 24, minute, sec, micro, tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None


def fast_solar_context(
    jd_ut1: float,
    longitude: float,
    latitude: float,
) -> dict[str, Any]:
    """Resolve sunrise/sunset brackets in <0.3 ms using C Swiss Ephemeris rise_trans."""
    swe = runtime.swe
    geopos = (longitude, latitude, 0.0)
    if swe is None:
        return {
            "status": "unavailable",
            "day_lord": None,
            "hora_lord": None,
            "tribhaga_lord": None,
        }

    def _next_event(start_jd: float, rsmi: int) -> float | None:
        res, tret = runtime.ephemeris_call(
            "rise_trans",
            start_jd,
            swe.SUN,
            rsmi | swe.BIT_HINDU_RISING,
            geopos,
            0.0,
            0.0,
            swe.FLG_SWIEPH,
        )
        return float(tret[0]) if res >= 0 and math.isfinite(tret[0]) else None

    with runtime.preserve_ephemeris_path():
        # Search for sunrise just before jd_ut1 (within 25h) and next sunrise after jd_ut1
        prev_rise = _next_event(jd_ut1 - 1.05, swe.CALC_RISE)
        if prev_rise is not None and prev_rise > jd_ut1:
            prev_rise = _next_event(jd_ut1 - 2.05, swe.CALC_RISE)
        next_rise = _next_event(jd_ut1, swe.CALC_RISE)
        prev_set = _next_event(jd_ut1 - 1.05, swe.CALC_SET)
        if prev_set is not None and prev_set > jd_ut1:
            prev_set = _next_event(jd_ut1 - 2.05, swe.CALC_SET)
        next_set = _next_event(jd_ut1, swe.CALC_SET)

    result: dict[str, Any] = {
        "status": "solar_day_not_bracketed",
        "day_lord": None,
        "hora_lord": None,
        "tribhaga_lord": None,
        "is_day": None,
        "sunrise_jd_ut1": prev_rise,
        "next_sunrise_jd_ut1": next_rise,
        "sunset_jd_ut1": prev_set,
        "next_sunset_jd_ut1": next_set,
    }

    if (
        prev_rise is not None
        and next_rise is not None
        and prev_rise <= jd_ut1 < next_rise
    ):
        # Local solar weekday of opening sunrise
        y, m, d, _ = swe.revjul(prev_rise + longitude / 360.0, swe.GREG_CAL)
        try:
            opening_dt = datetime(y, m, d)
            day_lord = WEEK[(opening_dt.weekday() + 1) % 7]
            opening_date = opening_dt.date().isoformat()
        except ValueError:
            day_lord = None
            opening_date = None
        elapsed_hours = (jd_ut1 - prev_rise) * 24.0
        hora = max(1, min(24, int(elapsed_hours) + 1))
        hora_lord = (
            HORA_ORDER[(HORA_ORDER.index(day_lord) + hora - 1) % 7]
            if day_lord
            else None
        )
        result.update(
            {
                "status": "bracketed",
                "day_lord": day_lord,
                "opening_local_mean_date": opening_date,
                "opening_sunrise_jd_ut1": prev_rise,
                "sunrise_utc": _jd_ut1_to_utc_iso(prev_rise),
                "sunset_utc": _jd_ut1_to_utc_iso(next_set) if next_set else None,
                "hora_number": hora,
                "hora_lord": hora_lord,
            }
        )

    # Active day/night arc for Tribhaga Bala
    events = []
    if prev_rise is not None and prev_rise <= jd_ut1:
        events.append((prev_rise, "rise"))
    if prev_set is not None and prev_set <= jd_ut1:
        events.append((prev_set, "set"))
    after_events = []
    if next_rise is not None and next_rise > jd_ut1:
        after_events.append((next_rise, "rise"))
    if next_set is not None and next_set > jd_ut1:
        after_events.append((next_set, "set"))

    if events and after_events:
        arc_start, start_kind = max(events)
        arc_end, end_kind = min(after_events)
        if start_kind != end_kind and arc_end > arc_start:
            is_day = start_kind == "rise"
            third = min(2, int(3 * (jd_ut1 - arc_start) / (arc_end - arc_start)))
            result["is_day"] = is_day
            result["before_local_sunrise"] = not is_day
            result["tribhaga_lord"] = (
                ("Mercury", "Sun", "Saturn") if is_day else ("Moon", "Venus", "Mars")
            )[third]

    return result


def compute_panchanga(
    sun_longitude: float | Fraction,
    moon_longitude: float | Fraction,
    moon_nakshatra: dict[str, Any],
    *,
    local_datetime: datetime | None = None,
    solar_context: dict[str, Any] | None = None,
    sun_speed: float = 0.9856,
    moon_speed: float = 13.176,
    jd_ut1: float | None = None,
) -> dict[str, Any]:
    """Compute all five classical Panchanga limbs with exact rational boundaries and end estimates."""
    sn, sd = longitude_ratio(sun_longitude)
    mn, md = longitude_ratio(moon_longitude)
    sun = Fraction(sn, sd)
    moon = Fraction(mn, md)

    # 1. Tithi
    elongation = (moon - sun) % 360
    tithi_zero = int(elongation // 12)
    tithi_number = tithi_zero + 1
    tithi_elapsed = (elongation - tithi_zero * 12) / 12
    paksha = "Shukla" if tithi_number <= 15 else "Krishna"
    paksha_zh = "白分（盈月）" if paksha == "Shukla" else "黑分（亏月）"
    if tithi_number == 15:
        tithi_name, tithi_zh, tithi_lord = "Purnima", "满月（十五）", "Moon"
    elif tithi_number == 30:
        tithi_name, tithi_zh, tithi_lord = "Amavasya", "新月（三十）", "Rahu"
    else:
        pos = (tithi_number - 1) % 15
        tithi_name, num_zh = TITHI_BASE[pos]
        tithi_zh = f"{'白分' if paksha == 'Shukla' else '黑分'}{num_zh}"
        tithi_lord = TITHI_LORDS[pos % 8]

    # 2. Yoga
    lunisolar_sum = (sun + moon) % 360
    yoga_span = Fraction(40, 3)
    yoga_zero = int(lunisolar_sum // yoga_span)
    yoga_start = yoga_zero * yoga_span
    yoga_elapsed = (lunisolar_sum - yoga_start) / yoga_span
    yoga_name, yoga_zh = YOGAS[yoga_zero]

    # 3. Karana
    half_idx = int(elongation // 6)
    karana_start = half_idx * 6
    karana_elapsed = (elongation - karana_start) / 6
    if half_idx == 0:
        karana_name, karana_zh, karana_kind = "Kimstughna", "金斯图格纳", "fixed"
    elif half_idx == 57:
        karana_name, karana_zh, karana_kind = "Shakuni", "沙库尼", "fixed"
    elif half_idx == 58:
        karana_name, karana_zh, karana_kind = "Chatushpada", "四足", "fixed"
    elif half_idx == 59:
        karana_name, karana_zh, karana_kind = "Naga", "那伽", "fixed"
    else:
        karana_name, karana_zh = MOVABLE_KARANAS[(half_idx - 1) % 7]
        karana_kind = "movable"

    # 4. Vara
    weekday_sun0: int | None = None
    opening_date = None
    opening_sunrise = None
    before_sunrise = None
    lord_to_sun0 = {row[3]: idx for idx, row in enumerate(VARA_NAMES)}
    if isinstance(solar_context, dict):
        day_lord = solar_context.get("day_lord")
        opening_date = solar_context.get("opening_local_mean_date")
        opening_sunrise = solar_context.get("opening_sunrise_jd_ut1")
        if isinstance(day_lord, str) and day_lord in lord_to_sun0:
            weekday_sun0 = lord_to_sun0[day_lord]
            before_sunrise = solar_context.get("before_local_sunrise")
    if weekday_sun0 is None and local_datetime is not None:
        weekday_sun0 = (local_datetime.weekday() + 1) % 7

    if weekday_sun0 is not None:
        sanskrit, english, zh, lord = VARA_NAMES[weekday_sun0]
        vara_info: dict[str, Any] = {
            "index": weekday_sun0,
            "name": sanskrit,
            "weekday": english,
            "label_zh": zh,
            "lord": lord,
            "opening_local_mean_date": opening_date,
            "opening_sunrise_jd_ut1": opening_sunrise,
            "sunrise_utc": (
                solar_context.get("sunrise_utc")
                if isinstance(solar_context, dict)
                else None
            ),
            "sunset_utc": (
                solar_context.get("sunset_utc")
                if isinstance(solar_context, dict)
                else None
            ),
            "before_local_sunrise": before_sunrise,
            "basis": (
                "local_sunrise_to_sunrise" if opening_sunrise else "civil_date_fallback"
            ),
        }
    else:
        vara_info = {"status": "unavailable"}

    def _end_utc(rem_deg: float, rate: float) -> str | None:
        if jd_ut1 is None or rate <= 0:
            return None
        return _jd_ut1_to_utc_iso(jd_ut1 + rem_deg / rate)

    diff_rate = moon_speed - sun_speed
    sum_rate = moon_speed + sun_speed

    return {
        "method_id": "jyotish_panchanga_bit_hindu_rising_v2",
        "tithi": {
            "number": tithi_number,
            "paksha": paksha,
            "paksha_zh": paksha_zh,
            "name": tithi_name,
            "label_zh": tithi_zh,
            "lord": tithi_lord,
            "elongation_degrees": round(float(elongation), 6),
            "fraction_elapsed": round(float(tithi_elapsed), 6),
            "end_utc": _end_utc(float(1 - tithi_elapsed) * 12.0, diff_rate),
        },
        "vara": vara_info,
        "nakshatra": {
            "index": moon_nakshatra["index"],
            "name": moon_nakshatra["name"],
            "lord": moon_nakshatra["lord"],
            "pada": moon_nakshatra["pada"],
            "fraction_elapsed": round(float(moon_nakshatra["fraction_elapsed"]), 6),
            "end_utc": _end_utc(
                float((1 - (moon % yoga_span) / yoga_span) * yoga_span), moon_speed
            ),
        },
        "yoga": {
            "number": yoga_zero + 1,
            "name": yoga_name,
            "label_zh": yoga_zh,
            "lunisolar_sum_degrees": round(float(lunisolar_sum), 6),
            "fraction_elapsed": round(float(yoga_elapsed), 6),
            "end_utc": _end_utc(float((1 - yoga_elapsed) * yoga_span), sum_rate),
        },
        "karana": {
            "half_tithi_index": half_idx + 1,
            "name": karana_name,
            "label_zh": karana_zh,
            "kind": karana_kind,
            "fraction_elapsed": round(float(karana_elapsed), 6),
            "end_utc": _end_utc(float(1 - karana_elapsed) * 6.0, diff_rate),
        },
    }
