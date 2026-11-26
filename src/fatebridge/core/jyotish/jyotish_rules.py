"""Bibliographic records and rule references for the supported Parashari subset."""

from __future__ import annotations

from typing import Any, Dict, List

from fatebridge.core.jyotish.jyotish_aiyar_ashtakavarga import RULE as AIYAR_BAV_RULE
from fatebridge.core.jyotish.jyotish_aiyar_ashtakavarga import (
    SOURCE as AIYAR_BAV_SOURCE,
)
from fatebridge.core.jyotish.jyotish_aiyar_reductions import (
    RULE as AIYAR_REDUCTION_RULE,
)
from fatebridge.core.jyotish.jyotish_aiyar_reductions import (
    SOURCE as AIYAR_REDUCTION_SOURCE,
)
from fatebridge.core.jyotish.jyotish_ashtakavarga import RULE as ASHTAKAVARGA_RULE
from fatebridge.core.jyotish.jyotish_ashtakavarga import SOURCE as ASHTAKAVARGA_SOURCE
from fatebridge.core.jyotish.jyotish_dasha_levels import RULE as RECURSIVE_DASHA_RULE
from fatebridge.core.jyotish.jyotish_dasha_levels import (
    SOURCE as RECURSIVE_DASHA_SOURCE,
)
from fatebridge.core.jyotish.jyotish_longitude_motion import (
    RULE as LONGITUDE_MOTION_RULE,
)
from fatebridge.core.jyotish.jyotish_pinda import RULE as PINDA_RULE
from fatebridge.core.jyotish.jyotish_pinda import SOURCE as PINDA_SOURCE
from fatebridge.core.jyotish.jyotish_relationships import SOURCE as RELATIONSHIP_SOURCE
from fatebridge.core.jyotish.jyotish_relationships import (
    SOURCE_ID as RELATIONSHIP_SOURCE_ID,
)
from fatebridge.core.jyotish.jyotish_sthana import RAMAN_SOURCE
from fatebridge.core.jyotish.jyotish_strength import SOURCE as STRENGTH_SOURCE
from fatebridge.core.jyotish.jyotish_strength import SOURCE_ID as STRENGTH_SOURCE_ID
from fatebridge.core.jyotish.jyotish_war import SOURCE as WAR_SOURCE

SOURCES = [
    ASHTAKAVARGA_SOURCE,
    PINDA_SOURCE,
    AIYAR_REDUCTION_SOURCE,
    AIYAR_BAV_SOURCE,
    RECURSIVE_DASHA_SOURCE,
    STRENGTH_SOURCE,
    RELATIONSHIP_SOURCE,
    RAMAN_SOURCE,
    WAR_SOURCE,
    {
        "id": "iers_leap_seconds",
        "title": "IERS Bulletin C leap-second table (version frozen in the package)",
        "url": "https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat",
        "scope": "TAI minus UTC from 1972; last offset held fixed beyond table expiry as an explicit assumption",
    },
    {
        "id": "pvr_2000",
        "title": "P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach (2000)",
        "url": "https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf",
        "sections": [
            "2 Rasis",
            "3 Planets",
            "4 Houses",
            "6 Divisional Charts",
            "10 Aspects and Argalas",
            "16 Vimsottari Dasa",
        ],
    },
    {
        "id": "swiss_ephemeris",
        "title": "Swiss Ephemeris Programmer's Manual: sidereal positions, UTC and solar clocks",
        "url": "https://www.astro.com/swisseph/swephprg.htm",
    },
]


def rule_trace() -> List[Dict[str, Any]]:
    return [
        {"rule_id": rule, "source_id": source, "section": section}
        for rule, source, section in [
            (
                "jyotish.lahiri.v1",
                "swiss_ephemeris",
                "swe_set_sid_mode / SE_SIDM_LAHIRI / SEFLG_SIDEREAL",
            ),
            (
                "jyotish.recorded_instant.v1",
                "swiss_ephemeris",
                "9.3 UTC conversions; 9.4 local solar clocks; FateBridge preserves the recorded instant",
            ),
            (
                "jyotish.birth_clock_source_coherence.v1",
                "swiss_ephemeris",
                "9.4 solar clocks, 10.1 Delta-T; FateBridge checks clock/native Sun contexts and a same-label replay under one managed configuration; not a classical prediction rule or atomic read proof",
            ),
            (
                "jyotish.time_scales.v2",
                "iers_leap_seconds",
                "TAI-UTC table; TT=TAI+32.184 seconds; model UT1 from Swiss Delta-T",
            ),
            ("jyotish.nakshatra.v1", "pvr_2000", "2 Rasis; 16 Vimsottari Dasa"),
            ("jyotish.varga.v1", "pvr_2000", "6.2.9 Navamsa; 6.2.10 Dasamsa"),
            (
                "jyotish.extended_varga.v1",
                STRENGTH_SOURCE_ID,
                "6.5-8, 6.10-15, 6.27-28; D30 sign table only",
            ),
            (
                "jyotish.sthana_bala.v1",
                STRENGTH_SOURCE_ID,
                "27.1-6, printed pp.263-267",
            ),
            (
                "jyotish.dig_bala.v1",
                STRENGTH_SOURCE_ID,
                "27.7, printed p.267; physical cardinal angles",
            ),
            (
                "jyotish.naisargika_bala.v1",
                STRENGTH_SOURCE_ID,
                "27.14, printed p.276; exact multiples of60/7",
            ),
            (
                "jyotish.quantitative_drishti.v1",
                RAMAN_SOURCE["id"],
                "113-115, printed pp.82-86; directed base plus additive special, no cap",
            ),
            (
                "jyotish.drik_bala_conditional.v2",
                RAMAN_SOURCE["id"],
                "53 and116-120; lunar nature author readings and Mercury association retained as branches",
            ),
            (
                "jyotish.moon_nature_readings.v1",
                RAMAN_SOURCE["id"],
                "53 versus117-118; eighth-tithi boundaries unadjudicated",
            ),
            (
                "jyotish.kala_components.v1",
                STRENGTH_SOURCE_ID,
                "27.8-17; printed268-283; commentary and implementation choices declared",
            ),
            (
                "jyotish.solar_component_dependencies.v1",
                STRENGTH_SOURCE_ID,
                "27.12 day/night thirds and27.13 sunrise-to-sunrise; independent availability checks are a FateBridge implementation choice",
            ),
            (
                "jyotish.solar_event_enumeration.v2",
                STRENGTH_SOURCE_ID,
                "27.12-13 need chronological solar events; successive next-event searches within each UT1 date are a FateBridge implementation, not a new classical rule",
            ),
            (
                "jyotish.yuddha_raman_76_77.v1",
                WAR_SOURCE["id"],
                "76-77 printed60-61/PDF65-66; fixed Bimba divisor and through-Hora inputs; upstream source profiles retained",
            ),
            (
                "jyotish.luminary_cheshta.v1",
                STRENGTH_SOURCE_ID,
                "27.18; printed284; five-star mean model separately declared",
            ),
            (
                "jyotish.cheshta_arc.v1",
                STRENGTH_SOURCE_ID,
                "27.24-25; printed285; angular stage needs a separately admitted mean model",
            ),
            (
                "jyotish.cheshta_ruler_provenance.v1",
                STRENGTH_SOURCE_ID,
                "27.18 versus27.24-25; FateBridge maps each ruler to actual same-run upstream inputs, not a global selected model",
            ),
            (
                "jyotish.saptavargaja_profiles.v1",
                STRENGTH_SOURCE_ID,
                "27.2-4 literal seven-sign reading; alternative Raman section30 independently labeled",
            ),
            (
                "jyotish.saptavargaja_raman.v1",
                RAMAN_SOURCE["id"],
                "30, printed22-24/PDF27-29; fixed scan, selected page images verified",
            ),
            (
                "jyotish.drekkana_profiles.v1",
                STRENGTH_SOURCE_ID,
                "27.6, printed266/PDF265; Santhanam grouping",
            ),
            (
                "jyotish.drekkana_profiles.v1",
                RAMAN_SOURCE["id"],
                "36-39 and Example12 printed27-28/PDF32-33; selected15 versus conflicting summary105/PDF110 value60",
            ),
            ("jyotish.house_lords.v1", "pvr_2000", "3 Planets: ownership of rasis"),
            (
                "jyotish.sign_dignity.v1",
                "pvr_2000",
                "3 Planets: exaltation and debilitation",
            ),
            ("jyotish.graha_drishti.v1", "pvr_2000", "10.2 Graha Drishti"),
            (
                ASHTAKAVARGA_RULE,
                ASHTAKAVARGA_SOURCE["id"],
                "12.2-12.6; Tables19-27; unreduced counts on separately declared varga signs",
            ),
            (
                PINDA_RULE,
                PINDA_SOURCE["id"],
                "3.1 and12.7.1-12.7.3; selected seven-graha occupancy; unspecified equal single-occupied cells remain null",
            ),
            (
                AIYAR_REDUCTION_RULE,
                AIYAR_REDUCTION_SOURCE["id"],
                "Chapter IX English N.B. commentary, printed101-104/PDF145-148; separate reduction comparison on the same raw BAV, not a Rao patch or Pinda weighting",
            ),
            (
                AIYAR_BAV_RULE,
                AIYAR_BAV_SOURCE["id"],
                "IX.1-7, printed97-99/PDF141-143; separate seven planetary BAV tables and their own English-note reductions. Six literal cells differ from Rao; no Ascendant target inferred.",
            ),
            (
                "jyotish.vimshottari.v1",
                "pvr_2000",
                "16 Vimsottari Dasa: Moon seed, balance, antardasa",
            ),
            (
                RECURSIVE_DASHA_RULE,
                RECURSIVE_DASHA_SOURCE["id"],
                "16.1-16.3 Table38; complete parent periods recursively weighted through Deha; microsecond quantization is declared separately",
            ),
            ("jyotish.bphs_degree_zones.v1", STRENGTH_SOURCE_ID, "3.49-54"),
            ("jyotish.bphs_uchcha_bala.v1", STRENGTH_SOURCE_ID, "27.1"),
            ("jyotish.bphs_baladi.v1", STRENGTH_SOURCE_ID, "45.3-4"),
            (
                "jyotish.santhanam_solar_orb.v1",
                STRENGTH_SOURCE_ID,
                "7.28-29 translator commentary, printed p.100 / PDF p.99",
            ),
            (
                LONGITUDE_MOTION_RULE,
                "swiss_ephemeris",
                "Native swe_calc speed plus qualified FateBridge apparent-position/chain derivatives; per-body D1 longitude_motion_context records coverage, TT epoch and retained raw speed",
            ),
            (
                "jyotish.satyacharya_relationships.v1",
                RELATIONSHIP_SOURCE_ID,
                "II.16-18, pp.21-22",
            ),
            (
                "jyotish.physical_source_cohort.v1",
                "swiss_ephemeris",
                "2.6 current physical file contexts;3.3.2 returned backends; FateBridge per-body/frame grid coherence and endpoint file hashes, not an atomic read-set proof",
            ),
        ]
    ]
