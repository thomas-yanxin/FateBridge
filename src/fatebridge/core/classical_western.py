"""Western classical-astrology primitives (Hellenistic / medieval).

Phase 1 of the 西占古典深度段 project: per-planet essential + accidental
condition, shared by ``astro_chart`` (the new ``classical`` layer) and the
horary engine. Dignity tables are reused from :mod:`fatebridge.core.astrology_tables`
(single source); only the genuinely
missing pieces — Chaldean faces, Dorothean triplicity rulers, Lilly dignity
scores, combustion / orientality / sect / joy — are added here.

Reference data ported verbatim from horosa `data/dignities.js` (Egyptian terms,
Dorothean triplicity, Chaldean faces, Lilly scores); derivation logic follows
the standard classical definitions those tables cite (Ptolemy / Lilly /
Dorotheus). There is no closed byte-oracle, so correctness is pinned by
table-parity + classical invariants (see tests).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fatebridge.core.astrology_tables import (
    DOMICILE_RULERS,
    EGYPTIAN_BOUNDS_BY_SIGN,
    ELEMENT_BY_SIGN,
    EXALTATION_SIGNS,
    RULER_BY_SIGN,
    SIGNS,
    _opposite_sign,
)

# Chaldean decan faces — each sign's three 10° faces, Chaldean order from Mars at
# 0° Aries. Ported verbatim from horosa data/dignities.js FACES (lowercased there).
CHALDEAN_FACES: Dict[str, List[str]] = {
    "Aries": ["Mars", "Sun", "Venus"],
    "Taurus": ["Mercury", "Moon", "Saturn"],
    "Gemini": ["Jupiter", "Mars", "Sun"],
    "Cancer": ["Venus", "Mercury", "Moon"],
    "Leo": ["Saturn", "Jupiter", "Mars"],
    "Virgo": ["Sun", "Venus", "Mercury"],
    "Libra": ["Moon", "Saturn", "Jupiter"],
    "Scorpio": ["Mars", "Sun", "Venus"],
    "Sagittarius": ["Mercury", "Moon", "Saturn"],
    "Capricorn": ["Jupiter", "Mars", "Sun"],
    "Aquarius": ["Venus", "Mercury", "Moon"],
    "Pisces": ["Saturn", "Jupiter", "Mars"],
}

# Dorothean triplicity rulers by element → day / night / participating ruler.
DOROTHEAN_TRIPLICITY: Dict[str, Dict[str, str]] = {
    "Fire": {"day": "Sun", "night": "Jupiter", "participating": "Saturn"},
    "Earth": {"day": "Venus", "night": "Moon", "participating": "Mars"},
    "Air": {"day": "Saturn", "night": "Mercury", "participating": "Jupiter"},
    "Water": {"day": "Venus", "night": "Mars", "participating": "Moon"},
}

# Lilly's essential-dignity scores (domicile +5 … face +1; detriment −5 / fall −4).
DIGNITY_SCORE: Dict[str, int] = {
    "rulership": 5,
    "exaltation": 4,
    "triplicity": 3,
    "bound": 2,
    "face": 1,
    "detriment": -5,
    "fall": -4,
}

DIGNITY_LABELS_ZH: Dict[str, str] = {
    "rulership": "庙",
    "exaltation": "旺",
    "triplicity": "三分",
    "bound": "界",
    "face": "面",
    "detriment": "陷",
    "fall": "弱",
    "peregrine": "平",
}

# Planetary joys by house (Hellenistic): Mercury 1, Moon 3, Venus 5, Mars 6,
# Sun 9, Jupiter 11, Saturn 12.
PLANETARY_JOYS: Dict[str, int] = {
    "Mercury": 1,
    "Moon": 3,
    "Venus": 5,
    "Mars": 6,
    "Sun": 9,
    "Jupiter": 11,
    "Saturn": 12,
}

# Natural sect of the seven traditional planets (Mercury is sect-neutral —
# resolved by orientality at call sites).
DIURNAL_PLANETS = frozenset({"Sun", "Jupiter", "Saturn"})
NOCTURNAL_PLANETS = frozenset({"Moon", "Venus", "Mars"})

TRADITIONAL_PLANETS = frozenset(
    {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
)

# Combustion thresholds (degrees) — cazimi 17′, combust 8.5°, under-beams 15°.
# Under-the-sunbeams uses the Sun's moiety of 15° (Lilly, CA p.113); this matches
# the solar moiety in ``astrology_horary.PLANET_MOIETIES``.
_COMBUST_CAZIMI = 17.0 / 60.0
_COMBUST_LIMIT = 8.5
_UNDER_BEAMS_LIMIT = 15.0
# Max separation for enclosure/besiegement by body — flanking bodies must be
# within this orb on each side, else nearest-neighbour over-reports.
_ENCLOSURE_ORB = 15.0
# Solar obliquity bound — a body beyond this declination is "out of bounds".
OUT_OF_BOUNDS_LIMIT = 23.4367


def _angular_distance(first: float, second: float) -> float:
    """Unsigned 0–180° separation."""
    diff = abs((first - second) % 360.0)
    return min(diff, 360.0 - diff)


def _signed_delta(reference: float, target: float) -> float:
    """``target − reference`` folded into (−180, 180]."""
    return (target - reference + 540.0) % 360.0 - 180.0


def bound_lord(sign: str, degree_in_sign: float) -> Optional[str]:
    """Egyptian-term (bound) lord at this sign + degree."""
    for lord, start, end in EGYPTIAN_BOUNDS_BY_SIGN.get(sign, []):
        if start <= degree_in_sign < end:
            return lord
    return None


def face_lord(sign: str, degree_in_sign: float) -> Optional[str]:
    """Chaldean face (decan) lord at this sign + degree."""
    faces = CHALDEAN_FACES.get(sign)
    if not faces:
        return None
    return faces[min(2, int(degree_in_sign // 10))]


def triplicity_members(sign: str) -> List[str]:
    """All three Dorothean triplicity rulers of the sign's element (unordered).

    Used for reception / horary's membership-style dignity flag.
    """
    rulers = DOROTHEAN_TRIPLICITY.get(ELEMENT_BY_SIGN.get(sign, ""))
    if not rulers:
        return []
    return [rulers["day"], rulers["night"], rulers["participating"]]


def triplicity_ruler(sign: str, is_day: bool) -> Optional[str]:
    """The sect triplicity ruler (Lilly scores the in-sect ruler +3)."""
    rulers = DOROTHEAN_TRIPLICITY.get(ELEMENT_BY_SIGN.get(sign, ""))
    if not rulers:
        return None
    return rulers["day"] if is_day else rulers["night"]


def _detriment_signs(planet: str) -> set:
    return {_opposite_sign(s) for s in DOMICILE_RULERS.get(planet, ())}


def essential_dignities(
    planet: str, sign: str, degree_in_sign: float, is_day: bool
) -> Optional[Dict[str, Any]]:
    """Full classical essential-dignity picture for a traditional planet.

    Returns the dignities held (rulership/exaltation/triplicity/bound/face) and
    debilities (detriment/fall), a Lilly score, and the bound/triplicity/face
    lords of the placement. ``None`` for non-traditional bodies (outers/nodes).
    """
    if planet not in TRADITIONAL_PLANETS:
        return None

    held: List[str] = []
    if sign in DOMICILE_RULERS.get(planet, ()):
        held.append("rulership")
    if EXALTATION_SIGNS.get(planet) == sign:
        held.append("exaltation")
    if triplicity_ruler(sign, is_day) == planet:
        held.append("triplicity")
    if bound_lord(sign, degree_in_sign) == planet:
        held.append("bound")
    if face_lord(sign, degree_in_sign) == planet:
        held.append("face")

    debilities: List[str] = []
    if sign in _detriment_signs(planet):
        debilities.append("detriment")
    if sign == _opposite_sign(EXALTATION_SIGNS.get(planet, "")):
        debilities.append("fall")

    score = sum(DIGNITY_SCORE[d] for d in held) + sum(
        DIGNITY_SCORE[d] for d in debilities
    )
    peregrine = not held and not debilities

    return {
        "dignities": held,
        "debilities": debilities,
        "peregrine": peregrine,
        "score": score,
        "bound_lord": bound_lord(sign, degree_in_sign),
        "triplicity_ruler": triplicity_ruler(sign, is_day),
        "face_lord": face_lord(sign, degree_in_sign),
        "labels_zh": [DIGNITY_LABELS_ZH[d] for d in held]
        + [DIGNITY_LABELS_ZH[d] for d in debilities]
        + (["平"] if peregrine else []),
    }


def is_above_horizon(house: Optional[int]) -> Optional[bool]:
    """Houses 7–12 are above the horizon (Desc → MC → Asc)."""
    if not house:
        return None
    return house >= 7


def angularity(house: Optional[int]) -> Optional[str]:
    """Angular (1/4/7/10) · succedent (2/5/8/11) · cadent (3/6/9/12)."""
    if not house:
        return None
    if house in (1, 4, 7, 10):
        return "angular"
    if house in (2, 5, 8, 11):
        return "succedent"
    return "cadent"


def combustion_state(planet_lon: float, sun_lon: Optional[float]) -> Optional[str]:
    """cazimi (≤17′) · combust (<8.5°) · under_beams (<15°), else None."""
    if sun_lon is None:
        return None
    distance = _angular_distance(planet_lon, sun_lon)
    if distance <= _COMBUST_CAZIMI:
        return "cazimi"
    if distance < _COMBUST_LIMIT:
        return "combust"
    if distance < _UNDER_BEAMS_LIMIT:
        return "under_beams"
    return None


def orientality(planet_lon: float, sun_lon: Optional[float]) -> Optional[str]:
    """oriental (rises before the Sun) / occidental (sets after)."""
    if sun_lon is None:
        return None
    delta = _signed_delta(sun_lon, planet_lon)  # planet − sun ∈ (−180, 180]
    if abs(delta) < 1e-4:
        return None
    return "oriental" if delta < 0 else "occidental"


def planet_sect(planet: str, orientality_value: Optional[str]) -> Optional[str]:
    """Natural sect of a planet; Mercury follows its orientality."""
    if planet in DIURNAL_PLANETS:
        return "day"
    if planet in NOCTURNAL_PLANETS:
        return "night"
    if planet == "Mercury":
        if orientality_value == "oriental":
            return "day"
        if orientality_value == "occidental":
            return "night"
    return None


def sect_placement(
    planet: str, chart_sect: Optional[str], orientality_value: Optional[str]
) -> Optional[str]:
    """Whether the planet is of the chart's sect or contrary to it."""
    own = planet_sect(planet, orientality_value)
    if own is None or chart_sect is None:
        return None
    return "of_sect" if own == chart_sect else "contrary_to_sect"


def in_halb(
    planet: str,
    chart_sect: Optional[str],
    above_horizon: Optional[bool],
    orientality_value: Optional[str],
) -> Optional[bool]:
    """Rejoicing by halb: an of-sect planet on its preferred side of the horizon
    (diurnal above by day / nocturnal below by day, and vice-versa)."""
    own = planet_sect(planet, orientality_value)
    if own is None or chart_sect is None or above_horizon is None:
        return None
    if own != chart_sect:
        return False
    if chart_sect == "day":
        return above_horizon if own == "day" else not above_horizon
    return not above_horizon if own == "day" else above_horizon


def planetary_joy(planet: str, house: Optional[int]) -> bool:
    return bool(house) and PLANETARY_JOYS.get(planet) == house


def is_retrograde(longitude_speed: Optional[float]) -> Optional[bool]:
    """Retrograde when ecliptic longitude speed is negative.

    ``None`` when the speed is unknown — the offline approximate orbital model
    supplies no per-planet speed, so we report "unknown" rather than fabricate a
    direction the engine never computed.
    """
    if longitude_speed is None:
        return None
    return longitude_speed < 0.0


def out_of_bounds(declination: Optional[float]) -> Optional[bool]:
    """A body is *out of bounds* when its declination exceeds the Sun's maximum.

    Beyond ±23.44° a planet stands outside the band the Sun ever reaches, a
    classical mark of unruly / extra-potent expression. ``None`` when declination
    is unknown (offline engine — declination needs the equatorial ephemeris).
    """
    if declination is None:
        return None
    return abs(declination) > OUT_OF_BOUNDS_LIMIT


# ── Phase 2: almuten (essential-dignity rulership of a degree) + dispositors ──

# Reverse of EXALTATION_SIGNS: sign → the planet exalted there (7 of 12 signs).
EXALT_RULER_BY_SIGN: Dict[str, str] = {
    sign: planet for planet, sign in EXALTATION_SIGNS.items()
}

# Five essential-dignity weights used to score an almuten (Lilly / Ibn Ezra).
_ALMUTEN_WEIGHTS = {
    "domicile": DIGNITY_SCORE["rulership"],
    "exaltation": DIGNITY_SCORE["exaltation"],
    "triplicity": DIGNITY_SCORE["triplicity"],
    "term": DIGNITY_SCORE["bound"],
    "face": DIGNITY_SCORE["face"],
}


def dignity_lords_at(
    sign: str, degree_in_sign: float, is_day: bool
) -> Dict[str, Optional[str]]:
    """The five essential-dignity lords of a point (domicile/exalt/trip/term/face)."""
    return {
        "domicile": RULER_BY_SIGN.get(sign),
        "exaltation": EXALT_RULER_BY_SIGN.get(sign),
        "triplicity": triplicity_ruler(sign, is_day),
        "term": bound_lord(sign, degree_in_sign),
        "face": face_lord(sign, degree_in_sign),
    }


# Chaldean (slowest-first) order — the deterministic tie-break for any almuten.
_CHALDEAN_ORDER = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]


def _almuten_winner(totals: Dict[str, int]) -> Optional[str]:
    """The strongest planet in a weighted-dignity tally.

    Deterministic tie-break: higher score, then Chaldean (slowest-first) order —
    so identical sums resolve to the slower planet. Shared by the per-degree
    almuten and the whole-chart Almuten Figuris.
    """
    if not totals:
        return None
    return max(
        totals,
        key=lambda p: (
            totals[p],
            -_CHALDEAN_ORDER.index(p) if p in _CHALDEAN_ORDER else 0,
        ),
    )


def almuten_of(sign: str, degree_in_sign: float, is_day: bool) -> Dict[str, Any]:
    """Almuten of a degree: the planet with the most weighted essential dignity.

    Sums the 5 dignity weights (5/4/3/2/1) each planet earns over the point;
    the winner is the strongest ruler. Ties resolve to the heavier dignity then
    the traditional Chaldean order (slowest first) for determinism.
    """
    lords = dignity_lords_at(sign, degree_in_sign, is_day)
    totals: Dict[str, int] = {}
    for dignity, weight in _ALMUTEN_WEIGHTS.items():
        lord = lords[dignity]
        if lord:
            totals[lord] = totals.get(lord, 0) + weight
    return {"winner": _almuten_winner(totals), "totals": totals, "lords": lords}


def planetary_hour_sequence(day_ruler: str) -> List[str]:
    """The 24 planetary-hour rulers of one sunrise-to-sunrise day.

    Hour 1 (the first after sunrise) is ruled by ``day_ruler`` — the planet of
    the weekday — and each subsequent hour steps through the Chaldean
    (slowest-first) order. Indices 0–11 are the twelve day hours; 12–23 the
    twelve night hours. Returns ``[]`` for a non-traditional ``day_ruler``.

    Cycling 24 hours lands the next day's first hour on the next weekday's
    planet — this is exactly why the days of the week run in their order.
    """
    if day_ruler not in _CHALDEAN_ORDER:
        return []
    start = _CHALDEAN_ORDER.index(day_ruler)
    return [_CHALDEAN_ORDER[(start + offset) % 7] for offset in range(24)]


# Almuten Figuris (命主 / Lord of the Nativity, Ibn Ezra) is elected over five
# hylegic points. Order is fixed for deterministic JSON; ``syzygy`` is dropped on
# the offline engine (it needs the prenatal lunation, an ephemeris search).
ALMUTEN_FIGURIS_POINTS = ("Sun", "Moon", "Ascendant", "fortune", "syzygy")


def build_almuten_figuris(
    points: Dict[str, Dict[str, Any]], is_day: bool
) -> Dict[str, Any]:
    """Almuten Figuris (命主): the planet ruling the chart's hylegic points.

    ``points`` maps each point id (see :data:`ALMUTEN_FIGURIS_POINTS`) to a
    ``{"sign", "degree_in_sign"}`` placement; only the points the engine could
    supply are passed. Each point contributes the weighted essential-dignity
    tally of :func:`almuten_of`; summing those tallies across every point names
    the chart's overall ruler. Same Chaldean tie-break as the per-degree almuten.
    """
    totals: Dict[str, int] = {}
    per_point: Dict[str, Any] = {}
    for point_id in ALMUTEN_FIGURIS_POINTS:
        placement = points.get(point_id)
        if not placement:
            continue
        sign = placement.get("sign")
        degree = placement.get("degree_in_sign")
        if not sign or degree is None:
            continue
        result = almuten_of(sign, float(degree), is_day)
        per_point[point_id] = {
            "sign": sign,
            "degree_in_sign": round(float(degree), 4),
            "winner": result["winner"],
            "totals": result["totals"],
        }
        for planet, weight in result["totals"].items():
            totals[planet] = totals.get(planet, 0) + weight
    return {
        "winner": _almuten_winner(totals),
        "totals": totals,
        "points": per_point,
    }


def domicile_ruler(sign: str) -> Optional[str]:
    """Traditional domicile ruler of a sign (for dispositor chains)."""
    return RULER_BY_SIGN.get(sign)


def dispositor_chain(planet: str, placements: Dict[str, str]) -> Dict[str, Any]:
    """Follow the domicile-dispositor chain from ``planet``.

    ``placements`` maps planet → the sign it occupies. Each planet is disposited
    by the ruler of its sign; the chain walks rulers until it reaches a planet in
    its own domicile (final dispositor) or revisits a planet (mutual-reception /
    longer loop). Returns the visited chain + terminal info.
    """
    chain: List[str] = [planet]
    seen = {planet}
    current = planet
    while True:
        sign = placements.get(current)
        ruler = domicile_ruler(sign) if sign else None
        if ruler is None:
            return {"chain": chain, "terminal": None, "terminal_type": "unknown"}
        if ruler == current:
            return {"chain": chain, "terminal": current, "terminal_type": "domicile"}
        if ruler in seen:
            # Loop: a planet rules its own dispositor (mutual reception if length 2).
            kind = "mutual_reception" if ruler == planet and len(chain) == 2 else "loop"
            return {"chain": chain + [ruler], "terminal": ruler, "terminal_type": kind}
        chain.append(ruler)
        seen.add(ruler)
        current = ruler


def build_dispositor_layer(placements: Dict[str, str]) -> Dict[str, Any]:
    """Per-planet dispositor chains + the chart's final dispositor(s)."""
    chains = {planet: dispositor_chain(planet, placements) for planet in placements}
    finals = sorted(
        {
            info["terminal"]
            for info in chains.values()
            if info["terminal_type"] == "domicile" and info["terminal"]
        }
    )
    return {"chains": chains, "final_dispositors": finals}


def build_topic_almutens(
    houses: Dict[int, Dict[str, Any]], is_day: bool
) -> Dict[str, Dict[str, Any]]:
    """Almuten of each house cusp — the topic ruler of that house's matters.

    Keyed by the house number as a **string** so the structure round-trips
    identically through JSON (REST) and in-process (MCP) transports — JSON object
    keys are always strings, and the two surfaces must stay byte-identical.
    """
    topic: Dict[str, Dict[str, Any]] = {}
    for house_number, cusp in houses.items():
        sign = cusp.get("sign")
        degree = cusp.get("degree_in_sign")
        if not sign or degree is None:
            continue
        result = almuten_of(sign, degree, is_day)
        topic[str(house_number)] = {"sign": sign, "winner": result["winner"]}
    return topic


# ── Phase 3: Arabic lots (parts) ──

# Lot formulas: lon = (a + b − c) mod 360, with day/night reversal. Marker keys
# index into the longitude table (asc / sun / moon / planets).
# Ported verbatim from horosa data/lots.js (卜卦构建清单 §1.5).
LOTS: Dict[str, Dict[str, Any]] = {
    "fortune": {
        "cn": "福点",
        "use": "财富·失物·方位·身体",
        "day": ["asc", "moon", "sun"],
        "night": ["asc", "sun", "moon"],
    },
    "spirit": {
        "cn": "精神点",
        "use": "心智·事业·名望",
        "day": ["asc", "sun", "moon"],
        "night": ["asc", "moon", "sun"],
    },
    "marriage": {
        "cn": "婚姻点",
        "use": "婚姻（七宫）",
        "day": ["asc", "venus", "saturn"],
        "night": ["asc", "saturn", "venus"],
    },
    "children": {
        "cn": "子女点",
        "use": "子嗣（五宫）",
        "day": ["asc", "jupiter", "saturn"],
        "night": ["asc", "saturn", "jupiter"],
    },
}


def _sign_of_longitude(longitude: float) -> str:
    return SIGNS[int((longitude % 360.0) // 30.0)]


def compute_lot(formula: List[str], lons: Dict[str, float]) -> Optional[float]:
    """``lon = (a + b − c) mod 360`` from the longitude table; None if a marker missing."""
    a = lons.get(formula[0])
    b = lons.get(formula[1])
    c = lons.get(formula[2])
    if a is None or b is None or c is None:
        return None
    return ((a + b - c) % 360.0 + 360.0) % 360.0


def lot_dispositor(lot_longitude: float) -> Optional[str]:
    """Domicile ruler of the sign a lot falls in (its dispositor / 定位星)."""
    return RULER_BY_SIGN.get(_sign_of_longitude(lot_longitude))


def build_lots_layer(lons: Dict[str, float], is_day: bool) -> Dict[str, Any]:
    """Each Arabic lot's position + its domicile dispositor and weighted almuten."""
    out: Dict[str, Any] = {}
    for lot_id, definition in LOTS.items():
        formula = definition["day"] if is_day else definition["night"]
        lon = compute_lot(formula, lons)
        if lon is None:
            continue
        sign = _sign_of_longitude(lon)
        degree = lon % 30.0
        out[lot_id] = {
            "cn": definition["cn"],
            "longitude": round(lon, 4),
            "sign": sign,
            "degree_in_sign": round(degree, 4),
            "dispositor": RULER_BY_SIGN.get(sign),
            "almuten": almuten_of(sign, degree, is_day)["winner"],
        }
    return out


# ── Phase 4 / 4b: [古典格局] relational patterns ──────────────────────────────

BENEFICS = frozenset({"Jupiter", "Venus"})
MALEFICS = frozenset({"Mars", "Saturn"})
# Of-sect benefic/malefic: by day Jupiter/Saturn are the diurnal pair, by night
# Venus/Mars the nocturnal pair (the of-sect benefic helps most, of-sect malefic
# harms least).
_SECT_BENEFIC = {"day": "Jupiter", "night": "Venus"}
_SECT_MALEFIC = {"day": "Saturn", "night": "Mars"}

_SIGN_INDEX = {sign: index for index, sign in enumerate(SIGNS)}
# Whole-sign aspect by sign distance (both directions fold to the same aspect).
_WHOLE_SIGN_ASPECT = {
    0: "conjunction",
    2: "sextile",
    10: "sextile",
    3: "square",
    9: "square",
    4: "trine",
    8: "trine",
    6: "opposition",
}


def whole_sign_aspect(sign_a: str, sign_b: str) -> Optional[str]:
    """Classical whole-sign aspect between two signs (None = aversion)."""
    if sign_a not in _SIGN_INDEX or sign_b not in _SIGN_INDEX:
        return None
    distance = (_SIGN_INDEX[sign_b] - _SIGN_INDEX[sign_a]) % 12
    return _WHOLE_SIGN_ASPECT.get(distance)


def overcomes(sign_a: str, sign_b: str) -> bool:
    """True if A overcomes B — A in the 10th sign from B (superior dexter square)."""
    if sign_a not in _SIGN_INDEX or sign_b not in _SIGN_INDEX:
        return False
    return (_SIGN_INDEX[sign_a] - _SIGN_INDEX[sign_b]) % 12 == 9


# Exact Ptolemaic aspect angles, keyed by the aspect names ``_build_aspects`` emits.
_ASPECT_ANGLES = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}
# A planet within this orb of a square to the nodal axis sits "at the bending".
NODE_BENDING_ORB = 3.0
# Small forward step (days) for the applying/separating test.
_APPLY_PROBE_DAYS = 0.05


def _aspect_is_applying(
    lon_a: float,
    speed_a: Optional[float],
    lon_b: float,
    speed_b: Optional[float],
    exact_angle: float,
) -> Optional[bool]:
    """Whether an aspect is applying (separation nearing exact) vs separating.

    Steps both bodies forward a fraction of a day at their true (signed) speeds
    and asks whether the gap to the exact aspect angle shrank. ``None`` when a
    speed is unknown (offline engine) — applying/separating is then undefined.
    """
    if speed_a is None or speed_b is None:
        return None
    now = abs(_angular_distance(lon_a, lon_b) - exact_angle)
    later = abs(
        _angular_distance(
            lon_a + speed_a * _APPLY_PROBE_DAYS, lon_b + speed_b * _APPLY_PROBE_DAYS
        )
        - exact_angle
    )
    return later < now


def build_classical_patterns(
    planet_positions: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
    chart_sect: Optional[str],
    *,
    speeds: Optional[Dict[str, float]] = None,
    node_longitude: Optional[float] = None,
) -> Dict[str, Any]:
    """``[古典格局]`` relational layer over the seven traditional planets.

    Phase 4: aversion, overcoming (superior square), besiegement/enclosure by
    body, bonification/maltreatment. Phase 4b (needs ``speeds`` /
    ``node_longitude``, both from the ephemeris): translation & collection of
    light (applying/separating) and nodal bending. The 4b blocks stay empty when
    the inputs are absent (offline engine) rather than guessing.

    Only structural configurations are emitted — *which* planets, *what* relation.
    What a configuration signifies is the skills layer's job, not the engine's.
    """
    trad = [p for p in planet_positions if p["id"] in TRADITIONAL_PLANETS]
    by_id = {p["id"]: p for p in trad}
    speeds = speeds or {}

    # --- aversion: pairs sharing no whole-sign aspect ---
    aversions: List[List[str]] = []
    overcoming: List[Dict[str, str]] = []
    ids = [p["id"] for p in trad]
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            if whole_sign_aspect(by_id[a]["sign"], by_id[b]["sign"]) is None:
                aversions.append([a, b])
        # overcoming is directional — check both orders
        for b in ids:
            if a != b and overcomes(by_id[a]["sign"], by_id[b]["sign"]):
                overcoming.append({"overcomer": a, "overcome": b})

    # --- besiegement / enclosure by body (immediate longitude neighbours) ---
    # Enclosure by body requires the flanking bodies within ~15° on each side;
    # nearest-neighbour alone over-reports in sparse charts.
    ordered = sorted(trad, key=lambda p: p["longitude"])
    besiegement: Dict[str, str] = {}
    n = len(ordered)
    for index, planet in enumerate(ordered):
        if planet["id"] in BENEFICS or planet["id"] in MALEFICS:
            continue
        prev_p = ordered[(index - 1) % n]
        next_p = ordered[(index + 1) % n]
        within_orb = (
            _angular_distance(planet["longitude"], prev_p["longitude"])
            <= _ENCLOSURE_ORB
            and _angular_distance(planet["longitude"], next_p["longitude"])
            <= _ENCLOSURE_ORB
        )
        if not within_orb:
            continue
        prev_id, next_id = prev_p["id"], next_p["id"]
        if prev_id in MALEFICS and next_id in MALEFICS:
            besiegement[planet["id"]] = "besieged_by_malefics"
        elif prev_id in BENEFICS and next_id in BENEFICS:
            besiegement[planet["id"]] = "enclosed_by_benefics"

    # --- bonification / maltreatment by aspect to benefics / malefics ---
    bonification: Dict[str, Dict[str, List[str]]] = {
        pid: {"bonified_by": [], "maltreated_by": []} for pid in ids
    }
    for aspect in aspects:
        a, b = aspect.get("planet_a"), aspect.get("planet_b")
        for source, target in ((a, b), (b, a)):
            if target not in bonification:
                continue
            if source in BENEFICS:
                bonification[target]["bonified_by"].append(source)
            elif source in MALEFICS:
                bonification[target]["maltreated_by"].append(source)

    # --- Phase 4b: translation & collection of light (need applying/separating) ---
    # Aspect angle between two traditional planets, keyed by the unordered pair.
    pair_angle: Dict[frozenset, float] = {}
    for aspect in aspects:
        a, b = aspect.get("planet_a"), aspect.get("planet_b")
        angle = _ASPECT_ANGLES.get(str(aspect.get("aspect") or ""))
        if a in by_id and b in by_id and angle is not None:
            pair_angle[frozenset((a, b))] = angle

    def faster(p: str, q: str) -> bool:
        """``p`` outpaces ``q`` in longitude (by absolute speed)."""
        return abs(speeds.get(p, 0.0)) > abs(speeds.get(q, 0.0))

    def applying(source: str, target: str) -> Optional[bool]:
        angle = pair_angle.get(frozenset((source, target)))
        if angle is None:
            return None
        return _aspect_is_applying(
            by_id[source]["longitude"],
            speeds.get(source),
            by_id[target]["longitude"],
            speeds.get(target),
            angle,
        )

    translation: List[Dict[str, str]] = []
    collection: List[Dict[str, Any]] = []
    if all(speeds.get(pid) is not None for pid in ids):
        # Translation: a faster Z separates from X and applies to Y, where X and
        # Y are in aversion (no mutual aspect) — Z carries light from X to Y.
        for translator in ids:
            for source in ids:
                for sink in ids:
                    if len({translator, source, sink}) < 3:
                        continue
                    if frozenset((source, sink)) in pair_angle:
                        continue
                    if frozenset((translator, source)) not in pair_angle:
                        continue
                    if frozenset((translator, sink)) not in pair_angle:
                        continue
                    if not (faster(translator, source) and faster(translator, sink)):
                        continue
                    if applying(translator, source) is False and applying(
                        translator, sink
                    ):
                        translation.append(
                            {"translator": translator, "from": source, "to": sink}
                        )
        # Collection: a slower Z is applied to by two faster planets that are in
        # aversion to each other — Z gathers their light.
        for collector in ids:
            contributors = [
                other
                for other in ids
                if other != collector
                and frozenset((collector, other)) in pair_angle
                and faster(other, collector)
                and applying(other, collector)
            ]
            for i, first in enumerate(contributors):
                for second in contributors[i + 1 :]:
                    if frozenset((first, second)) in pair_angle:
                        continue
                    collection.append(
                        {"collector": collector, "from": sorted((first, second))}
                    )

    # --- Phase 4b: nodal bending (a planet square the nodal axis) ---
    nodal_bending: List[Dict[str, Any]] = []
    if node_longitude is not None:
        bending_points = {
            "north": (node_longitude + 90.0) % 360.0,
            "south": (node_longitude - 90.0) % 360.0,
        }
        for planet in trad:
            for side, point in bending_points.items():
                separation = _angular_distance(planet["longitude"], point)
                if separation <= NODE_BENDING_ORB:
                    nodal_bending.append(
                        {
                            "planet": planet["id"],
                            "bending": side,
                            "orb": round(separation, 4),
                        }
                    )

    return {
        "sect_benefic": _SECT_BENEFIC.get(chart_sect or ""),
        "sect_malefic": _SECT_MALEFIC.get(chart_sect or ""),
        "aversions": aversions,
        "overcoming": overcoming,
        "besiegement": besiegement,
        "translation_of_light": translation,
        "collection_of_light": collection,
        "nodal_bending": nodal_bending,
        "bonification": {
            k: v
            for k, v in bonification.items()
            if v["bonified_by"] or v["maltreated_by"]
        },
    }


# ── Phase 3b: fixed stars (恒星) ──────────────────────────────────────────────

# Curated classical catalogue: the 15 Behenian stars + 5 notable bright stars.
# ``lon2000`` / ``lat`` are the J2000.0 tropical ecliptic coordinates extracted
# from the Swiss Ephemeris star catalogue — a star's position is a public
# astronomical fact, so the numbers are vendored here even though the AGPL data
# file itself is never shipped (same stance as the .se1 ephemeris). ``nature`` is
# the Ptolemaic planetary nature (a cited traditional attribution, the raw
# material for a reading); ``cn`` the traditional Chinese name. Interpretation of
# what a conjunction *means* is the skills layer's job, not the engine's.
FIXED_STARS: Dict[str, Dict[str, Any]] = {
    "Algol": {
        "lon2000": 56.1682,
        "lat": 22.430,
        "nature": ["Saturn", "Jupiter"],
        "cn": "大陵五",
    },
    "Alcyone": {
        "lon2000": 59.9929,
        "lat": 4.051,
        "nature": ["Moon", "Mars"],
        "cn": "昴宿六",
    },
    "Aldebaran": {
        "lon2000": 69.7903,
        "lat": -5.468,
        "nature": ["Mars"],
        "cn": "毕宿五",
    },
    "Rigel": {
        "lon2000": 76.8319,
        "lat": -31.124,
        "nature": ["Jupiter", "Saturn"],
        "cn": "参宿七",
    },
    "Capella": {
        "lon2000": 81.8600,
        "lat": 22.865,
        "nature": ["Mars", "Mercury"],
        "cn": "五车二",
    },
    "Betelgeuse": {
        "lon2000": 88.7566,
        "lat": -16.027,
        "nature": ["Mars", "Mercury"],
        "cn": "参宿四",
    },
    "Sirius": {
        "lon2000": 104.0853,
        "lat": -39.605,
        "nature": ["Jupiter", "Mars"],
        "cn": "天狼",
    },
    "Pollux": {
        "lon2000": 113.2175,
        "lat": 6.684,
        "nature": ["Mars"],
        "cn": "北河三",
    },
    "Procyon": {
        "lon2000": 115.7875,
        "lat": -16.019,
        "nature": ["Mercury", "Mars"],
        "cn": "南河三",
    },
    "Regulus": {
        "lon2000": 149.8290,
        "lat": 0.465,
        "nature": ["Mars", "Jupiter"],
        "cn": "轩辕十四",
    },
    "Denebola": {
        "lon2000": 171.6156,
        "lat": 12.266,
        "nature": ["Saturn", "Venus"],
        "cn": "五帝座一",
    },
    "Algorab": {
        "lon2000": 193.4476,
        "lat": -12.195,
        "nature": ["Mars", "Saturn"],
        "cn": "轸宿三",
    },
    "Spica": {
        "lon2000": 203.8361,
        "lat": -2.054,
        "nature": ["Venus", "Mars"],
        "cn": "角宿一",
    },
    "Arcturus": {
        "lon2000": 204.2282,
        "lat": 30.733,
        "nature": ["Jupiter", "Mars"],
        "cn": "大角",
    },
    "Alphecca": {
        "lon2000": 222.2877,
        "lat": 44.320,
        "nature": ["Venus", "Mercury"],
        "cn": "贯索四",
    },
    "Antares": {
        "lon2000": 249.7534,
        "lat": -4.570,
        "nature": ["Mars", "Jupiter"],
        "cn": "心宿二",
    },
    "Vega": {
        "lon2000": 285.3003,
        "lat": 61.733,
        "nature": ["Venus", "Mercury"],
        "cn": "织女一",
    },
    "Deneb Algedi": {
        "lon2000": 323.5344,
        "lat": -2.602,
        "nature": ["Saturn", "Jupiter"],
        "cn": "垒壁阵四",
    },
    "Fomalhaut": {
        "lon2000": 333.8527,
        "lat": -21.137,
        "nature": ["Venus", "Mercury"],
        "cn": "北落师门",
    },
    "Markab": {
        "lon2000": 353.4799,
        "lat": 19.408,
        "nature": ["Mars", "Mercury"],
        "cn": "室宿一",
    },
}

# General precession in tropical longitude (IAU): ~50.2877″/yr. Fixed-star
# longitudes advance by this much; over modern births it dominates the much
# smaller proper motion, keeping vendored J2000 values accurate within a few
# arc-seconds (well inside the 1° conjunction orb).
PRECESSION_DEG_PER_YEAR = 50.2877 / 3600.0
_J2000_JD = 2451545.0
# Classical fixed-star conjunctions use a tight orb; 1° is the common default.
FIXED_STAR_ORB = 1.0


def fixed_star_longitude(lon2000: float, julian_day: float) -> float:
    """Precess a J2000 ecliptic longitude to ``julian_day`` (tropical, mod 360)."""
    years = (julian_day - _J2000_JD) / 365.25
    return (lon2000 + PRECESSION_DEG_PER_YEAR * years) % 360.0


def build_fixed_star_hits(
    points: Dict[str, float], julian_day: float, orb: float = FIXED_STAR_ORB
) -> List[Dict[str, Any]]:
    """Conjunctions of catalogue stars to chart points, within ``orb`` degrees.

    ``points`` maps a point id (planet / Ascendant / Midheaven) to its longitude.
    Pure computation — the star longitudes come from the vendored J2000 table
    precessed to date, so this needs no ephemeris data file and runs everywhere.
    Sorted by orb (tightest first), then star then point for determinism.
    """
    hits: List[Dict[str, Any]] = []
    for star, data in FIXED_STARS.items():
        star_lon = fixed_star_longitude(data["lon2000"], julian_day)
        for point_id, point_lon in points.items():
            separation = _angular_distance(star_lon, point_lon)
            if separation <= orb:
                hits.append(
                    {
                        "star": star,
                        "cn": data["cn"],
                        "point": point_id,
                        "orb": round(separation, 4),
                        "star_longitude": round(star_lon, 4),
                        "nature": data["nature"],
                    }
                )
    hits.sort(key=lambda hit: (hit["orb"], hit["star"], hit["point"]))
    return hits


# ── Phase 5: dodekatemoria (12分度) + melothesia (身体部位) + temperament (气质) ──

# Sign → governed body parts (head-to-foot). Ported verbatim from horosa
# data/signs.js body_parts (卜卦构建清单 §1.6).
SIGN_BODY_PARTS: Dict[str, List[str]] = {
    "Aries": ["头", "脸", "眼", "鼻", "耳"],
    "Taurus": ["喉", "颈", "甲状腺"],
    "Gemini": ["手臂", "肩", "肺", "神经", "气管"],
    "Cancer": ["胃", "胸", "子宫", "卵巢", "牙"],
    "Leo": ["心脏", "脊椎", "背", "脊髓"],
    "Virgo": ["小肠", "胰", "脾", "腹", "十二指肠"],
    "Libra": ["下背", "肾", "静脉", "卵巢"],
    "Scorpio": ["生殖", "排泄", "结肠", "膀胱", "摄护腺"],
    "Sagittarius": ["大腿", "臀", "坐骨神经", "肝", "动脉"],
    "Capricorn": ["膝", "关节", "胆囊", "头发", "皮肤"],
    "Aquarius": ["小腿", "踝", "血液循环", "脊髓"],
    "Pisces": ["脚掌", "淋巴"],
}

# Classical primary qualities. Sign qualities follow the element; planet
# qualities ported from horosa data/planets.js (Mercury = common/neutral).
ELEMENT_QUALITIES: Dict[str, List[str]] = {
    "Fire": ["hot", "dry"],
    "Earth": ["cold", "dry"],
    "Air": ["hot", "moist"],
    "Water": ["cold", "moist"],
}
PLANET_QUALITIES: Dict[str, List[str]] = {
    "Sun": ["hot", "dry"],
    "Moon": ["cold", "moist"],
    "Mercury": [],  # common / takes on what it is connected to
    "Venus": ["cold", "moist"],
    "Mars": ["hot", "dry"],
    "Jupiter": ["hot", "moist"],
    "Saturn": ["cold", "dry"],
}
# Humor by dominant (thermal, hygral) quality pair.
_HUMORS = {
    ("hot", "moist"): {"humor": "sanguine", "cn": "多血质（风）"},
    ("hot", "dry"): {"humor": "choleric", "cn": "胆汁质（火）"},
    ("cold", "dry"): {"humor": "melancholic", "cn": "忧郁质（土）"},
    ("cold", "moist"): {"humor": "phlegmatic", "cn": "粘液质（水）"},
}


def dodekatemorion(sign: str, degree_in_sign: float) -> Optional[str]:
    """12分度: the sign reached by advancing ``floor(degree / 2.5)`` signs from
    the planet's own sign (each 30° sign carries all 12 in 2.5° steps)."""
    if sign not in _SIGN_INDEX:
        return None
    step = int((degree_in_sign % 30.0) // 2.5)
    return SIGNS[(_SIGN_INDEX[sign] + step) % 12]


# Ninth-part (九分部 / navamsa) opening sign by triplicity — the cardinal sign of
# the placement's own element. Fire→Aries, Earth→Capricorn, Air→Libra, Water→
# Cancer (the dominant Parashari convention, equivalent to the Hellenistic
# ninth-part's triplicity reset). Pure geometry; no degree-ruler doctrine.
_NINTH_PART_START = {
    "Fire": "Aries",
    "Earth": "Capricorn",
    "Air": "Libra",
    "Water": "Cancer",
}
# 30° / 9 = 3°20′ per ninth-part.
_NINTH_PART_ARC = 30.0 / 9.0


def ninth_part(sign: str, degree_in_sign: float) -> Optional[str]:
    """九分部 (ninth-part / navamsa): the sign of the 3°20′ division.

    Each sign splits into nine 3°20′ parts; the first opens on the cardinal sign
    of the placement's triplicity and successive parts advance one sign
    zodiacally. ``None`` for a non-zodiacal sign.
    """
    start = _NINTH_PART_START.get(ELEMENT_BY_SIGN.get(sign, ""))
    if start is None:
        return None
    step = int((degree_in_sign % 30.0) // _NINTH_PART_ARC)
    return SIGNS[(_SIGN_INDEX[start] + step) % 12]


def _degree_position(degree_in_sign: float) -> str:
    deg = degree_in_sign % 30.0
    if deg < 10:
        return "上方"
    if deg < 20:
        return "中间"
    return "下方"


def melothesia(sign: str, degree_in_sign: float) -> Dict[str, Any]:
    """Body parts governed by the sign + the early/middle/late degree band."""
    return {
        "body_parts": SIGN_BODY_PARTS.get(sign, []),
        "position": _degree_position(degree_in_sign),
    }


def build_temperament(
    asc_sign: Optional[str],
    asc_ruler: Optional[str],
    sun_sign: Optional[str],
    moon_sign: Optional[str],
) -> Dict[str, Any]:
    """Simplified Lilly-style qualities tally → dominant humor.

    Tallies the primary qualities of the Ascendant / Sun / Moon signs (by
    element) plus the planetary qualities of the Ascendant ruler, Sun and Moon.
    The dominant thermal (hot/cold) and hygral (dry/moist) pair names the humor.
    """
    tally = {"hot": 0, "cold": 0, "dry": 0, "moist": 0}

    def add_sign(sign: Optional[str]) -> None:
        for quality in ELEMENT_QUALITIES.get(ELEMENT_BY_SIGN.get(sign or "", ""), []):
            tally[quality] += 1

    def add_planet(planet: Optional[str]) -> None:
        for quality in PLANET_QUALITIES.get(planet or "", []):
            tally[quality] += 1

    add_sign(asc_sign)
    add_sign(sun_sign)
    add_sign(moon_sign)
    add_planet(asc_ruler)
    add_planet("Sun")
    add_planet("Moon")

    thermal = "hot" if tally["hot"] >= tally["cold"] else "cold"
    hygral = "moist" if tally["moist"] >= tally["dry"] else "dry"
    humor = _HUMORS[(thermal, hygral)]
    return {"tally": tally, "thermal": thermal, "hygral": hygral, **humor}


def build_planet_classical(
    *,
    planet: str,
    sign: str,
    degree_in_sign: float,
    longitude: float,
    house: Optional[int],
    sun_longitude: Optional[float],
    chart_sect: Optional[str],
    longitude_speed: Optional[float] = None,
    declination: Optional[float] = None,
) -> Dict[str, Any]:
    """The per-planet ``classical`` entry surfaced on the chart payload.

    ``longitude_speed`` / ``declination`` come from the equatorial ephemeris and
    drive the ``retrograde`` / ``out_of_bounds`` accidental flags; both are
    ``None`` on the offline approximate engine, where direction and declination
    are unknowable rather than zero.
    """
    above = is_above_horizon(house)
    orient = None if planet == "Sun" else orientality(longitude, sun_longitude)
    return {
        "essential": essential_dignities(
            planet, sign, degree_in_sign, chart_sect == "day"
        ),
        "angularity": angularity(house),
        "above_horizon": above,
        "combustion": (
            None if planet == "Sun" else combustion_state(longitude, sun_longitude)
        ),
        "orientality": orient,
        "sect_placement": sect_placement(planet, chart_sect, orient),
        "in_halb": in_halb(planet, chart_sect, above, orient),
        "joy": planetary_joy(planet, house),
        "retrograde": is_retrograde(longitude_speed),
        "out_of_bounds": out_of_bounds(declination),
        "dodekatemorion": dodekatemorion(sign, degree_in_sign),
        "ninth_part": ninth_part(sign, degree_in_sign),
        "melothesia": melothesia(sign, degree_in_sign),
    }
