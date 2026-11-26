"""Assemble topic evidence from same-run houses and conditional strengths."""

from __future__ import annotations

from typing import Any

from fatebridge.core.jyotish.jyotish_ashtakavarga import (
    topic_factor as ashtakavarga_topic_factor,
)
from fatebridge.core.jyotish.jyotish_balas import verify_drik_evidence
from fatebridge.core.jyotish.jyotish_evidence import (
    cheshta_ruler_provenance,
    strength_context,
)
from fatebridge.core.jyotish.jyotish_longitude_motion import (
    RULE as LONGITUDE_MOTION_RULE,
)
from fatebridge.core.jyotish.jyotish_relationships import (
    SOURCE_ID as RELATIONSHIP_SOURCE_ID,
)
from fatebridge.core.jyotish.jyotish_strength import SOURCE_ID as STRENGTH_SOURCE_ID
from fatebridge.core.jyotish.jyotish_war import SOURCE as WAR_SOURCE


def topic_evidence(
    charts: dict[str, Any],
    sthana: dict[str, Any] | None = None,
    additional_balas: dict[str, Any] | None = None,
    ashtakavarga: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if "D1" in charts and additional_balas is not None:
        verify_drik_evidence(additional_balas["drik_bala"], charts["D1"])
    topics = {}
    for topic, scopes in [
        ("personality", [("D1", 1)]),
        ("career", [("D1", 10), ("D10", 10)]),
        ("relationship", [("D1", 7), ("D9", 7)]),
    ]:
        facts = []
        factors: list[dict[str, Any]] = []
        for name, house in scopes:
            if name in charts:
                fact = charts[name]["houses"][house - 1]
                facts.append({"chart": name, **fact})
                factors.append(
                    {
                        "chart": name,
                        "rule_id": "jyotish.house_lords.v1",
                        "fact": {
                            "house": house,
                            "lord": fact["lord"],
                            "lord_house": fact["lord_house"],
                        },
                        "source_id": "pvr_2000",
                        "source_section": "4 Houses; 6 Divisional Charts",
                    }
                )
                factors.append(
                    {
                        "chart": name,
                        "rule_id": "jyotish.sign_dignity.v1",
                        "fact": {"planet": fact["lord"], **fact["lord_dignity"]},
                        "source_id": "pvr_2000",
                        "source_section": "3 Planets: dignities",
                    }
                )
                placed = next(
                    p for p in charts[name]["planets"] if p["id"] == fact["lord"]
                )
                if ashtakavarga is not None:
                    factors.append(
                        ashtakavarga_topic_factor(
                            name, charts[name], house, ashtakavarga
                        )
                    )
                state = placed.get("physical_state")
                if name == "D1" and sthana is not None:
                    values = sthana["summary"][fact["lord"]]
                    factors.append(
                        {
                            "chart": name,
                            "rule_id": "jyotish.sthana_bala.v1",
                            "fact_path": f"india.strengths.sthana_bala.summary.{fact['lord']}",
                            "fact": values,
                            "source_id": STRENGTH_SOURCE_ID,
                            "source_section": "27.1,27.4-5; Saptavargaja and Drekkana use their separately declared profiles",
                            "component_profile_paths": [
                                "india.strengths.sthana_bala.profile.id",
                                "india.strengths.sthana_bala.profile.drekkana_profile",
                            ],
                        }
                    )
                if name == "D1" and additional_balas is not None:
                    for key, rule_id in [
                        ("dig_bala", "jyotish.dig_bala.v1"),
                        ("naisargika_bala", "jyotish.naisargika_bala.v1"),
                        ("drik_bala", "jyotish.drik_bala_conditional.v2"),
                        ("kala_bala", "jyotish.kala_components.v1"),
                        ("cheshta_bala", "jyotish.luminary_cheshta.v1"),
                    ]:
                        component = additional_balas[key]
                        provenance = (
                            cheshta_ruler_provenance(
                                fact["lord"], component, additional_balas["kala_bala"]
                            )
                            if key == "cheshta_bala"
                            else None
                        )
                        if provenance is not None:
                            rule_id = provenance["rule_id"]
                        value = component["summary"][fact["lord"]]
                        context = strength_context(key, fact["lord"], component)
                        if provenance is not None:
                            context["method_context"] = provenance["method_context"]
                        factors.append(
                            {
                                "chart": name,
                                "rule_id": rule_id,
                                "fact_path": f"india.strengths.{key}.summary.{fact['lord']}",
                                "fact": value,
                                "calculation_context": context,
                                "source_id": component["source_id"],
                                "source_section": (
                                    provenance["source_section"]
                                    if provenance is not None
                                    else component["source_section"]
                                ),
                                **(
                                    {
                                        "supporting_source_id": provenance[
                                            "supporting_source_id"
                                        ]
                                    }
                                    if provenance is not None
                                    and "supporting_source_id" in provenance
                                    else (
                                        {"supporting_source_id": WAR_SOURCE["id"]}
                                        if key == "kala_bala"
                                        else {}
                                    )
                                ),
                            }
                        )
                if "dispositor_relationship" in placed:
                    factors.append(
                        {
                            "chart": name,
                            "rule_id": "jyotish.satyacharya_relationships.v1",
                            "fact_path": f"india.charts.{name}.planets.{charts[name]['planets'].index(placed)}.dispositor_relationship",
                            "fact": placed["dispositor_relationship"],
                            "source_id": RELATIONSHIP_SOURCE_ID,
                            "source_section": "II.16-18, pp.21-22",
                        }
                    )
                if state is not None:
                    point_path = f"india.charts.{name}.planets.{charts[name]['planets'].index(placed)}.physical_state"
                    condition = state["degree_condition"]
                    factors.append(
                        {
                            "chart": name,
                            "rule_id": "jyotish.bphs_degree_zones.v1",
                            "fact_path": point_path + ".degree_condition",
                            "fact": condition,
                            "source_id": STRENGTH_SOURCE_ID,
                            "source_section": "3.49-54; 27.1; 45.3-4",
                        }
                    )
                    factors.append(
                        {
                            "chart": name,
                            "rule_id": LONGITUDE_MOTION_RULE,
                            "fact_path": point_path + ".motion",
                            "fact": state["motion"],
                            "source_id": "swiss_ephemeris",
                            "source_section": "D1 reported rate; calculation basis in physical_state.longitude_motion_context",
                        }
                    )
                    if "combustion" in state:
                        factors.append(
                            {
                                "chart": name,
                                "rule_id": "jyotish.santhanam_solar_orb.v1",
                                "fact_path": point_path + ".combustion",
                                "fact": state["combustion"],
                                "source_id": STRENGTH_SOURCE_ID,
                                "source_section": "7.28-29 translator commentary, printed p.100 / PDF p.99",
                            }
                        )
                influences = [
                    a
                    for a in charts[name]["graha_aspects"]
                    if a["target_house"] == house
                ]
                factors.append(
                    {
                        "chart": name,
                        "rule_id": "jyotish.graha_drishti.v1",
                        "fact": influences,
                        "source_id": "pvr_2000",
                        "source_section": "10.2 Graha Drishti",
                    }
                )
        topics[topic] = {
            "engine_facts": facts,
            "factors": factors,
            "source_id": "pvr_2000",
            "source_section": "6 Divisional Charts; houses and planets",
            "rule_ids": sorted(
                {"jyotish.varga.v1", *(factor["rule_id"] for factor in factors)}
            ),
            "application_scope": "single-person structure; no event dates, partner intent, outcome probability or ability certification",
        }
    return topics
