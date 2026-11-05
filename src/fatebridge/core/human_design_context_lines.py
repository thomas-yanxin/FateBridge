"""Enumerate complete charts actually retained in a verified original result.

This is pure witness replay. It is deliberately not an ephemeris or verifier;
the public service first verifies the complete original calculation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Iterator

from fatebridge.core.human_design_cross_coverage import expanded_cross_evidence
from fatebridge.core.human_design_depth import depth_evidence
from fatebridge.core.human_design_historical_polarity import comparison_report
from fatebridge.core.human_design_mechanics import VALID_PROFILES
from fatebridge.core.human_design_native_positions import decode_native_positions
from fatebridge.core.human_design_node_comparisons import reconstruct_node_reference
from fatebridge.core.human_design_primary_diagrams import primary_diagram_evidence
from fatebridge.core.human_design_root_interpretations import candidate_chart
from fatebridge.core.human_design_sample_witness import unpack_sample_witnesses
from fatebridge.core.human_design_source_variants import (
    cross_name_evidence,
    line_variant_impact,
)

METHOD = "human_design_retained_context_line_reference_packet_v2"
SIDES = ("personality", "design")
LEVELS = ("gate", "line", "color", "tone", "base")


def _chart(activations: dict, node_mode: str) -> dict:
    """Rebuild dependencies, never copy nominal fixings or source impacts."""
    chart = candidate_chart(*(deepcopy(activations[s]) for s in SIDES))
    chart["calculation_policy"] = {"node_mode": node_mode}
    chart["depth_evidence"] = depth_evidence(chart)
    return chart


def _context(path: str, kind: str, chart: dict, mode: str, times: dict) -> dict:
    rebuilt = _chart(chart["activations"], mode)
    return {
        "source_path": path,
        "kind": kind,
        "node_mode": mode,
        "epoch_tt": times,
        "chart": rebuilt,
        "profile_in_declared_pairs": rebuilt["profile"] in VALID_PROFILES,
        "source_numeric_line_impacts": line_variant_impact(rebuilt),
        "source_context": {
            "paths_relative_to": "this_context.chart",
            "cross_name_comparison": cross_name_evidence(rebuilt),
            "expanded_cross_name_comparison": expanded_cross_evidence(rebuilt),
            "primary_transcript_diagrams": primary_diagram_evidence(rebuilt),
            "historical_polarity_comparison": comparison_report(rebuilt),
            "nominal_field_names_refer_to_this_context_only": True,
        },
    }


def _times(chart: dict) -> dict:
    return {s: chart["time_scales"][s]["jd_tt"] for s in SIDES}


def _roots(
    path: str, parent: dict, mode: str, required: bool, policy: str
) -> Iterator[dict]:
    precision = parent["design_solver"]["numerical_precision"]
    stem = path + ".design_solver.numerical_precision"
    collections = [
        (
            "design_body_endpoint_assessment.evaluations",
            "numeric_design_endpoint",
            precision["design_body_endpoint_assessment"]["evaluations"],
        )
    ]
    family = precision["local_root_family"]
    if family is not None:
        collections.append(
            (
                "local_root_family.candidates",
                "numeric_design_root_candidate",
                family["candidates"],
            )
        )
    for suffix, kind, rows in collections:
        for i, row in enumerate(rows):
            design = decode_native_positions(
                row["native_positions"],
                mode,
                require_swiss_files=required,
                physical_backend_policy=policy,
            )
            chart = {
                "activations": {
                    "personality": parent["activations"]["personality"],
                    "design": design,
                }
            }
            context = _context(
                f"{stem}.{suffix}.{i}",
                kind,
                chart,
                mode,
                {"personality": _times(parent)["personality"], "design": row["jd_tt"]},
            )
            context["parent_source_path"] = path
            context["native_source_role"] = row["source_role"]
            context["numerical_candidate_is_physical_uncertainty_bound"] = False
            yield context


def iter_contexts(source: dict) -> Iterator[dict]:
    """Every retained whole chart, including repeated source roles, in fixed order."""
    policy = source["calculation_policy"]
    mode, required = policy["node_mode"], policy["require_swiss_files"]
    physical = policy["physical_backend_policy"]
    yield _context("$", "selected_nominal", source, mode, _times(source))
    yield from _roots("$", source, mode, required, physical)
    report = source["node_convention_comparison"]
    other = "mean" if mode == "true" else "true"
    alternative = reconstruct_node_reference(
        source, report["reference_node_positions"], other, require_swiss_files=required
    )
    yield _context(
        "$.node_convention_comparison.reference_node_positions",
        "alternative_node_convention",
        alternative,
        other,
        _times(source),
    )
    report = source["node_backend_comparison"]
    if isinstance(report.get("reference_node_positions"), dict):
        alternative = reconstruct_node_reference(
            source, report["reference_node_positions"], mode, required_model="moshier"
        )
        yield _context(
            "$.node_backend_comparison.reference_node_positions",
            "node_only_backend_reference",
            alternative,
            mode,
            _times(source),
        )
    report = source["ephemeris_backend_comparison"]
    if report["status"] == "full_backend_compared":
        reference = report["reference_chart"]
        path = "$.ephemeris_backend_comparison.reference_chart"
        yield _context(
            path, "full_backend_reference", reference, mode, _times(reference)
        )
        yield from _roots(path, reference, mode, False, "auto")
    witnesses = source["time_sensitivity"]["evaluation_witnesses"]
    if witnesses is not None:
        samples = unpack_sample_witnesses(
            witnesses,
            mode,
            require_swiss_files=required,
            physical_backend_policy=physical,
        )
        for i, sample in enumerate(samples.values()):
            path = f"$.time_sensitivity.evaluation_witnesses.samples.{i}"
            yield _context(path, "birth_interval_sample", sample, mode, _times(sample))
            yield from _roots(path, sample, mode, required, physical)


def unavailable_contexts(source: dict) -> list[dict]:
    result = []
    for key in ("node_backend_comparison", "ephemeris_backend_comparison"):
        report = source[key]
        complete = (
            isinstance(report.get("reference_node_positions"), dict)
            if key == "node_backend_comparison"
            else report["status"] == "full_backend_compared"
        )
        if not complete:
            result.append(
                {
                    "source_path": "$." + key,
                    "status": report["status"],
                    "complete_chart_assembled": False,
                }
            )
    if source["time_sensitivity"]["evaluation_witnesses"] is None:
        result.append(
            {
                "source_path": "$.time_sensitivity.evaluation_witnesses",
                "status": "interval_not_assessed",
                "complete_chart_assembled": False,
            }
        )
    result.append(
        {
            "source_path": "$.cycle_context",
            "status": source["cycle_context"]["status"],
            "complete_chart_assembled": False,
            "reason": "周期接触是单因子见证，未保留可绑定本解释模型的完整人格／设计双时刻盘；不借用名义盘固定或永久通道条件。",
        }
    )
    return result


def subdivision_changes(nominal: dict, chart: dict) -> list[dict]:
    return [
        {
            "activation_path": f"activations.{side}.{i}",
            "body": b["body"],
            "changed_levels": [k for k in LEVELS if a[k] != b[k]],
            "nominal": {k: a[k] for k in LEVELS},
            "context": {k: b[k] for k in LEVELS},
        }
        for side in SIDES
        for i, (a, b) in enumerate(
            zip(nominal["activations"][side], chart["activations"][side], strict=True)
        )
        if any(a[k] != b[k] for k in LEVELS)
    ]
