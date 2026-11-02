"""Verify one paragraph's naming directions and eleven literal door/palace pairs."""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.qimen_gate_relations import (
    DOOR_ELEMENTS,
    PALACE_ELEMENTS,
    describe_gate_relations,
    gate_palace_relation,
)


def audit_gate_relations(directory: Path) -> dict[str, Any]:
    ref = json.loads((directory / "sources-and-gate-relations.json").read_text())
    if (
        ref.get("excerpt_file") != "siku-page34.pdf"
        or ref.get("original_one_based_pages") != [34]
        or hashlib.sha256((directory / "siku-page34.pdf").read_bytes()).hexdigest()
        != ref["excerpt_sha256"]
        or ref.get("verse_clause") != "宫制其门不为迫门制其宫是迫雄"
        or ref.get("prose_clause") != "宫制其门是凶迫门制其宫为吉迫门生宫为和宫生门为义"
    ):
        raise ValueError("门宫关系须保留整页指纹、歌诀与正文四名，不能只留吉迫")
    required = {
        ("开门", "震"),
        ("休门", "离"),
        ("生门", "坎"),
        ("景门", "兑"),
        ("伤门", "坤"),
        ("伤门", "艮"),
        ("杜门", "坤"),
        ("杜门", "艮"),
        ("死门", "坎"),
        ("惊门", "震"),
        ("惊门", "巽"),
    }
    if (
        len(ref["examples"]) != 11
        or {(r["door"], r["trigram"]) for r in ref["examples"]} != required
        or {r["clause_group"] for r in ref["examples"]} != set(range(1, 8))
        or ref.get("same_element_named_in_selected_paragraph") is not False
        or ref.get("label_is_real_world_outcome") is not False
    ):
        raise ValueError(
            "须保留七组十一项原文观察，不能补同五行原文名或把关系名当现实结果"
        )
    definitions = ref["definitions"]
    if len(definitions) != 4 or {r["relation"] for r in definitions} != {
        "door_controls_palace",
        "palace_controls_door",
        "door_generates_palace",
        "palace_generates_door",
    }:
        raise ValueError("须保留两种制与两种生的四项关系定义")
    errors = []
    profile = describe_gate_relations()
    for row in definitions:
        actual = gate_palace_relation(row["witness_door"], row["witness_trigram"])
        for key, expected in {
            "relation": row["relation"],
            "prose_label": row["label"],
            **(
                {"verse_door_pressure": row["verse_door_pressure"]}
                if "verse_door_pressure" in row
                else {}
            ),
        }.items():
            if actual[key] != expected:
                errors.append(
                    {
                        "kind": "relation_definition",
                        "field": key,
                        "source_value": expected,
                        "computed_value": actual[key],
                    }
                )
        if profile["prose_labels_by_relation"][row["relation"]] != row["label"]:
            errors.append(
                {
                    "kind": "profile_label",
                    "field": row["relation"],
                    "source_value": row["label"],
                    "computed_value": profile["prose_labels_by_relation"][
                        row["relation"]
                    ],
                }
            )
    observations = []
    door_controls_label = next(
        d["label"] for d in definitions if d["relation"] == "door_controls_palace"
    )
    for row in ref["examples"]:
        actual = gate_palace_relation(row["door"], row["trigram"])
        number = "坎坤震巽中乾兑艮离".index(row["trigram"]) + 1
        matched = (
            number == row["palace_number"]
            and actual["verse_door_pressure"] is True
            and actual["relation"] == "door_controls_palace"
            and actual["prose_label"] == door_controls_label
            and (actual.get("printed_example") or {}).get("category") == row["category"]
        )
        observations.append(
            {
                "door": row["door"],
                "trigram": row["trigram"],
                "matched": matched,
                "relation": actual["relation"],
                "prose_label": actual["prose_label"],
                "printed_category": row["category"],
            }
        )
        if not matched:
            errors.append({"kind": "literal_pair_observation", **observations[-1]})
    probes = [
        gate_palace_relation(door, trigram)
        for door in DOOR_ELEMENTS
        for trigram in PALACE_ELEMENTS
        if trigram != "中"
    ]
    same_name_added = (
        profile.get("same_element_named_in_selected_paragraph") is not False
        or profile.get("prose_labels_by_relation", {}).get("same_element") is not None
        or any(
            e["relation"] == "same_element"
            and (
                e["prose_label"] is not None
                or e.get("same_element_named_in_selected_paragraph") is not False
            )
            for e in probes
        )
    )
    labels_used_as_outcomes = any(
        e.get("prose_label_is_outcome_judgment") is not False
        or e.get("outcome_inference_allowed") is not False
        or (
            e.get("printed_example") is not None
            and e["printed_example"].get("outcome_inference_allowed") is not False
        )
        for e in probes
    )
    if same_name_added:
        errors.append({"kind": "unsupported_same_element_source_name"})
    if labels_used_as_outcomes:
        errors.append({"kind": "source_label_used_as_outcome"})
    for e in probes:
        example = e.get("printed_example")
        if example is not None and (
            (e["door"], e["trigram"]) not in required
            or example.get("scope")
            != "literal_door_palace_observation_not_global_door_classification"
        ):
            errors.append(
                {
                    "kind": "unsupported_printed_example_scope",
                    "door": e["door"],
                    "trigram": e["trigram"],
                }
            )
    return {
        "method_id": "qimen_gate_palace_source_relations_v1",
        "source_relation_definition_count": 4,
        "derived_witness_count": 4,
        "printed_clause_group_count": 7,
        "literal_pair_observation_count": 11,
        "matched_pair_observation_count": sum(o["matched"] for o in observations),
        "observations": observations,
        "disagreements": errors,
        "finite_evidence_scope_probes": len(probes),
        "same_element_source_name_added": same_name_added,
        "source_labels_used_as_outcome_judgments": labels_used_as_outcomes,
        "whole_book_conformance_established": False,
        "real_world_efficacy_validated": False,
        "scope": "Four wording directions and eleven literal door/palace observations, not eleven dated complete charts or outcome cases",
    }
