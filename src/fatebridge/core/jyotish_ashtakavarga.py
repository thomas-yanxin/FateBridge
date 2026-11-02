"""Rao2000 unreduced sign-count tables; no event or probability model."""

from __future__ import annotations

import math
from typing import Any, Mapping

from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.jyotish_aiyar_ashtakavarga import SOURCE as AIYAR_SOURCE
from fatebridge.core.jyotish_aiyar_ashtakavarga import calculate as aiyar_calculate
from fatebridge.core.jyotish_pinda import PLANETS as PINDA_PLANETS
from fatebridge.core.jyotish_pinda import RULE as PINDA_RULE
from fatebridge.core.jyotish_pinda import analyze as pinda_analysis
from fatebridge.core.jyotish_vargas import varga_sign

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
RULE = "jyotish.ashtakavarga_rao2000.v1"
METHOD = "rao2000_unreduced_ashtakavarga_v1"
SOURCE = {
    "id": "pvr_2000_ashtakavarga_1cafa828",
    "title": "P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach (2000; 2010 update)",
    "url": "https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf",
    "sha256": "1cafa828f34764ed5e85816882df2e8f0bc014c5c57ccdb27169416e117fd4db",
    "sections": ["12.2-12.6; Tables19-27; printed146-156/PDF158-168"],
    "scope": "Unreduced PAV/BAV/SAV; the author's divisional application reading. Actual varga construction has its own declared source. Separate reduction_analysis has its own declared source and occupancy reading; no empirical forecast acceptance.",
}
# Each row is one relative house1..12; columns follow REFERENCES. Literal
# numeric facts from Tables19..26, checked against frozen pre-implementation
# primary pages and an isolated implementation.1=rekha under THIS author.
HOUSE_ROWS = (
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


def calculate(signs: Mapping[str, int]) -> dict[str, Any]:
    """Shift each contributor's relative-house1 into its occupied sign."""
    if set(signs) != set(REFERENCES) or any(
        type(value) is not int or not 0 <= value < 12 for value in signs.values()
    ):
        raise ValueError(
            "Ashtakavarga requires exactly seven planets and Ascendant, with integer signs0..11"
        )
    pav: dict[str, dict[str, list[int]]] = {}
    bav: dict[str, list[int]] = {}
    for target, table in zip(REFERENCES, HOUSE_ROWS):
        contributions = {}
        for column, donor in enumerate(REFERENCES):
            values = [0] * 12
            for offset, row in enumerate(table):
                values[(signs[donor] + offset) % 12] = int(row[column])
            contributions[donor] = values
        pav[target] = contributions
        bav[target] = [
            sum(row[sign] for row in contributions.values()) for sign in range(12)
        ]
    sav = [sum(bav[target][sign] for target in REFERENCES[:7]) for sign in range(12)]
    return {
        "input_sign_indices": dict(signs),
        "prastara": pav,
        "bhinna": bav,
        "samudaya": sav,
        "bhinna_totals": {target: sum(values) for target, values in bav.items()},
        "samudaya_total": sum(sav),
    }


def chart_inputs(chart: dict[str, Any]) -> dict[str, int]:
    points = {"Ascendant": chart["ascendant"]}
    for point in chart["planets"]:
        if point["id"] in REFERENCES:
            if point["id"] in points:
                raise ValueError("Duplicate Ashtakavarga contributor")
            points[point["id"]] = point
    return {name: SIGNS.index(points[name]["sign"]) for name in REFERENCES}


def chart_claims(name: str, chart: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "fact_path": f"india.charts.{name}.ascendant.sign",
            "value": chart["ascendant"]["sign"],
        },
        *[
            {
                "fact_path": f"india.charts.{name}.planets.{i}.sign",
                "value": point["sign"],
            }
            for i, point in enumerate(chart["planets"])
            if point["id"] in REFERENCES
        ],
    ]


def source_profiles(
    default: dict[str, Any],
    *,
    name: str | None = None,
    chart: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep an author's own table and reductions on these exact contributor signs."""
    other = aiyar_calculate(default["input_sign_indices"])
    other["comparison_to_default"] = {
        "default_source_id": SOURCE["id"],
        "same_input_sign_indices": True,
        "bhinna_different_sign_indices": {
            p: [
                i for i in range(12) if default["bhinna"][p][i] != other["bhinna"][p][i]
            ]
            for p in PINDA_PLANETS
        },
        "samudaya_different_sign_indices": [
            i for i in range(12) if default["samudaya"][i] != other["samudaya"][i]
        ],
        "scope": "Actual local count differences between registered sources on the same supplied signs. Equal totals do not prove identical table cells; differences are not event failures or probabilities.",
    }
    if name is not None and chart is not None:
        other.update(
            chart_method=chart["method"],
            chart_rule_ids=chart["rule_ids"],
            input_claims=chart_claims(name, chart),
        )
    return {"aiyar1905": other}


def for_charts(charts: dict[str, Any]) -> dict[str, Any]:
    results = {}
    for name, chart in charts.items():
        result = calculate(chart_inputs(chart))
        analysis = pinda_analysis(
            result["bhinna"],
            {p: result["input_sign_indices"][p] for p in PINDA_PLANETS},
        )
        results[name] = {
            **result,
            "chart_method": chart["method"],
            "chart_rule_ids": chart["rule_ids"],
            "input_claims": chart_claims(name, chart),
            "source_profile_comparison": source_profiles(
                result, name=name, chart=chart
            ),
            "reduction_analysis": {
                **analysis,
                "basis_bhinna_rule_id": RULE,
                "bhinna_fact_path": f"india.ashtakavarga.charts.{name}.bhinna",
            },
        }
    return {
        "status": "computed_unreduced",
        "method_id": METHOD,
        "source_id": SOURCE["id"],
        "source_section": "12.2-12.6; Tables19-27",
        "rule_ids": [RULE, PINDA_RULE],
        "reference_instant": "nominal_birth_instant",
        "sign_order": list(SIGNS),
        "contributor_order": list(REFERENCES),
        "target_order": list(REFERENCES),
        "samudaya_targets": list(REFERENCES[:7]),
        "notation": {
            "one": "rekha: benefic reference count under selected author",
            "zero": "bindu: no benefic count under selected author; alternate authors may reverse these words",
        },
        "reductions_applied": False,
        "charts": results,
        "not_computed": [
            "unique_occupation_reading_across_authors",
            "single_occupied_equal_nonzero_reduction_rule",
            "transit_event_prediction",
        ],
        "interpretation_scope": "Counts from8references, SAV sums7planetary target BAVs and excludes the Ascendant target. reductions_applied=false preserves these original arrays; separate reduction_analysis declares seven-graha occupancy and source missingness. Not percentages, complete Shadbala, physical strengths or event probabilities. Rao12.5 application to returned vargas retains their own method/source; not whole-book acceptance.",
    }


class SampleGrid:
    """Group only identical contributor signs, retaining each sample's own table."""

    def __init__(self, chart_names: list[str]):
        self.groups: dict[str, dict[tuple[int, ...], dict[str, Any]]] = {
            name: {} for name in chart_names
        }
        self.offsets: set[float] = set()

    def observe(self, offset: float, raw: dict[str, Any]) -> None:
        if not math.isfinite(offset) or offset in self.offsets:
            raise ValueError("Ashtakavarga grid offsets must be finite and unique")
        self.offsets.add(offset)
        for name, groups in self.groups.items():
            division = int(name[1:])
            signs = {
                p: varga_sign(
                    raw["ascendant"] if p == "Ascendant" else raw["longitudes"][p],
                    division,
                )
                for p in REFERENCES
            }
            key = tuple(signs[p] for p in REFERENCES)
            if key not in groups:
                table = calculate(signs)
                groups[key] = {
                    **table,
                    "source_profile_comparison": source_profiles(table),
                    "reduction_analysis": {
                        **pinda_analysis(
                            table["bhinna"], {p: signs[p] for p in PINDA_PLANETS}
                        ),
                        "basis_bhinna_rule_id": RULE,
                    },
                    "sample_offsets_seconds": [],
                }
            groups[key]["sample_offsets_seconds"].append(offset)

    def result(self) -> dict[str, Any]:
        return {
            "method_id": METHOD,
            "sample_count": len(self.offsets),
            "charts": {
                name: [
                    {
                        **group,
                        "sample_count": len(group["sample_offsets_seconds"]),
                        "contains_nominal": 0.0 in group["sample_offsets_seconds"],
                    }
                    for _, group in sorted(groups.items())
                ]
                for name, groups in self.groups.items()
            },
            "scope": "Own sampled varga signs, full unreduced tables and separate declared-occupancy reduction analysis, not nominal-chart source claims. Same UTC grid; counts are coverage, never probabilities or proof of continuity between samples.",
        }


def topic_factor(
    name: str, chart: dict[str, Any], house: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Bind count prose to the actual ruler/sign and its eight contributions."""
    packet = data["charts"][name]
    expected = calculate(chart_inputs(chart))
    if (
        any(packet[key] != value for key, value in expected.items())
        or packet.get("input_claims") != chart_claims(name, chart)
        or packet.get("chart_method") != chart["method"]
        or packet.get("chart_rule_ids") != chart["rule_ids"]
        or data.get("source_id") != SOURCE["id"]
        or data.get("method_id") != METHOD
        or data.get("reductions_applied") is not False
        or data.get("reference_instant") != "nominal_birth_instant"
        or packet.get("source_profile_comparison")
        != source_profiles(expected, name=name, chart=chart)
    ):
        raise ValueError("Ashtakavarga topic evidence contradicts chart contributors")
    ruler = chart["houses"][house - 1]["lord"]
    sign = packet["input_sign_indices"][ruler]
    house_sign = SIGNS.index(chart["houses"][house - 1]["sign"])
    prefix = f"india.ashtakavarga.charts.{name}"
    count = packet["bhinna"][ruler][sign]
    sav = packet["samudaya"][house_sign]
    paths = [
        {"fact_path": f"{prefix}.bhinna.{ruler}.{sign}", "value": count},
        {"fact_path": f"{prefix}.samudaya.{house_sign}", "value": sav},
        *[
            {
                "fact_path": f"{prefix}.prastara.{ruler}.{donor}.{sign}",
                "value": packet["prastara"][ruler][donor][sign],
            }
            for donor in REFERENCES
        ],
    ]
    other = packet["source_profile_comparison"]["aiyar1905"]
    other_prefix = f"{prefix}.source_profile_comparison.aiyar1905"
    other_count, other_sav = other["bhinna"][ruler][sign], other["samudaya"][house_sign]
    other_paths = [
        {"fact_path": f"{other_prefix}.bhinna.{ruler}.{sign}", "value": other_count},
        {"fact_path": f"{other_prefix}.samudaya.{house_sign}", "value": other_sav},
        *[
            {
                "fact_path": f"{other_prefix}.prastara.{ruler}.{donor}.{sign}",
                "value": other["prastara"][ruler][donor][sign],
            }
            for donor in REFERENCES
        ],
    ]
    return {
        "chart": name,
        "rule_id": RULE,
        "fact_path": paths[0]["fact_path"],
        "fact": count,
        "source_id": SOURCE["id"],
        "source_section": "12.3-12.6; count interpretation12.3",
        "calculation_context": {
            "value_status": "computed_consensus",
            "scenario_count": 1,
            "computed_scenario_count": 1,
            "missing_evidence": [],
            "scenarios": paths[:1],
            "constraints": [
                *paths[1:],
                {"fact_path": "india.ashtakavarga.reductions_applied", "value": False},
            ],
            "context_paths": [row["fact_path"] for row in [*paths, *other_paths]],
            "method_context": {
                "input_claims": [
                    *packet["input_claims"],
                    {
                        "fact_path": "india.ashtakavarga.source_id",
                        "value": SOURCE["id"],
                    },
                    {
                        "fact_path": f"{other_prefix}.source_id",
                        "value": AIYAR_SOURCE["id"],
                    },
                ],
                "reading_rule_id": RULE,
                "reference_instant": "nominal_birth_instant",
                "value_status_scope": "Primary Rao count only; this is not consensus across authors. Other source counts retain their own paths and table rules.",
                "source_profile_comparisons": {
                    "aiyar1905": {
                        "source_id": AIYAR_SOURCE["id"],
                        "ruler_sign_count": other_count,
                        "house_sav": other_sav,
                        "ruler_count_matches_primary": other_count == count,
                        "house_sav_matches_primary": other_sav == sav,
                        "input_claims": other_paths,
                        "scope": "These local aggregates only; their agreement does not adjudicate whole sources, all contributors, varga application or event validity.",
                    }
                },
            },
        },
        "traditional_interpretation": f"名义生时{name}按Rao表，该宫主所在星座有{count}个rekha（8个贡献者的传统有利参考计数）；第{house}宫所在星座的SAV为{sav}，合计七曜目标表。Aiyar1905自己的原始表在同一宫主星座给{other_count}个有利点，该宫SAV为{other_sav}，来源分别保留，不能混作同一套数值。两者不是满分、完整六力或现实成功概率；分盘构造及非D1应用另有声明，给定生时范围须读各样本自己的ashtakavarga_variants。",
    }
