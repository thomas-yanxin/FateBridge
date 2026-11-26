"""Jyotish Yogas, Arudha Padas, Jaimini Chara Karakas, Gulika/Mandi, Upagrahas, and Special Lagnas."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.jyotish.vargas import EXALTATION, GRAHAS, RASI_LORDS

SEVEN_GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
CHARA_KARAKA_LABELS = ("AK", "AmK", "BK", "MK", "PK", "GK", "DK")
KENDRAS = {1, 4, 7, 10}
TRIKONAS = {1, 5, 9}
DUSTHANAS = {6, 8, 12}

# Gulika / Mandi rising eighth-portion index (0-based out of 8 equal parts of day/night)
# Sunday(0)..Saturday(6): day portion of Saturn is 7,6,5,4,3,2,1 (0-based 6,5,4,3,2,1,0)
_DAY_SATURN_SLICE = (6, 5, 4, 3, 2, 1, 0)
_NIGHT_SATURN_SLICE = (2, 1, 0, 6, 5, 4, 3)


def chara_karakas(longitudes: dict[str, float]) -> list[dict[str, Any]]:
    """Compute the 7 Jaimini Chara Karakas (Atmakaraka -> Darakaraka) by degree in sign."""
    ranked = sorted(
        ((p, float(longitudes[p]) % 30.0) for p in SEVEN_GRAHAS),
        key=lambda item: (-item[1], item[0]),
    )
    return [
        {"karaka": label, "planet": planet, "degree_in_sign": round(deg, 4)}
        for label, (planet, deg) in zip(CHARA_KARAKA_LABELS, ranked)
    ]


def arudha_padas(longitudes: dict[str, float], ascendant: float) -> dict[str, Any]:
    """Compute AL, UL (A12), and A2..A12 using BPHS 1st/7th house exception (+10 signs)."""
    signs = {p: int(longitudes[p] // 30) for p in SEVEN_GRAHAS}
    asc_sign = int(ascendant // 30)
    padas: dict[str, dict[str, Any]] = {}
    for house in range(1, 13):
        house_sign = (asc_sign + house - 1) % 12
        lord = RASI_LORDS[house_sign]
        lord_sign = signs[lord]
        dist = (lord_sign - house_sign) % 12
        pada_sign = (lord_sign + dist) % 12
        # BPHS exception: Pada cannot fall in the house itself (dist==0) or 7th from it (dist==6)
        rel = (pada_sign - house_sign) % 12
        if rel in (0, 6):
            pada_sign = (pada_sign + 9) % 12  # 10th from that sign (0-based +9)
        code = "AL" if house == 1 else "UL" if house == 12 else f"A{house}"
        padas[code] = {
            "house": house,
            "sign": SIGNS[pada_sign],
            "sign_index": pada_sign,
            "lord": RASI_LORDS[pada_sign],
        }
    return padas


def upagrahas_and_special_lagnas(
    *,
    sun_longitude: float,
    ascendant: float,
    jd_ut1: float,
    solar_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute Dhuma..Upaketu, Gulika/Mandi, Hora Lagna, Ghatika Lagna, and Bhava Lagna."""
    dhuma = (sun_longitude + 133.0 + 20.0 / 60.0) % 360.0
    vyatipata = (360.0 - dhuma) % 360.0
    parivesha = (vyatipata + 180.0) % 360.0
    indrachapa = (360.0 - parivesha) % 360.0
    upaketu = (indrachapa + 16.0 + 40.0 / 60.0) % 360.0

    # Special Lagnas (approx. 15°/hour for Bhava, 30°/hour for Hora, 75°/hour = 1 sign/ghati for Ghatika from sunrise)
    hora_lagna = ghatika_lagna = bhava_lagna = gulika_jd = None
    sunrise_jd = (
        solar_context.get("opening_sunrise_jd_ut1")
        if isinstance(solar_context, dict)
        else None
    )
    if isinstance(sunrise_jd, float):
        hrs = (jd_ut1 - sunrise_jd) * 24.0
        ghatis = hrs * 2.5
        bhava_lagna = (sun_longitude + hrs * 15.0) % 360.0
        hora_lagna = (sun_longitude + hrs * 30.0) % 360.0
        ghatika_lagna = (sun_longitude + ghatis * 30.0) % 360.0

        # Gulika time: Saturn's portion of day/night divided into 8 parts
        from fatebridge.core.jyotish.panchanga import WEEK

        day_lord = solar_context.get("day_lord")
        weekday_sun0 = WEEK.index(day_lord) if day_lord in WEEK else 0
        is_day = solar_context.get("is_day")
        next_set = solar_context.get("next_sunset_jd_ut1")
        prev_set = solar_context.get("sunset_jd_ut1")
        next_rise = solar_context.get("next_sunrise_jd_ut1")
        if is_day and isinstance(next_set, float) and next_set > sunrise_jd:
            slice_idx = _DAY_SATURN_SLICE[weekday_sun0]
            gulika_jd = sunrise_jd + (next_set - sunrise_jd) * slice_idx / 8.0
        elif (
            is_day is False
            and isinstance(prev_set, float)
            and isinstance(next_rise, float)
            and next_rise > prev_set
        ):
            slice_idx = _NIGHT_SATURN_SLICE[weekday_sun0]
            gulika_jd = prev_set + (next_rise - prev_set) * slice_idx / 8.0

    # Fallback approximate Gulika longitude offset from ascendant when sunrise lag unavailable
    def _pt(lon: float | None) -> dict[str, Any] | None:
        if lon is None:
            return None
        s = int(lon // 30)
        return {
            "longitude": round(lon, 4),
            "sign": SIGNS[s],
            "degree_in_sign": round(lon % 30.0, 4),
        }

    gulika_lon = None
    if gulika_jd is not None:
        from fatebridge.core.astro import runtime

        if runtime.swe is not None:
            with runtime.preserve_ephemeris_path():
                _, ascmc = runtime.ephemeris_call(
                    "houses_ex", gulika_jd, 0.0, 0.0, b"W", runtime.swe.FLG_SIDEREAL
                )
                gulika_lon = float(ascmc[0]) % 360.0

    return {
        "dhuma": _pt(dhuma),
        "vyatipata": _pt(vyatipata),
        "parivesha": _pt(parivesha),
        "indrachapa": _pt(indrachapa),
        "upaketu": _pt(upaketu),
        "gulika": _pt(gulika_lon),
        "hora_lagna": _pt(hora_lagna if hora_lagna is not None else ascendant),
        "ghatika_lagna": _pt(ghatika_lagna if ghatika_lagna is not None else ascendant),
        "bhava_lagna": _pt(bhava_lagna if bhava_lagna is not None else ascendant),
    }


def evaluate_yogas(longitudes: dict[str, float], ascendant: float) -> dict[str, Any]:
    """Identify classical Parashari Planetary Yogas on the D1 sidereal chart."""
    signs = {p: int(longitudes[p] // 30) for p in GRAHAS}
    asc_sign = int(ascendant // 30)
    houses = {p: (signs[p] - asc_sign) % 12 + 1 for p in GRAHAS}

    house_lord = {h: RASI_LORDS[(asc_sign + h - 1) % 12] for h in range(1, 13)}
    lord_houses: dict[str, list[int]] = {}
    for h, lord in house_lord.items():
        lord_houses.setdefault(lord, []).append(h)

    def _aspecting(a: str, b: str) -> bool:
        dist = (signs[b] - signs[a]) % 12 + 1
        offsets = {7}
        if a == "Mars":
            offsets.update({4, 8})
        elif a == "Jupiter":
            offsets.update({5, 9})
        elif a == "Saturn":
            offsets.update({3, 10})
        return dist in offsets

    def _linked(a: str, b: str) -> bool:
        return a != b and (
            signs[a] == signs[b] or (_aspecting(a, b) and _aspecting(b, a))
        )

    matched: list[dict[str, Any]] = []

    # 1. Pancha Mahapurusha Yogas
    mahapurusha_names = {
        "Mars": "Ruchaka",
        "Mercury": "Bhadra",
        "Jupiter": "Hamsa",
        "Venus": "Malavya",
        "Saturn": "Sasa",
    }
    for p, yname in mahapurusha_names.items():
        s = signs[p]
        if houses[p] in KENDRAS and (RASI_LORDS[s] == p or s == EXALTATION[p]):
            matched.append(
                {
                    "name": f"{yname} Mahapurusha",
                    "category": "pancha_mahapurusha",
                    "planets": [p],
                }
            )

    # 2. Gajakesari Yoga (Jupiter in Kendra from Moon)
    if ((signs["Jupiter"] - signs["Moon"]) % 12 + 1) in KENDRAS:
        matched.append(
            {
                "name": "Gajakesari",
                "category": "chandra_yoga",
                "planets": ["Moon", "Jupiter"],
            }
        )

    # 3. Budhaditya Yoga
    if signs["Sun"] == signs["Moon"] or signs["Sun"] == signs["Mercury"]:
        if signs["Sun"] == signs["Mercury"]:
            matched.append(
                {
                    "name": "Budhaditya",
                    "category": "solar_yoga",
                    "planets": ["Sun", "Mercury"],
                }
            )

    # 4. Rajayoga (Kendra lord + Trikona lord linked by conjunction or mutual aspect)
    kendra_lords = {house_lord[h] for h in KENDRAS}
    trikona_lords = {house_lord[h] for h in TRIKONAS}
    for kl in sorted(kendra_lords):
        for tl in sorted(trikona_lords):
            if kl != tl and _linked(kl, tl):
                matched.append(
                    {"name": "Rajayoga", "category": "rajayoga", "planets": [kl, tl]}
                )

    # 5. Dhana Yoga (2nd/11th with 1st/5th/9th lord)
    wealth_lords = {house_lord[2], house_lord[11]}
    trine_lords = {house_lord[1], house_lord[5], house_lord[9]}
    for wl in sorted(wealth_lords):
        for tl in sorted(trine_lords):
            if wl != tl and _linked(wl, tl):
                matched.append(
                    {"name": "Dhana", "category": "dhana_yoga", "planets": [wl, tl]}
                )

    # 6. Viparita Rajayoga (Harsha=6 in 6/8/12, Sarala=8 in 6/8/12, Vimala=12 in 6/8/12)
    for h, yname in ((6, "Harsha"), (8, "Sarala"), (12, "Vimala")):
        lord = house_lord[h]
        if houses[lord] in DUSTHANAS:
            matched.append(
                {
                    "name": f"{yname} Viparita Rajayoga",
                    "category": "viparita_rajayoga",
                    "planets": [lord],
                }
            )

    # 7. Neecha Bhanga (Debilitated planet whose dispositor or exaltation lord is in Kendra from Lagna/Moon)
    for p, ex_sign in EXALTATION.items():
        deb_sign = (ex_sign + 6) % 12
        if signs[p] == deb_sign:
            dispositor = RASI_LORDS[deb_sign]
            ex_lord = RASI_LORDS[ex_sign]
            in_lagna_kendra = any(houses[x] in KENDRAS for x in (dispositor, ex_lord))
            in_moon_kendra = any(
                ((signs[x] - signs["Moon"]) % 12 + 1) in KENDRAS
                for x in (dispositor, ex_lord)
            )
            if in_lagna_kendra or in_moon_kendra:
                matched.append(
                    {
                        "name": "Neecha Bhanga",
                        "category": "cancellation",
                        "planets": [p],
                    }
                )

    # 8. Kemadruma Yoga (no physical planet in 2nd/12th from Moon, cancelled if Kendra from Lagna/Moon occupied)
    moon_s = signs["Moon"]
    adj_signs = {(moon_s + 1) % 12, (moon_s - 1) % 12}
    flanking = [
        p
        for p in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
        if signs[p] in adj_signs
    ]
    if not flanking:
        kendra_occupied = any(
            houses[p] in KENDRAS
            for p in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
        )
        matched.append(
            {
                "name": "Kemadruma",
                "category": "chandra_yoga",
                "planets": ["Moon"],
                "cancelled": kendra_occupied,
            }
        )

    # 9. Kala Sarpa (all 7 grahas strictly within Rahu->Ketu or Ketu->Rahu half-circle)
    rahu_lon = longitudes["Rahu"] % 360.0
    ketu_lon = longitudes["Ketu"] % 360.0
    all_rk = all(
        ((longitudes[p] - rahu_lon) % 360.0) <= ((ketu_lon - rahu_lon) % 360.0)
        for p in SEVEN_GRAHAS
    )
    all_kr = all(
        ((longitudes[p] - ketu_lon) % 360.0) <= ((rahu_lon - ketu_lon) % 360.0)
        for p in SEVEN_GRAHAS
    )
    if all_rk or all_kr:
        matched.append(
            {
                "name": "Kala Sarpa",
                "category": "nodal_yoga",
                "planets": ["Rahu", "Ketu"],
                "orientation": "Rahu_to_Ketu" if all_rk else "Ketu_to_Rahu",
            }
        )

    return {"count": len(matched), "yogas": matched}
