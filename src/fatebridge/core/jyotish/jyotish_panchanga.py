"""Classical five-limb Vedic Panchanga (Tithi, Vara, Nakshatra, Yoga, Karana).

Computed directly from exact rational sidereal Lahiri Sun and Moon longitudes
and local apparent sunrise (Vedic day = sunrise to next sunrise).
"""

from __future__ import annotations

import math
from datetime import datetime
from fractions import Fraction
from typing import Any, Dict, Optional

from fatebridge.core.jyotish.jyotish_dasha_levels import NakshatraPlacement
from fatebridge.core.jyotish.jyotish_vargas import longitude_ratio

# 30 Tithis (1-15 Shukla Paksha, 16-30 Krishna Paksha)
_TITHI_BASE = (
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

# Classical Tithi lords cycle every 8 tithis (BPHS / Muhurta Chintamani)
_TITHI_LORDS = (
    "Sun",
    "Moon",
    "Mars",
    "Mercury",
    "Jupiter",
    "Venus",
    "Saturn",
    "Rahu",
)

# 27 Luni-Solar Yogas (each 13°20' = 40/3 deg of (Sun + Moon) % 360)
_YOGAS = (
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

_MOVABLE_KARANAS = (
    ("Bava", "巴瓦"),
    ("Balava", "巴拉瓦"),
    ("Kaulava", "考拉瓦"),
    ("Taitila", "泰提拉"),
    ("Gara", "加拉"),
    ("Vanija", "瓦尼加"),
    ("Vishti", "维什提/跋陀罗"),
)

_VARA_NAMES = (
    ("Ravivara", "Sunday", "日曜日", "Sun"),
    ("Somavara", "Monday", "月曜日", "Moon"),
    ("Mangalavara", "Tuesday", "火曜日", "Mars"),
    ("Budhavara", "Wednesday", "水曜日", "Mercury"),
    ("Guruvara", "Thursday", "木曜日", "Jupiter"),
    ("Shukravara", "Friday", "金曜日", "Venus"),
    ("Shanivara", "Saturday", "土曜日", "Saturn"),
)


def _exact_angle(longitude: float | Fraction) -> Fraction:
    n, d = longitude_ratio(longitude)
    return Fraction(n, d)


def _band_angle(value: Fraction, lower: int | Fraction, width: int | Fraction) -> float:
    """Round within the exact half-open interval to which the angle belongs."""
    rendered = float(value)
    if rendered < lower:
        return math.nextafter(rendered, math.inf)
    else:
        pass
    if rendered >= lower + width:
        return math.nextafter(rendered, -math.inf)
    else:
        pass
    return rendered


def _limb_progress(elapsed: Fraction) -> dict[str, float]:
    return {
        "fraction_elapsed": min(float(elapsed), math.nextafter(1.0, 0.0)),
        "fraction_remaining": max(float(1 - elapsed), math.nextafter(0.0, 1.0)),
    }


def compute_panchanga(
    sun_longitude: float | Fraction,
    moon_longitude: float | Fraction,
    moon_nakshatra: NakshatraPlacement,
    *,
    local_datetime: Optional[datetime] = None,
    solar_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute all five classical Panchanga limbs with exact rational boundaries."""
    sun = _exact_angle(sun_longitude)
    moon = _exact_angle(moon_longitude)

    # 1. Tithi (12° increments of (Moon - Sun) mod 360)
    elongation = (moon - sun) % 360
    tithi_zero = int(elongation // 12)
    tithi_number = tithi_zero + 1
    tithi_elapsed = (elongation - tithi_zero * 12) / 12
    paksha = "Shukla" if tithi_number <= 15 else "Krishna"
    paksha_zh = "白分（盈月）" if paksha == "Shukla" else "黑分（亏月）"
    if tithi_number == 15:
        tithi_name, tithi_zh = "Purnima", "满月（十五）"
        tithi_lord = "Moon"
    elif tithi_number == 30:
        tithi_name, tithi_zh = "Amavasya", "新月（三十）"
        tithi_lord = "Rahu"
    else:
        pos = (tithi_number - 1) % 15
        tithi_name, num_zh = _TITHI_BASE[pos]
        tithi_zh = f"{'白分' if paksha == 'Shukla' else '黑分'}{num_zh}"
        tithi_lord = _TITHI_LORDS[pos % 8]

    # 2. Yoga (13°20' = 40/3° increments of (Sun + Moon) mod 360)
    lunisolar_sum = (sun + moon) % 360
    yoga_span = Fraction(40, 3)
    yoga_zero = int(lunisolar_sum // yoga_span)
    yoga_start = yoga_zero * yoga_span
    yoga_elapsed = (lunisolar_sum - yoga_start) / yoga_span
    yoga_name, yoga_zh = _YOGAS[yoga_zero]

    # 3. Karana (half-tithi = 6° increments of (Moon - Sun) mod 360; 0..59)
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
        karana_name, karana_zh = _MOVABLE_KARANAS[(half_idx - 1) % 7]
        karana_kind = "movable"

    # 4. Vara (Vedic weekday anchored to local sunrise -> next sunrise)
    vara_info: Dict[str, Any]
    opening_date: Optional[str] = None
    opening_sunrise_jd_ut1: Optional[float] = None
    before_sunrise: Optional[bool] = None
    weekday_sun0: Optional[int] = None
    _LORD_TO_SUN0 = {row[3]: idx for idx, row in enumerate(_VARA_NAMES)}
    if isinstance(solar_context, dict):
        day_lord = solar_context.get("day_lord")
        opening_date = solar_context.get("opening_local_mean_date")
        opening_sunrise_jd_ut1 = solar_context.get("opening_sunrise_jd_ut1")
        if isinstance(day_lord, str) and day_lord in _LORD_TO_SUN0:
            weekday_sun0 = _LORD_TO_SUN0[day_lord]
            before_sunrise = solar_context.get("before_local_sunrise")
        else:
            pass
    else:
        pass
    if weekday_sun0 is None and local_datetime is not None:
        weekday_sun0 = (local_datetime.weekday() + 1) % 7
    else:
        pass

    if weekday_sun0 is not None:
        sanskrit, english, zh, lord = _VARA_NAMES[weekday_sun0]
        vara_info = {
            "index": weekday_sun0,
            "name": sanskrit,
            "weekday": english,
            "label_zh": zh,
            "lord": lord,
            "opening_local_mean_date": opening_date,
            "opening_sunrise_jd_ut1": opening_sunrise_jd_ut1,
            "is_day": (
                solar_context.get("is_day") if isinstance(solar_context, dict) else None
            ),
            "before_local_sunrise": before_sunrise,
            "basis": (
                "local_sunrise_to_sunrise"
                if opening_sunrise_jd_ut1 is not None
                else "civil_date_fallback"
            ),
        }
    else:
        vara_info = {"status": "unavailable"}

    return {
        "method_id": "jyotish_panchanga_exact_rational_v1",
        "tithi": {
            "number": tithi_number,
            "paksha": paksha,
            "paksha_zh": paksha_zh,
            "name": tithi_name,
            "label_zh": tithi_zh,
            "lord": tithi_lord,
            "elongation_degrees": _band_angle(elongation, karana_start, 6),
            **_limb_progress(tithi_elapsed),
        },
        "vara": vara_info,
        "nakshatra": {
            "index": moon_nakshatra["index"],
            "name": moon_nakshatra["name"],
            "lord": moon_nakshatra["lord"],
            "pada": moon_nakshatra["pada"],
            **_limb_progress((moon % yoga_span) / yoga_span),
        },
        "yoga": {
            "number": yoga_zero + 1,
            "name": yoga_name,
            "label_zh": yoga_zh,
            "lunisolar_sum_degrees": _band_angle(lunisolar_sum, yoga_start, yoga_span),
            **_limb_progress(yoga_elapsed),
        },
        "karana": {
            "half_tithi_index": half_idx + 1,
            "name": karana_name,
            "label_zh": karana_zh,
            "kind": karana_kind,
            **_limb_progress(karana_elapsed),
        },
    }
