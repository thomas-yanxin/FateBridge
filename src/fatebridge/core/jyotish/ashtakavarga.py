"""Rao 2000 & Aiyar 1905 Ashtakavarga, Trikona & Ekadhipatya Sodhana, and Pinda (fixed equal-count rule)."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from fatebridge.core.astro.astrology_tables import SIGNS

REFERENCES = (
    "Sun",
    "Moon",
    "Mars",
    "Mercury",
    "Jupiter",
    "Venus",
    "Saturn",
    "Ascendant",
)
PLANETS = REFERENCES[:7]
TRINES = ((0, 4, 8), (1, 5, 9), (2, 6, 10), (3, 7, 11))
PAIRS = ((0, 7), (1, 6), (2, 5), (8, 11), (9, 10))
RASI_WEIGHTS = (7, 10, 8, 4, 10, 6, 7, 8, 9, 5, 11, 12)
GRAHA_WEIGHTS = (5, 5, 8, 5, 10, 7, 5)
BAV_TOTALS = dict(zip(REFERENCES, (48, 49, 39, 54, 56, 52, 39, 49)))

# Rao 2000 BAV relative houses 1..12; columns follow REFERENCES
RAO_HOUSE_ROWS = (
    (
        "10100010",
        "10100010",
        "01010001",
        "10100011",
        "00011000",
        "01011101",
        "10100110",
        "10100010",
        "10111010",
        "11110011",
        "11111011",
        "00010101",
    ),
    (
        "01011000",
        "00101000",
        "11110111",
        "00011100",
        "00110110",
        "11100011",
        "11011100",
        "10011000",
        "01000100",
        "11111101",
        "11111111",
        "00000000",
    ),
    (
        "00100011",
        "00100000",
        "11010001",
        "00100010",
        "10010000",
        "11011101",
        "00100010",
        "00100110",
        "00000010",
        "10101011",
        "11111111",
        "00001100",
    ),
    (
        "00110111",
        "01100111",
        "00010100",
        "01100111",
        "10010100",
        "11011001",
        "00100010",
        "01101111",
        "10110110",
        "01110011",
        "11111111",
        "10011000",
    ),
    (
        "10111001",
        "11111101",
        "10001010",
        "10111001",
        "01010111",
        "00010111",
        "11101001",
        "10101000",
        "11010101",
        "10111101",
        "11111101",
        "00000010",
    ),
    (
        "01000101",
        "01000101",
        "01110111",
        "01100111",
        "01011111",
        "00110000",
        "00000000",
        "11001111",
        "01111111",
        "00001110",
        "11111111",
        "11100000",
    ),
    (
        "10000001",
        "10000000",
        "01100011",
        "10000001",
        "00101010",
        "01111111",
        "10000000",
        "10010000",
        "00010000",
        "10110001",
        "11111111",
        "00111100",
    ),
    (
        "00111110",
        "00011100",
        "11100111",
        "10011110",
        "00001100",
        "11111011",
        "00001000",
        "00010100",
        "00001100",
        "11111011",
        "11111011",
        "11000000",
    ),
)

# Aiyar 1905 Brihat Jataka IX.1-7 positive relative houses (1-based)
AIYAR_POSITIVE_HOUSES: dict[str, dict[str, tuple[int, ...]]] = {
    "Sun": {
        "Sun": (1, 2, 4, 7, 8, 9, 10, 11),
        "Mars": (1, 2, 4, 7, 8, 9, 10, 11),
        "Saturn": (1, 2, 4, 7, 8, 9, 10, 11),
        "Venus": (6, 7, 12),
        "Jupiter": (5, 6, 9, 11),
        "Moon": (3, 6, 10, 11),
        "Mercury": (3, 5, 6, 9, 10, 11, 12),
        "Ascendant": (3, 4, 6, 10, 11, 12),
    },
    "Moon": {
        "Ascendant": (3, 6, 10, 11),
        "Mars": (2, 3, 5, 6, 9, 10, 11),
        "Moon": (1, 3, 6, 7, 10, 11),
        "Sun": (3, 6, 7, 8, 10, 11),
        "Saturn": (3, 5, 6, 11),
        "Mercury": (1, 3, 4, 5, 7, 8, 10, 11),
        "Jupiter": (1, 4, 7, 8, 10, 11, 12),
        "Venus": (3, 4, 5, 7, 9, 10, 11),
    },
    "Mars": {
        "Sun": (3, 5, 6, 10, 11),
        "Ascendant": (1, 3, 6, 10, 11),
        "Moon": (3, 6, 11),
        "Mars": (1, 2, 4, 7, 8, 10, 11),
        "Saturn": (1, 4, 7, 8, 9, 10, 11),
        "Mercury": (3, 5, 6, 11),
        "Venus": (6, 8, 11, 12),
        "Jupiter": (6, 10, 11, 12),
    },
    "Mercury": {
        "Venus": (1, 2, 3, 4, 5, 8, 9, 11),
        "Saturn": (1, 2, 4, 7, 8, 9, 10, 11),
        "Mars": (1, 2, 4, 7, 8, 9, 10, 11),
        "Jupiter": (6, 8, 11, 12),
        "Sun": (5, 6, 9, 11, 12),
        "Mercury": (1, 3, 5, 6, 9, 10, 11, 12),
        "Moon": (2, 4, 6, 8, 10, 11),
        "Ascendant": (1, 2, 4, 6, 8, 10, 11),
    },
    "Jupiter": {
        "Mars": (1, 2, 4, 7, 8, 10, 11),
        "Jupiter": (1, 2, 3, 4, 7, 8, 10, 11),
        "Sun": (1, 2, 3, 4, 7, 8, 9, 10, 11),
        "Venus": (2, 5, 6, 9, 10, 11),
        "Moon": (2, 5, 7, 9, 11),
        "Saturn": (3, 5, 6, 12),
        "Mercury": (1, 2, 4, 5, 6, 9, 10, 11),
        "Ascendant": (1, 2, 4, 5, 6, 7, 9, 10, 11),
    },
    "Venus": {
        "Ascendant": (1, 2, 3, 4, 5, 8, 9, 11),
        "Moon": (1, 2, 3, 4, 5, 8, 9, 11, 12),
        "Venus": (1, 2, 3, 4, 5, 8, 9, 10, 11),
        "Saturn": (3, 4, 5, 8, 9, 10, 11),
        "Sun": (8, 11, 12),
        "Jupiter": (5, 8, 9, 10, 11),
        "Mercury": (3, 5, 6, 9, 11),
        "Mars": (3, 5, 6, 9, 11, 12),
    },
    "Saturn": {
        "Saturn": (3, 5, 6, 11),
        "Mars": (3, 5, 6, 10, 11, 12),
        "Sun": (1, 2, 4, 7, 8, 10, 11),
        "Ascendant": (1, 3, 4, 6, 10, 11),
        "Mercury": (6, 8, 9, 10, 11, 12),
        "Moon": (3, 6, 11),
        "Venus": (6, 11, 12),
        "Jupiter": (5, 6, 11, 12),
    },
}


def calculate_rao(signs: Mapping[str, int]) -> dict[str, Any]:
    """Compute unreduced Rao 2000 Prastara, Bhinna (BAV), and Samudaya (SAV) Ashtakavarga."""
    if set(signs) != set(REFERENCES) or any(
        type(v) is not int or not 0 <= v < 12 for v in signs.values()
    ):
        raise ValueError(
            "Ashtakavarga requires 7 physical grahas + Ascendant signs 0..11"
        )
    pav: dict[str, dict[str, list[int]]] = {}
    bav: dict[str, list[int]] = {}
    for target, table in zip(REFERENCES, RAO_HOUSE_ROWS):
        contributions = {}
        for col, donor in enumerate(REFERENCES):
            vals = [0] * 12
            for offset, row in enumerate(table):
                vals[(signs[donor] + offset) % 12] = int(row[col])
            contributions[donor] = vals
        pav[target] = contributions
        bav[target] = [sum(row[s] for row in contributions.values()) for s in range(12)]
    sav = [sum(bav[t][s] for t in PLANETS) for s in range(12)]
    return {
        "profile": "rao",
        "input_sign_indices": dict(signs),
        "prastara": pav,
        "bhinna": bav,
        "samudaya": sav,
        "bhinna_totals": {t: sum(v) for t, v in bav.items()},
        "samudaya_total": sum(sav),
    }


def calculate_aiyar(signs: Mapping[str, int]) -> dict[str, Any]:
    """Compute unreduced Aiyar 1905 Brihat Jataka IX.1-7 Ashtakavarga."""
    if set(signs) != set(REFERENCES) or any(
        type(v) is not int or not 0 <= v < 12 for v in signs.values()
    ):
        raise ValueError(
            "Ashtakavarga requires 7 physical grahas + Ascendant signs 0..11"
        )
    pav = {
        p: {
            d: [
                int((sign - signs[d]) % 12 + 1 in AIYAR_POSITIVE_HOUSES[p][d])
                for sign in range(12)
            ]
            for d in REFERENCES
        }
        for p in PLANETS
    }
    bav = {
        p: [sum(pav[p][d][s] for d in REFERENCES) for s in range(12)] for p in PLANETS
    }
    sav = [sum(bav[p][s] for p in PLANETS) for s in range(12)]
    return {
        "profile": "aiyar",
        "input_sign_indices": dict(signs),
        "prastara": pav,
        "bhinna": bav,
        "samudaya": sav,
        "bhinna_totals": {p: sum(bav[p]) for p in PLANETS},
        "samudaya_total": sum(sav),
    }


def reduce_pinda(values: Sequence[int], signs: Mapping[str, int]) -> dict[str, Any]:
    """Apply Trikona Sodhana -> Ekadhipatya Sodhana -> Rasi/Graha/Sodhya Pinda cleanly."""
    raw = list(values)
    trinal = list(raw)
    for group in TRINES:
        sub = min(raw[i] for i in group)
        for s in group:
            trinal[s] = raw[s] - sub

    occupied = {signs[p] for p in PLANETS}
    sodhita = list(trinal)
    for a, b in PAIRS:
        va, vb = trinal[a], trinal[b]
        fa, fb = a in occupied, b in occupied
        if 0 in (va, vb) or (fa and fb):
            continue
        if not fa and not fb:
            sodhita[a] = sodhita[b] = 0 if va == vb else min(va, vb)
        else:
            empty, full = (b, a) if fa else (a, b)
            # Clear empty co-owned sign when equal nonzero (fixes None cascade)
            sodhita[empty] = 0 if trinal[empty] <= trinal[full] else trinal[full]

    rasi_pinda = sum(v * w for v, w in zip(sodhita, RASI_WEIGHTS))
    graha_pinda = sum(sodhita[signs[p]] * w for p, w in zip(PLANETS, GRAHA_WEIGHTS))
    return {
        "trikona": trinal,
        "sodhita": sodhita,
        "rasi_pinda": rasi_pinda,
        "graha_pinda": graha_pinda,
        "sodhya_pinda": rasi_pinda + graha_pinda,
    }


def chart_inputs(chart: dict[str, Any]) -> dict[str, int]:
    points = {"Ascendant": chart["ascendant"]}
    for pt in chart["planets"]:
        if pt["id"] in REFERENCES:
            points[pt["id"]] = pt
    return {name: SIGNS.index(points[name]["sign"]) for name in REFERENCES}


def for_charts(
    charts: dict[str, Any], *, profile: Literal["rao", "aiyar"] = "rao"
) -> dict[str, Any]:
    """Build complete Ashtakavarga (BAV/SAV/PAV + Pinda reductions) for requested charts."""
    if profile not in ("rao", "aiyar"):
        raise ValueError("ashtakavarga profile 必须为 rao 或 aiyar。")
    calc_fn = calculate_rao if profile == "rao" else calculate_aiyar
    results = {}
    for name, chart in charts.items():
        signs = chart_inputs(chart)
        table = calc_fn(signs)
        occ = {p: signs[p] for p in PLANETS}
        pinda = {p: reduce_pinda(table["bhinna"][p], occ) for p in PLANETS}
        results[name] = {
            **table,
            "pinda": pinda,
        }
    return {
        "status": "complete",
        "profile": profile,
        "sign_order": list(SIGNS),
        "charts": results,
    }
