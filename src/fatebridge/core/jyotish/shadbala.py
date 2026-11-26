"""Complete 6-fold Parashari Shadbala, Ishta/Kashta Phala, Planetary War, and Bhava Bala."""

from __future__ import annotations

import math
from fractions import Fraction
from itertools import combinations
from typing import Any

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.jyotish.ephemeris import simon1994_mean_longitudes
from fatebridge.core.jyotish.panchanga import WEEK, fast_solar_context
from fatebridge.core.jyotish.vargas import (
    EXALTATION_PEAKS,
    MOOLATRIKONA,
    RASI_LORDS,
    SAPTA_DIVISIONS,
    bhava_chalit,
    longitude_ratio,
    relationship,
    varga_sign,
)

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
STARS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
NATURAL_RANKS = dict(
    zip(("Saturn", "Mars", "Mercury", "Jupiter", "Venus", "Moon", "Sun"), range(1, 8))
)
REQUIRED_SHADBALA_RUPA = {
    "Sun": 6.5,
    "Moon": 6.0,
    "Mars": 5.0,
    "Mercury": 7.0,
    "Jupiter": 6.5,
    "Venus": 5.5,
    "Saturn": 5.0,
}
SAPTA_PROFILES = {
    "santhanam_27": {
        "moolatrikona": 45.0,
        "own_sign": 30.0,
        "great_friend": 20.0,
        "friend": 15.0,
        "neutral": 10.0,
        "enemy": 4.0,
        "great_enemy": 2.0,
    },
    "raman_30": {
        "moolatrikona": 45.0,
        "own_sign": 30.0,
        "great_friend": 22.5,
        "friend": 15.0,
        "neutral": 7.5,
        "enemy": 3.75,
        "great_enemy": 1.875,
    },
}
DREKKANA_GROUPS = {
    "santhanam_27_6": [
        ["Sun", "Mars", "Jupiter"],
        ["Moon", "Venus"],
        ["Mercury", "Saturn"],
    ],
    "raman_36": [["Sun", "Mars", "Jupiter"], ["Mercury", "Saturn"], ["Moon", "Venus"]],
}
BIMBA = {"Mars": 9.4, "Mercury": 6.6, "Jupiter": 190.4, "Venus": 16.6, "Saturn": 158.0}


def _directed_angle(a_lon: float, b_lon: float) -> Fraction:
    a, ad = longitude_ratio(a_lon)
    b, bd = longitude_ratio(b_lon)
    return (Fraction(b, bd) - Fraction(a, ad)) % 360


def _uchcha_virupa(planet: str, lon: float) -> float:
    peak = EXALTATION_PEAKS[planet]
    niche = (peak + 180.0) % 360.0
    arc = abs(((lon - niche + 180.0) % 360.0) - 180.0)
    return round(arc / 3.0, 4)


def compute_sthana_bala(
    longitudes: dict[str, float],
    ascendant: float,
    *,
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
) -> dict[str, dict[str, float]]:
    if saptavargaja_profile not in SAPTA_PROFILES:
        raise ValueError("saptavargaja_profile 须为 santhanam_27 或 raman_30。")
    if drekkana_profile not in DREKKANA_GROUPS:
        raise ValueError("drekkana_profile 须为 santhanam_27_6 或 raman_36。")
    weights = SAPTA_PROFILES[saptavargaja_profile]
    drek_groups = DREKKANA_GROUPS[drekkana_profile]
    signs = {p: varga_sign(longitudes[p], 1) for p in PLANETS}
    asc_sign = varga_sign(ascendant, 1)

    summary: dict[str, dict[str, float]] = {}
    for p in PLANETS:
        lon = float(longitudes[p])
        uchcha = _uchcha_virupa(p, lon)
        sapta = 0.0
        for div in SAPTA_DIVISIONS:
            s = varga_sign(lon, div)
            lord = RASI_LORDS[s]
            if s == MOOLATRIKONA[p][0] and (
                div == 1 or saptavargaja_profile == "santhanam_27"
            ):
                cond = "moolatrikona"
            elif lord == p:
                cond = "own_sign"
            else:
                cond = relationship(p, lord, signs)["compound"]
            sapta += weights[cond]
        nav_sign = varga_sign(lon, 9)
        pref_parity = 1 if p in {"Moon", "Venus"} else 0
        oja = (15.0 if signs[p] % 2 == pref_parity else 0.0) + (
            15.0 if nav_sign % 2 == pref_parity else 0.0
        )
        house = (signs[p] - asc_sign) % 12 + 1
        kendra = float({0: 60, 1: 30, 2: 15}[(house - 1) % 3])
        decanate = int((lon % 30.0) // 10.0)
        drek = 15.0 if p in drek_groups[decanate] else 0.0
        total = uchcha + sapta + oja + kendra + drek
        summary[p] = {
            "uchcha_bala": round(uchcha, 4),
            "saptavargaja_bala": round(sapta, 4),
            "ojayugma_bala": round(oja, 4),
            "kendradi_bala": round(kendra, 4),
            "drekkana_bala": round(drek, 4),
            "total_virupa": round(total, 4),
        }
    return summary


def compute_dig_bala(
    longitudes: dict[str, float], ascendant: float, midheaven: float
) -> dict[str, float]:
    weak = {
        "Sun": (midheaven + 180.0) % 360.0,
        "Mars": (midheaven + 180.0) % 360.0,
        "Moon": midheaven % 360.0,
        "Venus": midheaven % 360.0,
        "Mercury": (ascendant + 180.0) % 360.0,
        "Jupiter": (ascendant + 180.0) % 360.0,
        "Saturn": ascendant % 360.0,
    }
    return {
        p: round(
            float(
                min(
                    _directed_angle(weak[p], longitudes[p]),
                    360 - _directed_angle(weak[p], longitudes[p]),
                )
            )
            / 3.0,
            4,
        )
        for p in PLANETS
    }


def compute_naisargika_bala() -> dict[str, float]:
    return {p: round(60.0 * NATURAL_RANKS[p] / 7.0, 4) for p in PLANETS}


def _aspect_virupa(aspector: str, angle: float) -> float:
    if angle < 30 or angle >= 300:
        base = 0.0
    elif angle < 60:
        base = (angle - 30) / 2.0
    elif angle < 90:
        base = angle - 45.0
    elif angle < 120:
        base = (120 - angle) / 2.0 + 30.0
    elif angle < 150:
        base = 150.0 - angle
    elif angle < 180:
        base = 2.0 * (angle - 150.0)
    else:
        base = (300.0 - angle) / 2.0
    extra = 0.0
    if aspector == "Mars" and (90 <= angle < 120 or 210 <= angle < 240):
        extra = 15.0
    elif aspector == "Jupiter" and (120 <= angle < 150 or 240 <= angle < 270):
        extra = 30.0
    elif aspector == "Saturn" and (60 <= angle < 90 or 270 <= angle < 300):
        extra = 45.0
    return base + extra


def _planet_natures(longitudes: dict[str, float]) -> dict[str, str]:
    elongation = float(_directed_angle(longitudes["Sun"], longitudes["Moon"]))
    # Classical waxing / Shukla Paksha benefic Moon; Mercury benefic unless conjoined sole malefic without benefic
    signs = {p: int(longitudes[p] // 30) for p in PLANETS}
    moon_nature = "benefic" if 0 < elongation < 180 else "malefic"
    benefics = {"Jupiter", "Venus", *(("Moon",) if moon_nature == "benefic" else ())}
    malefics = {
        "Sun",
        "Mars",
        "Saturn",
        *(("Moon",) if moon_nature == "malefic" else ()),
    }
    merc_companions = {
        p for p in PLANETS if p != "Mercury" and signs[p] == signs["Mercury"]
    }
    merc_nature = (
        "malefic"
        if (merc_companions & malefics and not (merc_companions & benefics))
        else "benefic"
    )
    return {
        p: (
            "benefic"
            if p in benefics or (p == "Mercury" and merc_nature == "benefic")
            else "malefic"
        )
        for p in PLANETS
    }


def compute_drik_bala(longitudes: dict[str, float]) -> dict[str, Any]:
    natures = _planet_natures(longitudes)
    summary: dict[str, float] = {}
    for target in PLANETS:
        total = 0.0
        for aspector in PLANETS:
            if aspector == target:
                continue
            angle = float(_directed_angle(longitudes[aspector], longitudes[target]))
            val = _aspect_virupa(aspector, angle) / 4.0
            total += val if natures[aspector] == "benefic" else -val
        summary[target] = round(total, 4)
    return {"summary": summary, "natures": natures}


def compute_kala_and_cheshta(
    raw: dict[str, Any],
    solar_ctx: dict[str, Any],
    sthana: dict[str, dict[str, float]],
    dig: dict[str, float],
    birth_longitude: float,
    *,
    cheshta_model: str = "simon1994_j2000",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    longitudes = raw["longitudes"]
    jd_ut1 = raw["julian_day_ut"]
    jd_tt = raw["julian_day_tt"]
    natures = _planet_natures(longitudes)

    # Nathonnatha Bala
    arc = float(
        _directed_angle(
            raw["equatorial"]["Sun"]["right_ascension"],
            raw["local_apparent_sidereal_meridian"],
        )
    )
    night_val = min(arc, 360.0 - arc) / 3.0
    natha = {
        p: (
            60.0
            if p == "Mercury"
            else 60.0 - night_val if p in {"Sun", "Jupiter", "Venus"} else night_val
        )
        for p in PLANETS
    }

    # Paksha Bala
    elong = float(_directed_angle(longitudes["Sun"], longitudes["Moon"]))
    benefic_paksha = min(elong, 360.0 - elong) / 3.0
    paksha = {}
    for p in PLANETS:
        val = benefic_paksha if natures[p] == "benefic" else 60.0 - benefic_paksha
        paksha[p] = 2.0 * val if p == "Moon" else val

    # Tribhaga, Abda, Masa, Dina, Hora
    tribhaga = {
        p: (60.0 if p in {"Jupiter", solar_ctx.get("tribhaga_lord")} else 0.0)
        for p in PLANETS
    }
    # Ahargana for Abda & Masa lords
    from datetime import date

    ordinal = (
        math.floor(Fraction(jd_ut1) + Fraction(birth_longitude) / 360 + Fraction(1, 2))
        - 1_721_425
    )
    day = date.fromordinal(max(1, min(ordinal, date.max.toordinal())))
    ahargana = 714_404_108_573 + (day - date(1860, 1, 1)).days
    year_lord = WEEK[((ahargana // 360 * 3 + 1) % 7 - 1) % 7]
    month_lord = WEEK[((ahargana // 30 * 2 + 1) % 7 - 1) % 7]
    day_lord = solar_ctx.get("day_lord") or WEEK[(day.weekday() + 1) % 7]
    hora_lord = solar_ctx.get("hora_lord") or day_lord

    abda = {p: (15.0 if p == year_lord else 0.0) for p in PLANETS}
    masa = {p: (30.0 if p == month_lord else 0.0) for p in PLANETS}
    dina = {p: (45.0 if p == day_lord else 0.0) for p in PLANETS}
    hora = {p: (60.0 if p == hora_lord else 0.0) for p in PLANETS}

    # Ayana Bala
    ayana = {}
    for p in PLANETS:
        dec = float(raw["equatorial"][p]["declination"])
        signed = (
            abs(dec) if p == "Mercury" else -dec if p in {"Moon", "Saturn"} else dec
        )
        ayana[p] = (23.45 + signed) * 30.0 / 23.45 * (2.0 if p == "Sun" else 1.0)

    # Pre-war Kala sum & Yuddha (Planetary War)
    prewar = {
        p: round(
            natha[p] + paksha[p] + tribhaga[p] + abda[p] + masa[p] + dina[p] + hora[p],
            4,
        )
        for p in PLANETS
    }
    yuddha = dict.fromkeys(PLANETS, 0.0)
    war_pairs = []
    for a, b in combinations(STARS, 2):
        ang = float(_directed_angle(longitudes[a], longitudes[b]))
        sep = min(ang, 360.0 - ang)
        if sep < 1.0:
            winner, loser = (
                (a, b) if (longitudes[a] % 360.0) < (longitudes[b] % 360.0) else (b, a)
            )
            tot_a = sthana[a]["total_virupa"] + dig[a] + prewar[a]
            tot_b = sthana[b]["total_virupa"] + dig[b] + prewar[b]
            amt = abs(tot_a - tot_b) / abs(BIMBA[a] - BIMBA[b])
            yuddha[winner] += amt
            yuddha[loser] -= amt
            war_pairs.append(
                {
                    "winner": winner,
                    "loser": loser,
                    "separation_deg": round(sep, 4),
                    "amount_virupa": round(amt, 4),
                }
            )

    kala_summary = {p: round(prewar[p] + ayana[p] + yuddha[p], 4) for p in PLANETS}
    kala_record = {
        "status": "complete",
        "summary": kala_summary,
        "components": {
            "nathonnatha_bala": {p: round(v, 4) for p, v in natha.items()},
            "paksha_bala": {p: round(v, 4) for p, v in paksha.items()},
            "tribhaga_bala": tribhaga,
            "abda_bala": abda,
            "masa_bala": masa,
            "dina_bala": dina,
            "hora_bala": hora,
            "ayana_bala": {p: round(v, 4) for p, v in ayana.items()},
            "yuddha_bala": {p: round(v, 4) for p, v in yuddha.items()},
        },
        "war_pairs": war_pairs,
    }

    # Cheshta Bala (Sun = Ayana Bala, Moon = Paksha Bala, 5 stars via Simon1994 secular mean)
    means = (
        simon1994_mean_longitudes(jd_tt) if cheshta_model == "simon1994_j2000" else None
    )
    cheshta_summary: dict[str, float] = {
        "Sun": round(ayana["Sun"], 4),
        "Moon": round(paksha["Moon"], 4),
    }
    for p in STARS:
        if means is not None and p in raw.get("motion_true_j2000", {}):
            true_lon = raw["motion_true_j2000"][p]["longitude"]
            inner = p in {"Mercury", "Venus"}
            mean_lon = means["Sun"] if inner else means[p]
            seeghra = means[p] if inner else means["Sun"]
        else:
            # Fallback using tropical ecliptic true longitude vs mean Sun approximation
            mean_lon = float(longitudes["Sun"])
            true_lon = float(longitudes[p])
            seeghra = float(longitudes["Sun"])
        delta = (true_lon - mean_lon) % 360.0
        if delta > 180.0:
            delta -= 360.0
        midpoint = (mean_lon + delta / 2.0) % 360.0
        kendra = (seeghra - midpoint) % 360.0
        cheshta_summary[p] = round(min(kendra, 360.0 - kendra) / 3.0, 4)

    cheshta_record = {
        "status": "complete",
        "method": (
            "simon1994_secular_mean"
            if means is not None
            else "sidereal_angular_fallback"
        ),
        "summary": cheshta_summary,
    }
    return kala_record, cheshta_record, cheshta_summary


def compute_bhava_bala(
    longitudes: dict[str, float],
    ascendant: float,
    midheaven: float,
    total_virupa_by_planet: dict[str, float],
) -> list[dict[str, Any]]:
    """Compute Bhava Bala for all 12 Sripati houses (Adhipati + Dig + Drishti)."""
    chalit = bhava_chalit(longitudes, ascendant, midheaven)
    natures = _planet_natures(longitudes)
    asc_sign = int(ascendant // 30)
    rows = []
    for h_info in chalit["bhavas"]:
        h_num = h_info["house"]
        cusp = h_info["cusp"]
        sign_idx = int(cusp // 30)
        lord = RASI_LORDS[sign_idx]
        adhipati = total_virupa_by_planet[lord]

        # Classical Bhava Dig Bala by sign nature of cusp (Dual=Nara, Movable=Jalachara, Fixed=Chatushpada, Scorpio=Keeta)
        # Standard BPHS/Raman house digbala: Nara houses max at 1, Jalachara at 4, Chatushpada at 10, Keeta at 7
        if sign_idx == 7:
            pref = 7
        elif sign_idx in {2, 5, 6, 10}:  # Gemini, Virgo, Libra, Aquarius (Nara signs)
            pref = 1
        elif sign_idx in {3, 11}:  # Cancer, Pisces (Jalachara)
            pref = 4
        else:
            pref = 10
        dist_h = abs(h_num - pref)
        dist_h = min(dist_h, 12 - dist_h)
        bhava_dig = round((6 - dist_h) * 10.0, 4)

        # Bhava Drishti Bala: quarter aspect from all grahas (Jupiter & Mercury full weighted)
        drishti = 0.0
        for p in PLANETS:
            ang = float(_directed_angle(longitudes[p], cusp))
            raw_asp = _aspect_virupa(p, ang)
            weight = 1.0 if p in {"Jupiter", "Mercury"} else 0.25
            sign_mult = 1.0 if natures[p] == "benefic" else -1.0
            drishti += sign_mult * raw_asp * weight
        drishti = round(drishti, 4)
        total_v = round(adhipati + bhava_dig + drishti, 4)
        rows.append(
            {
                "house": h_num,
                "sign": SIGNS[sign_idx],
                "lord": lord,
                "bhavadhipati_bala": round(adhipati, 4),
                "bhava_digbala": bhava_dig,
                "bhava_drishti_bala": drishti,
                "total_virupa": total_v,
                "total_rupa": round(total_v / 60.0, 4),
            }
        )
    return rows


def calculate_shadbala_bundle(
    raw: dict[str, Any],
    birth_longitude: float,
    birth_latitude: float,
    *,
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
    cheshta_model: str = "simon1994_j2000",
) -> dict[str, Any]:
    """Compute complete 6-fold Shadbala totals, Ishta/Kashta Phala, and Bhava Bala."""
    longitudes = raw["longitudes"]
    sthana = compute_sthana_bala(
        longitudes,
        raw["ascendant"],
        saptavargaja_profile=saptavargaja_profile,
        drekkana_profile=drekkana_profile,
    )
    dig = compute_dig_bala(longitudes, raw["ascendant"], raw["midheaven"])
    naisargika = compute_naisargika_bala()
    drik = compute_drik_bala(longitudes)
    solar_ctx = fast_solar_context(
        raw["julian_day_ut"], birth_longitude, birth_latitude
    )
    kala, cheshta, cheshta_summary = compute_kala_and_cheshta(
        raw, solar_ctx, sthana, dig, birth_longitude, cheshta_model=cheshta_model
    )

    total_virupa: dict[str, float] = {}
    total_rupa: dict[str, float] = {}
    is_strong: dict[str, bool] = {}
    ishta_kashta: dict[str, dict[str, float]] = {}

    for p in PLANETS:
        tot_v = (
            sthana[p]["total_virupa"]
            + dig[p]
            + kala["summary"][p]
            + cheshta_summary[p]
            + naisargika[p]
            + drik["summary"][p]
        )
        tot_r = tot_v / 60.0
        total_virupa[p] = round(tot_v, 4)
        total_rupa[p] = round(tot_r, 4)
        is_strong[p] = tot_r >= REQUIRED_SHADBALA_RUPA[p]

        u_clamp = max(0.0, min(60.0, sthana[p]["uchcha_bala"]))
        c_clamp = max(0.0, min(60.0, cheshta_summary[p]))
        ishta_kashta[p] = {
            "ishta_phala": round(math.sqrt(u_clamp * c_clamp), 4),
            "kashta_phala": round(math.sqrt((60.0 - u_clamp) * (60.0 - c_clamp)), 4),
        }

    bhava_bala = compute_bhava_bala(
        longitudes, raw["ascendant"], raw["midheaven"], total_virupa
    )

    return {
        "solar_context": solar_ctx,
        "strengths": {
            "sthana_bala": {"status": "complete", "summary": sthana},
            "dig_bala": {"status": "complete", "summary": dig},
            "kala_bala": kala,
            "cheshta_bala": cheshta,
            "naisargika_bala": {"status": "complete", "summary": naisargika},
            "drik_bala": {"status": "complete", **drik},
            "shadbala_assessment": {
                "status": "complete",
                "computed": [
                    "sthana_bala",
                    "dig_bala",
                    "kala_bala",
                    "cheshta_bala",
                    "naisargika_bala",
                    "drik_bala",
                ],
                "total_virupa": total_virupa,
                "total_rupa": total_rupa,
                "required_rupa": REQUIRED_SHADBALA_RUPA,
                "is_strong": is_strong,
                "ishta_kashta": ishta_kashta,
            },
            "bhava_bala": bhava_bala,
        },
    }
