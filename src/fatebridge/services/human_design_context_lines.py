"""Bind line references separately to every retained complete chart context."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256

from fatebridge.core import human_design_knowledge as knowledge
from fatebridge.core.human_design_context_lines import (
    METHOD,
    iter_contexts,
    subdivision_changes,
    unavailable_contexts,
)
from fatebridge.core.human_design_line_catalogue import _canonical
from fatebridge.core.human_design_line_reading import _compose
from fatebridge.core.human_design_references import coherent_human_design_references
from fatebridge.services.human_design_line_reading import build_human_design_line_packet


def _digest(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def build_human_design_context_packet(
    source_result: dict, *, reference_category: str = "lines"
) -> dict:
    if reference_category not in {
        "lines",
        "lines_v3",
        "lines_v4",
        "lines_v5",
        "lines_v6",
        "lines_v7",
    }:
        raise ValueError("Unsupported Human Design line reference category")
    source = deepcopy(source_result)
    with coherent_human_design_references():
        # The complete original verifier runs here before extracting any contexts.
        nominal = build_human_design_line_packet(source)
        if reference_category == "lines":
            data, snapshot = knowledge._catalogue()
            provenance = knowledge._provenance(data, snapshot)
            if nominal["line_reference_provenance"] != provenance:
                raise ValueError(
                    "Nominal packet and context references have different sources"
                )
            references = deepcopy(nominal["line_reading"]["source_references"])
        elif reference_category == "lines_v3":
            from fatebridge.core.human_design_knowledge_v3 import _catalogue

            data, snapshot, provenance = _catalogue()
            references = {}
        elif reference_category == "lines_v4":
            from fatebridge.core.human_design_knowledge_v4 import (
                _catalogue as context_catalogue,
            )

            data, snapshot, provenance = context_catalogue()
            references = {}
        elif reference_category == "lines_v5":
            from fatebridge.core.human_design_knowledge_v5 import (
                _catalogue as gate4_catalogue,
            )

            data, snapshot, provenance = gate4_catalogue()
            references = {}
        elif reference_category == "lines_v6":
            from fatebridge.core.human_design_knowledge_v6 import (
                _catalogue as gate5_catalogue,
            )

            data, snapshot, provenance = gate5_catalogue()
            references = {}
        else:
            from fatebridge.core.human_design_knowledge_v7 import (
                _catalogue as gate6_catalogue,
            )

            data, snapshot, provenance = gate6_catalogue()
            references = {}
        contexts: list[dict] = []
        groups: dict[str, dict] = {}
        for context in iter_contexts(source):
            chart = context["chart"]
            keys = dict.fromkeys(
                f"{r['gate']}.{r['line']}"
                for r in chart["depth_evidence"]["line_fixings"]
            )
            for key in keys:
                if key not in references:
                    references[key] = knowledge.read_reference(
                        category=reference_category, key=key
                    )
            # Raw coordinates/Color/Tone/Base are retained per context; all line
            # reading dependencies below are explicit and shared only if identical.
            dependencies = {
                "activations": {
                    s: [{k: a[k] for k in ("body", "gate", "line")} for a in rows]
                    for s, rows in chart["activations"].items()
                },
                **{
                    k: chart[k]
                    for k in (
                        "bodygraph",
                        "depth_evidence",
                        "profile",
                        "incarnation_cross",
                        "calculation_policy",
                    )
                },
            }
            if reference_category in {
                "lines_v3",
                "lines_v4",
                "lines_v5",
                "lines_v6",
                "lines_v7",
            }:
                dependencies["reference_catalogue_content_sha256"] = provenance[
                    "source_catalogue_content_sha256"
                ]
            group_id = _digest(dependencies)
            if group_id not in groups:
                # Compose from the dependency projection itself: fine subdivisions
                # cannot silently affect a supposedly shared reading.
                assembled = _compose(
                    dependencies,
                    {k: references[k] for k in keys},
                    source_available_poles_only=reference_category
                    in {"lines_v6", "lines_v7"},
                )
                rows = assembled["rows"]
                for row_index, row in enumerate(rows):
                    row["reading"] = row["reading"].replace(
                        "当前所选名义盘", "此计算上下文"
                    )
                    if reference_category in {
                        "lines_v3",
                        "lines_v4",
                        "lines_v5",
                        "lines_v6",
                        "lines_v7",
                    }:
                        record = references[row["reference_key"]]["reference_details"][
                            "record"
                        ]
                        row["source_qualifiers"] = deepcopy(
                            record.get("source_qualifiers")
                        )
                        row["heading_corroboration"] = deepcopy(
                            record.get("heading_corroboration")
                        )
                        if reference_category in {
                            "lines_v4",
                            "lines_v5",
                            "lines_v6",
                            "lines_v7",
                        }:
                            from fatebridge.core.human_design_source_context import (
                                bind_source_context,
                            )

                            annotations = record["source_context_annotations"]
                            bound = (
                                None
                                if annotations is None
                                else [
                                    bind_source_context(
                                        a,
                                        dependencies,
                                        dependencies["depth_evidence"]["line_fixings"][
                                            row_index
                                        ],
                                    )
                                    for a in annotations
                                ]
                            )
                            row["bound_source_context_annotations"] = bound
                            for annotation in bound or []:
                                row["reading"] += annotation["reading"]
                groups[group_id] = {
                    "dependency_sha256": group_id,
                    "rows": rows,
                    "coverage": assembled["coverage"],
                    "whole_chart_context": {
                        k: deepcopy(chart[k])
                        for k in (
                            "bodygraph",
                            "profile",
                            "incarnation_cross",
                            "calculation_policy",
                        )
                    },
                    "paths_relative_to": "each_linked_context.chart",
                    "source_context_dependent_meaning_accepted": False,
                }
            context.update(
                context_index=len(contexts),
                line_reading_group_id=group_id,
                chart_sha256=_digest(chart),
                subdivision_changes_from_nominal=subdivision_changes(source, chart),
            )
            contexts.append(context)
        if any(r["provenance"] != provenance for r in references.values()):
            raise ValueError("Context references do not share one source snapshot")
        result = {
            "method_id": METHOD,
            "packet_version": 2,
            "nominal_packet_v1": nominal,
            "contexts": contexts,
            "line_reading_groups": groups,
            "source_references": references,
            "line_reference_provenance": provenance,
            "unassembled_contexts": unavailable_contexts(source),
            "coverage": {
                "retained_complete_chart_contexts": len(contexts),
                "contexts_by_kind": dict(Counter(c["kind"] for c in contexts)),
                "activation_context_bindings": 26 * len(contexts),
                "distinct_line_reading_groups": len(groups),
                "distinct_source_line_references": len(references),
                "independently_accepted_full_line_meanings": 0,
                "source_conditions_exhaustively_reviewed": False,
                "repeated_source_roles_count_as_independent_evidence": False,
            },
            "complete384_line_semantics_accepted": False,
            "arbitrary_model_free_text_accepted": False,
            "publisher_master_authenticated": False,
            "continuous_interval_stability_certified": False,
            "physical_time_accuracy_certified": False,
            "real_world_prediction_validated": False,
            "scope": "逐一绑定原回执实际保留的完整双时刻盘、交点／后端对照、区间求值及数值设计候选。固定、通道条件、类型、权威、角色和原典数值分歧均取各自上下文。数值候选不是物理误差界，有限样本不认证连续生时区间；共享解释组不丢弃原始上下文，也不增加独立证据数。周期缺完整盘时保留未组装；本包仍非完整384爻义、任意模型文字或现实预测验收。",
        }
        if reference_category == "lines_v3":
            result.update(
                method_id="human_design_retained_context_line_reference_packet_v3",
                packet_version=3,
                reference_category=reference_category,
            )
        if reference_category == "lines_v4":
            result.update(
                method_id="human_design_retained_context_line_reference_packet_v4",
                packet_version=4,
                reference_category=reference_category,
            )
        if reference_category == "lines_v5":
            result.update(
                method_id="human_design_retained_context_line_reference_packet_v5",
                packet_version=5,
                reference_category=reference_category,
            )
        if reference_category == "lines_v6":
            result.update(
                method_id="human_design_retained_context_line_reference_packet_v6",
                packet_version=6,
                reference_category=reference_category,
                source_polarity_wording_policy="enumerated_source_poles_no_invented_opposite_v1",
            )
        if reference_category == "lines_v7":
            result.update(
                method_id="human_design_retained_context_line_reference_packet_v7",
                packet_version=7,
                reference_category=reference_category,
                source_polarity_wording_policy="enumerated_source_poles_no_invented_opposite_v1",
            )
        knowledge._check_end(snapshot)
        return result
