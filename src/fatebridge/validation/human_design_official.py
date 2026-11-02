"""Finite conformance to frozen visible official chart facts, never life efficacy."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fatebridge.core.human_design import chart_at
from fatebridge.core.human_design_cross_coverage import cross_coverage_reference
from fatebridge.core.human_design_evidence import source_reference
from fatebridge.services.human_design import calculate_human_design


def combine_official_chart_cohorts(*references: dict[str, Any]) -> dict[str, Any]:
    """Keep cohort selection scopes visible when aggregating finite observations."""
    if not references:
        raise ValueError("At least one frozen official cohort is required")
    first = references[0]
    if any(
        ref["planet_order"] != first["planet_order"]
        or ref["source"]["url"] != first["source"]["url"]
        for ref in references
    ):
        raise ValueError("Cannot combine different source URLs or body orders")
    return {
        **first,
        "cases": [case for ref in references for case in ref["cases"]],
        "cohorts": [
            {
                "chart_count": len(ref["cases"]),
                "scope": ref["scope"],
                "source": ref["source"],
            }
            for ref in references
        ],
        "scope": "Combined finite official cohorts, with each original selection scope retained. No blind population, exhaustive original text, fine-subdivision precision or predictive certification. Literal cross names compared without replacing 2001 variant numbers or spelling.",
    }


def _birth_clock_link(calculated: str, displayed: str) -> dict[str, Any]:
    actual = datetime.fromisoformat(calculated)
    source = datetime.fromisoformat(displayed)
    if actual.utcoffset() is None or source.utcoffset() is None:
        raise ValueError("Official clock links require explicit UTC offsets")
    delta = (actual - source).total_seconds()
    return {
        "status": (
            "same_nominal_instant" if delta == 0 else "nominal_clock_disagreement"
        ),
        "calculated_birth_utc": calculated,
        "displayed_source_birth_utc": displayed,
        "exact_label_match": calculated == displayed,
        "same_nominal_instant": delta == 0,
        "calculated_minus_displayed_seconds": delta,
        "ephemeris_cause_isolated": False,
        "physical_clock_accuracy_certified": False,
        "scope": "Nominal labels only; the displayed source may have limited precision. All original comparisons remain. Different instants cannot isolate an ephemeris error; matching labels do not authenticate historical clocks, future leaps or the source's internal TT.",
    }


def official_chart_checks(
    reference: dict[str, Any], *, include_clock_link_evidence: bool = False
) -> dict[str, Any]:
    if (
        set(reference["planet_order"])
        != {
            "Sun",
            "Earth",
            "Moon",
            "NorthNode",
            "SouthNode",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Uranus",
            "Neptune",
            "Pluto",
        }
        or len(reference["planet_order"]) != 13
    ):
        raise ValueError("Official body order must contain all 13 distinct bodies")
    if len({c["id"] for c in reference["cases"]}) != len(reference["cases"]):
        raise ValueError("Duplicate official case identifiers")
    pairs = {
        tuple(sorted(p)) for g in source_reference()["gates"] for p in g["channels"]
    }
    render_pairs = {"c" + "".join(map(str, pair)): pair for pair in pairs}
    type_map = {
        "Generator": ("generator", "pure_generator"),
        "Manifesting Generator": ("generator", "manifesting_generator"),
        "Projector": ("projector", None),
        "Manifestor": ("manifestor", None),
        "Reflector": ("reflector", None),
    }
    authority_map = {
        "Solar Plexus": "emotional",
        "Sacral": "sacral",
        "Splenic": "splenic",
        "Ego Manifested": "ego_manifested",
        "Ego Projected": "ego_projected",
        "Self Projected": "self_projected",
        "Sounding Board": "environment_no_inner_authority",
        "Lunar Cycle": "lunar_no_inner_authority",
    }
    definition_map = {
        "None": "none",
        "Single": "single",
        "Split": "split",
        "Triple Split": "triple_split",
    }
    # Do not silently expand an older frozen cohort's source vocabulary. The
    # new visible label is supported by the separately pinned observations.
    source_proofs = [reference["source"]] + [
        c["source"] for c in reference.get("cohorts", [])
    ]
    observed_source = cross_coverage_reference()["source"]["observation_fixture_sha256"]
    if any(
        s.get("observation_fixture_sha256") == observed_source for s in source_proofs
    ):
        definition_map["Quadruple Split"] = "quadruple_split"
    angle_map = {
        "Right Angle": "right",
        "Left Angle": "left",
        "Juxtaposition": "juxtaposition",
    }
    cases = []
    for case in reference["cases"]:
        if set(case["columns"]) != {"personality", "design"}:
            raise ValueError("Both official activation columns are required")
        actual = calculate_human_design(**case["birth_input"], node_mode="true")
        if "error" in actual:
            cases.append(
                {
                    "id": case["id"],
                    "status": "calculation_error",
                    "error": actual["error"],
                }
            )
            continue
        mean = chart_at(datetime.fromisoformat(case["displayed_birth_utc"]), "mean")
        mismatches = []
        mean_matches = 0
        for side, column in case["columns"].items():
            if len(column) != 13 or len(reference["planet_order"]) != 13:
                raise ValueError("Incomplete official activation column")
            observed = {a["body"]: a for a in actual["activations"][side]}
            mean_observed = {a["body"]: a for a in mean["activations"][side]}
            for body, expected in zip(reference["planet_order"], column):
                if not re.fullmatch(r"(?:[1-9]|[1-5][0-9]|6[0-4])\.[1-6]", expected):
                    raise ValueError("Invalid frozen official gate.line")
                row = observed[body]
                if f"{row['gate']}.{row['line']}" != expected:
                    mismatches.append(
                        {
                            "side": side,
                            "body": body,
                            "expected": expected,
                            "actual": f"{row['gate']}.{row['line']}",
                        }
                    )
                m = mean_observed[body]
                mean_matches += f"{m['gate']}.{m['line']}" == expected
        properties = case["properties"]
        if (
            properties["Type"] not in type_map
            or properties["Authority"] not in authority_map
            or properties["Definition"] not in definition_map
        ):
            raise ValueError(
                "Unknown official property label; expand source evidence first"
            )
        expected_type, expected_subtype = type_map[properties["Type"]]
        cross_match = re.fullmatch(
            r"(Right Angle|Left Angle|Juxtaposition) Cross of (.+?)\s+"
            r"\((\d+)/(\d+) \| (\d+)/(\d+)\)",
            properties["Incarnation Cross"],
        )
        if cross_match is None:
            raise ValueError("Official cross format outside this frozen cohort")
        cross_gates = list(map(int, cross_match.groups()[2:]))
        if any(not 1 <= gate <= 64 for gate in cross_gates):
            raise ValueError("Invalid official incarnation cross gate")
        expected_channels = {
            render_pairs[key] for key in case["defined_channel_render_ids"]
        }
        graph = actual["bodygraph"]
        checks = {
            "birth_utc": actual["birth_utc"] == case["displayed_birth_utc"],
            "type": graph["type"] == expected_type,
            "subtype": graph["subtype"] == expected_subtype,
            "authority": graph["authority"] == authority_map[properties["Authority"]],
            "definition": graph["definition"]["kind"]
            == definition_map[properties["Definition"]],
            "defined_centers": {
                "ego" if c == "heart" else c for c in case["defined_centers"]
            }
            == {c for c, v in graph["centers"].items() if v["status"] == "defined"},
            "complete_channels": expected_channels
            == {tuple(sorted(c["gates"])) for c in graph["channels"]},
            "profile": actual["profile"] == properties["Profile"],
            "cross_angle": actual["incarnation_cross"]["angle"]
            == angle_map[cross_match[1]],
            "cross_gates": actual["incarnation_cross"]["gates"] == cross_gates,
            "cross_name": " ".join(actual["incarnation_cross"]["name"].upper().split())
            == " ".join(cross_match[2].upper().split()),
            "variables": actual["variables"]["code"] == properties["Variable"],
        }
        if "Strategy" in properties:
            strategies = {
                "Wait to Respond": "respond",
                "To Inform": "inform",
                "Wait for Recognition and the Invitation": "recognition_and_invitation",
                "Wait a Lunar Cycle": "wait_a_lunar_cycle",
            }
            if properties["Strategy"] not in strategies:
                raise ValueError("Unknown observed strategy label")
            checks["strategy"] = graph["strategy"] == strategies[properties["Strategy"]]
        cases.append(
            {
                "id": case["id"],
                "status": (
                    "matched" if not mismatches and all(checks.values()) else "failed"
                ),
                "gate_lines_checked": 26,
                "gate_lines_matched": 26 - len(mismatches),
                "gate_line_mismatches": mismatches,
                "structure_checks": checks,
                "cross_name_comparison": {
                    "primary_2001_name": actual["incarnation_cross"]["name"],
                    "official_display_name": cross_match[2],
                    "exact_name_matched": checks["cross_name"],
                    "primary_source_url": actual["incarnation_cross"]["source_url"],
                    "scope": "Literal label comparison after whitespace/case normalization only; original variant numbers and spelling retained. No aliases silently accepted.",
                },
                "selected_variable_code": actual["variables"]["code"],
                "mean_node_gate_lines_matched": mean_matches,
                "mean_node_variable_code": mean["variables"]["code"],
                "observed_ephemeris_models": sorted(
                    {
                        a["ephemeris_model"]
                        for acts in actual["activations"].values()
                        for a in acts
                    }
                ),
                "source_pdf_sha256": case["pdf_sha256"],
            }
        )
        if include_clock_link_evidence:
            cases[-1]["birth_clock_link"] = _birth_clock_link(
                actual["birth_utc"], case["displayed_birth_utc"]
            )
    passed = bool(cases) and all(c["status"] == "matched" for c in cases)
    report = {
        "status": "bounded_official_examples_matched" if passed else "failed",
        "charts_checked": len(reference["cases"]),
        "charts_matched": sum(c["status"] == "matched" for c in cases),
        "gate_lines_checked": sum(c.get("gate_lines_checked", 0) for c in cases),
        "gate_lines_matched": sum(c.get("gate_lines_matched", 0) for c in cases),
        "charts_with_all_mechanics_matched": sum(
            c.get("gate_lines_matched") == 26
            and all(
                value
                for key, value in c.get("structure_checks", {}).items()
                if key != "cross_name"
            )
            for c in cases
        ),
        "cross_names_exactly_matched": sum(
            c.get("structure_checks", {}).get("cross_name", False) for c in cases
        ),
        "cases": cases,
        "coverage": {
            "years": sorted(
                {c["birth_input"]["birth_year"] for c in reference["cases"]}
            ),
            "displayed_types": sorted(
                {c["properties"]["Type"] for c in reference["cases"]}
            ),
            "displayed_authorities": sorted(
                {c["properties"]["Authority"] for c in reference["cases"]}
            ),
            "authority_ids": sorted(
                {
                    authority_map[c["properties"]["Authority"]]
                    for c in reference["cases"]
                }
            ),
            "definitions": sorted(
                {c["properties"]["Definition"] for c in reference["cases"]}
            ),
            "cross_angles": sorted(
                {
                    next(
                        value
                        for label, value in angle_map.items()
                        if c["properties"]["Incarnation Cross"].startswith(
                            label + " Cross"
                        )
                    )
                    for c in reference["cases"]
                }
            ),
            "profiles": sorted(
                {c["properties"]["Profile"] for c in reference["cases"]}
            ),
            "crosses": sorted(
                {c["properties"]["Incarnation Cross"] for c in reference["cases"]}
            ),
            "variable_codes": sorted(
                {c["properties"]["Variable"] for c in reference["cases"]}
            ),
        },
        "source_url": reference["source"]["url"],
        "cohorts": reference.get("cohorts", []),
        "scope": reference["scope"],
        "global_node_convention_certified": False,
        "full_original_text_certified": False,
        "physical_subdivision_accuracy_certified": False,
    }
    if include_clock_link_evidence:
        linked = [
            c
            for c in cases
            if c.get("birth_clock_link", {}).get("same_nominal_instant") is True
        ]
        unlinked = [
            c
            for c in cases
            if c.get("birth_clock_link", {}).get("same_nominal_instant") is False
        ]
        report["birth_clock_link_summary"] = {
            "same_nominal_instant_case_ids": [c["id"] for c in linked],
            "nominal_clock_disagreement_case_ids": [c["id"] for c in unlinked],
            "unassessed_case_ids": [
                c["id"] for c in cases if "birth_clock_link" not in c
            ],
            "linked_gate_lines_checked": sum(c["gate_lines_checked"] for c in linked),
            "linked_gate_lines_matched": sum(c["gate_lines_matched"] for c in linked),
            "unlinked_gate_lines_checked": sum(
                c["gate_lines_checked"] for c in unlinked
            ),
            "unlinked_gate_lines_matched": sum(
                c["gate_lines_matched"] for c in unlinked
            ),
            "original_counts_and_grades_retained": True,
            "physical_clock_accuracy_certified": False,
            "scope": "Additional causal context only. Original failed cases and raw comparison counts are unchanged; neither group certifies ephemeris truth or source clock accuracy.",
        }
    return report
