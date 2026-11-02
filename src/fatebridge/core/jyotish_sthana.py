"""Five positional-strength components under explicit source profiles.

No complete Shadbala, planetary beneficence or event probability is inferred.
Saptavargaja readings are kept separate: coefficients and moolatrikona scope
must never be silently blended to agree with a reference implementation.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.jyotish_relationships import relationship
from fatebridge.core.jyotish_strength import MOOLA, PEAKS, SOURCE_ID, degree_condition
from fatebridge.core.jyotish_vargas import (
    RASI_LORDS,
    SAPTA_DIVISIONS,
    longitude_ratio,
    varga_sign,
)

RAMAN_SOURCE = {
    "id": "raman_graha_bhava_balas_section30_preview",
    "title": "B.V. Raman, Graha and Bhava Balas (fixed scan; selected sections)",
    "url": "https://astrojyotish.info/pdf/graha-bhava-balas.pdf",
    "sha256": "727c8063f64816a0c1c7f6bc577c249629854e980bf860bf4cfd8de16ec9bab2",
    "legacy_id_note": "Stable source identifier predates the fixed scan; the preview suffix is not the current verification status.",
    "sections": [
        "30: printed pp.22-24",
        "31-40: printed pp.25-29; PDF30-34; Drekkana page images PDF32-33",
        "Summary: printed105/PDF110; conflicting Drekkana coefficient retained",
        "53: printed p.38",
        "76: printed pp.60-61",
        "113-120: printed pp.82-89",
    ],
    "textual_status": "Fixed primary scan; selected page images checked. Foreword to thirteenth edition dated1992; exact reprint unverified. Detailed Drekkana15 and summary60 conflict, so whole-book acceptance is unresolved.",
}
PROFILES: dict[str, dict[str, Any]] = {
    "santhanam_27": {
        "id": "santhanam_27",
        "source_id": SOURCE_ID,
        "source_section": "27.2-4, printed p.265",
        "weights": {
            "moolatrikona": 45.0,
            "own_sign": 30.0,
            "great_friend": 20.0,
            "friend": 15.0,
            "neutral": 10.0,
            "enemy": 4.0,
            "great_enemy": 2.0,
        },
        "moolatrikona_scope": "sign_assignment_in_all_seven_vargas",
        "reading_choice": "literal application of the stated same values in the other six vargas; degree-zone dignity is a separate calculation; not a claim of uniquely adjudicated author intent",
    },
    "raman_30": {
        "id": "raman_30",
        "source_id": RAMAN_SOURCE["id"],
        "source_section": "30, printed pp.22-24",
        "weights": {
            "moolatrikona": 45.0,
            "own_sign": 30.0,
            "great_friend": 22.5,
            "friend": 15.0,
            "neutral": 7.5,
            "enemy": 3.75,
            "great_enemy": 1.875,
        },
        "moolatrikona_scope": "D1_sign_assignment_only",
        "reading_choice": "explicit D1-only exception in section30, fixed scan printed22-23/PDF27-28; sign assignment used, not the separate Santhanam degree-zone state; exact reprint unverified",
    },
}
COMPONENTS = (
    "uchcha_bala",
    "saptavargaja_bala",
    "ojayugma_bala",
    "kendradi_bala",
    "drekkana_bala",
)
DREKKANA_PROFILES: dict[str, dict[str, Any]] = {
    "santhanam_27_6": {
        "id": "santhanam_27_6",
        "source_id": SOURCE_ID,
        "source_section": "27.6, printed266/PDF265",
        "groups": [
            ["Sun", "Mars", "Jupiter"],
            ["Moon", "Venus"],
            ["Mercury", "Saturn"],
        ],
        "value_virupa": 15.0,
    },
    "raman_36": {
        "id": "raman_36",
        "source_id": RAMAN_SOURCE["id"],
        "source_section": "36-39 and Example12, printed27-28/PDF32-33",
        "groups": [
            ["Sun", "Mars", "Jupiter"],
            ["Mercury", "Saturn"],
            ["Moon", "Venus"],
        ],
        "value_virupa": 15.0,
        "reading_choice": "Detailed section36 and workedExample12 coefficient15 selected explicitly; conflicting summary105 coefficient60 is not silently substituted or erased.",
    },
}


def drekkana(longitude: float, planet: str, profile_id: str) -> dict[str, Any]:
    if profile_id not in DREKKANA_PROFILES:
        raise ValueError("drekkana_profile 必须为 santhanam_27_6 或 raman_36。")
    profile = DREKKANA_PROFILES[profile_id]
    if planet not in PEAKS:
        raise ValueError(
            "Drekkana strength is registered for the seven physical grahas only"
        )
    n, d = longitude_ratio(longitude)
    decanate = n % (30 * d) // (10 * d)
    preferred = next(i for i, group in enumerate(profile["groups"]) if planet in group)
    return {
        "value": profile["value_virupa"] if decanate == preferred else 0.0,
        "D1_decanate": decanate + 1,
        "preferred_decanate": preferred + 1,
        "profile_id": profile_id,
        "source_id": profile["source_id"],
        "source_section": profile["source_section"],
        "rule_id": "jyotish.drekkana_profiles.v1",
        "coordinate_scope": "physical D1 degree, not transformed D3 longitude; half-open [0,10),[10,20),[20,30) per sign",
        "scope": "classical graha categories only; no human sex or gender assessment",
    }


def saptavargaja(
    longitudes: dict[str, float], planet: str, profile_id: str
) -> dict[str, Any]:
    if profile_id not in PROFILES:
        raise ValueError("saptavargaja_profile 必须为 santhanam_27 或 raman_30。")
    profile = PROFILES[profile_id]
    signs = {p: varga_sign(longitudes[p], 1) for p in PEAKS}
    rows = []
    for division in SAPTA_DIVISIONS:
        sign = varga_sign(longitudes[planet], division)
        lord = RASI_LORDS[sign]
        relation = relationship(planet, lord, signs)
        moola_applies = division == 1 or profile_id == "santhanam_27"
        if sign == MOOLA[planet][0] and moola_applies:
            condition = "moolatrikona"
        elif lord == planet:
            condition = "own_sign"
        else:
            condition = relation["compound"]
        rows.append(
            {
                "division": division,
                "sign": SIGNS[sign],
                "lord": lord,
                "condition": condition,
                "value": profile["weights"][condition],
                "relationship": relation,
                "relationship_basis": "D1 natal sign placements for every varga, including Hora",
            }
        )
    return {"value": sum(row["value"] for row in rows), "rows": rows}


def calculate_sthana(
    raw: dict[str, Any],
    profile_id: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
) -> dict[str, Any]:
    if profile_id not in PROFILES:
        raise ValueError("saptavargaja_profile 必须为 santhanam_27 或 raman_30。")
    if drekkana_profile not in DREKKANA_PROFILES:
        raise ValueError("drekkana_profile 必须为 santhanam_27_6 或 raman_36。")
    longitudes = raw["longitudes"]
    ascendant = varga_sign(raw["ascendant"], 1)
    summary: dict[str, dict[str, float]] = {}
    evidence: dict[str, Any] = {}
    comparisons: dict[str, dict[str, dict[str, float]]] = {key: {} for key in PROFILES}
    drekkana_comparisons: dict[str, dict[str, dict[str, float]]] = {
        key: {} for key in DREKKANA_PROFILES
    }
    for planet in PEAKS:
        sign = varga_sign(longitudes[planet], 1)
        navamsa = varga_sign(longitudes[planet], 9)
        house = (sign - ascendant) % 12 + 1
        preferred_parity = 1 if planet in {"Moon", "Venus"} else 0
        oja_rasi = 15.0 if sign % 2 == preferred_parity else 0.0
        oja_navamsa = 15.0 if navamsa % 2 == preferred_parity else 0.0
        decanate = drekkana(longitudes[planet], planet, drekkana_profile)
        known = {
            "uchcha_bala": degree_condition(planet, longitudes[planet])["uchcha_bala"][
                "value"
            ],
            "ojayugma_bala": oja_rasi + oja_navamsa,
            "kendradi_bala": {0: 60.0, 1: 30.0, 2: 15.0}[(house - 1) % 3],
            "drekkana_bala": decanate["value"],
        }
        sapta = saptavargaja(longitudes, planet, profile_id)
        values = {**known, "saptavargaja_bala": sapta["value"]}
        total = sum(values.values())
        summary[planet] = {**values, "total_virupa": total, "total_rupa": total / 60.0}
        evidence[planet] = {
            "saptavargaja": sapta,
            "ojayugma": {
                "D1_sign": SIGNS[sign],
                "D9_sign": SIGNS[navamsa],
                "D1_value": oja_rasi,
                "D9_value": oja_navamsa,
            },
            "kendradi": {
                "D1_whole_sign_house": house,
                "scope": "Rasi groups in Santhanam p.266; not a different Bhava/house-cusp model",
            },
            "drekkana": decanate,
        }
        for key in PROFILES:
            value = (
                sapta["value"]
                if key == profile_id
                else saptavargaja(longitudes, planet, key)["value"]
            )
            comparisons[key][planet] = {
                "saptavargaja_bala": value,
                "total_virupa": sum(known.values()) + value,
            }
        for key in DREKKANA_PROFILES:
            value = drekkana(longitudes[planet], planet, key)["value"]
            drekkana_comparisons[key][planet] = {
                "drekkana_bala": value,
                "total_virupa": sum(
                    {
                        **known,
                        "drekkana_bala": value,
                        "saptavargaja_bala": sapta["value"],
                    }.values()
                ),
            }
    return {
        "status": "computed_under_declared_reading",
        "profile": {
            **PROFILES[profile_id],
            "drekkana_profile": DREKKANA_PROFILES[drekkana_profile],
            "other_components_source_id": SOURCE_ID,
            "other_components_source_section": "27.1, 27.4-5, printed pp.263-267; independently selected Drekkana source below",
            "source_adjudication": "registered readings, not whole-text or universal classical acceptance",
            "scope": (
                "profile changes Saptavargaja only; other four components keep Santhanam rules"
                if drekkana_profile == "santhanam_27_6"
                else "Saptavargaja and Drekkana selected independently; the remaining three components retain Santhanam formulas, also registered in Raman20,31-35"
            ),
            "known_author_difference": "Santhanam27.6: Moon/Venus second, Mercury/Saturn third. Raman36 reverses those groups; drekkana_profile selects it independently of saptavargaja_profile.",
            "author_alignment_scope": "Matching five component arithmetic under registered readings is not whole-book or complete Shadbala acceptance. Shared D1 relationship and varga inputs retain their separately published source attribution.",
        },
        "unit": "virupa; 60 virupa = 1 rupa",
        "components": list(COMPONENTS),
        "summary": summary,
        "evidence": evidence,
        "profile_comparison": comparisons,
        "drekkana_profile_comparison": drekkana_comparisons,
        "comparison_scope": "profile_comparison varies Saptavargaja with selected Drekkana held fixed; drekkana_profile_comparison varies Drekkana with selected Saptavargaja held fixed. Source-profile differences, not uncertainty intervals or success probabilities.",
        "source_reading_conflicts": [
            {
                "source_id": RAMAN_SOURCE["id"],
                "detailed_section": "36 and Example12, printed27-28/PDF32-33",
                "detailed_value_virupa": 15.0,
                "summary_section": "Summary I(v), printed105/PDF110",
                "summary_value_virupa": 60.0,
                "selected_reading": "detailed15 when raman_36 is selected; summary60 remains an unresolved book-internal conflict",
                "applies_to_selected_profile": drekkana_profile == "raman_36",
                "whole_book_acceptance": False,
            }
        ],
        "excluded_points": ["Rahu", "Ketu", "Ascendant"],
        "remaining_shadbala": [
            "dig_bala",
            "kala_bala",
            "cheshta_bala",
            "naisargika_bala",
            "drik_bala",
        ],
        "shadbala_status": "not_complete",
        "rule_ids": [
            "jyotish.sthana_bala.v1",
            "jyotish.saptavargaja_profiles.v1",
            "jyotish.drekkana_profiles.v1",
            *(["jyotish.saptavargaja_raman.v1"] if profile_id == "raman_30" else []),
        ],
        "interpretation_scope": "positional-strength components only; no planetary beneficence, ability certificate, normalized perfect score or outcome probability",
    }
