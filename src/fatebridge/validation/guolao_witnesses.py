"""Targeted textual variants; never a source of computational cell overrides."""

from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

DATA = (
    Path(__file__).resolve().parents[1] / "data/guolao/gujin45-witness-variants-v1.json"
)
TARGETS = (
    ("day_rate_days", 90),
    ("day_rate_days", 154),
    ("day_rate_days", 166),
    ("signed_increment_ancient_du", 12),
    ("signed_increment_ancient_du", 155),
    ("signed_increment_ancient_du", 163),
)
WITNESSES = ("nlc_cbm1408_volume14", "ncl_06273_part2", "ncl_06272_part2")


def _read() -> tuple[dict[str, Any], str, dict[str, dict[str, Any]]]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    if (
        data["schema_version"] != "gujin45-targeted-witness-variants-v1"
        or data["scope"] != "six_preselected_cells_only"
        or [(t["field"], t["limit_index"]) for t in data["targets"]] != list(TARGETS)
        or [w["witness_id"] for w in data["witnesses"]] != list(WITNESSES)
    ):
        raise ValueError("须保留预先选定的六个争议格和三个新增见证")
    if (
        not data["single_collator"]
        or not data["prior_formula_and_witness_values_known"]
        or any(
            data[key]
            for key in [
                "independent_second_collator",
                "full_additional_table_transcription",
                "textual_ancestry_adjudicated",
                "computational_overrides_authorized",
            ]
        )
    ):
        raise ValueError("本登记不是独立双人校勘、整表复原或计算更改授权")
    baselines = {}
    expected = {
        "src/fatebridge/data/guolao/gujin45-day-rate-v1.json",
        "src/fatebridge/data/guolao/gujin45-cumulative-table-v1.json",
    }
    if set(data["baseline_files_sha256"]) != expected:
        raise ValueError("须绑定同次四库本日率及积度资料，不以异本覆盖")
    for name, digest in data["baseline_files_sha256"].items():
        # Resolve through the package, including in an installed wheel.
        filename = Path(name).name
        contents = (DATA.parent / filename).read_bytes()
        if hashlib.sha256(contents).hexdigest() != digest:
            raise ValueError("四库本既有数据指纹改变，须重新审计而非自动重建基线")
        baselines[filename] = json.loads(contents)
    for witness in data["witnesses"]:
        rows = witness["observations"]
        if [(row["field"], row["limit_index"]) for row in rows] != list(TARGETS):
            raise ValueError("每个见证须逐项保留六个目标，缺值不得省略或补齐")
        for row in rows:
            if (
                row["status"] != "legible_single_collator"
                or not isinstance(row["pdf_page_one_based"], int)
                or row["pdf_page_one_based"] < 1
                or not row["observed_glyphs"]
                or not row["inspection_crop"]
                or not row["complete_page_image"]
            ):
                raise ValueError("读数须有状态、字形和对应原页，不接受推算补字")
            pattern = (
                r"\d+\.\d{4}" if row["field"] == "day_rate_days" else r"-?\d+\.\d{8}"
            )
            if not isinstance(row["value"], str) or not re.fullmatch(
                pattern, row["value"]
            ):
                raise ValueError("数值须保留日率四位及损益八位小数的原读数")
    return data, hashlib.sha256(raw).hexdigest(), baselines


def audit_gujin45_witness_variants() -> dict[str, Any]:
    """Compare all declared readings, without voting, fitting, or cell repair."""
    data, digest, baselines = _read()
    cells = []
    for position, (field, index) in enumerate(TARGETS):
        filename = (
            "gujin45-day-rate-v1.json"
            if field == "day_rate_days"
            else "gujin45-cumulative-table-v1.json"
        )
        baseline_row = baselines[filename]["rows"][index]
        if baseline_row["limit_index"] != index:
            raise ValueError("四库本限序改变，不允许依位置猜配")
        baseline = baseline_row[field]
        readings = [
            {
                "witness_id": data["baseline_witness_id"],
                "value": baseline,
                "source_url": data["baseline_source_url"],
                "djvu_page": baseline_row["djvu_page"],
                "half": baseline_row["half"],
                "status": "previous_single_collator_transcription",
            }
        ]
        for witness in data["witnesses"]:
            row = witness["observations"][position]
            readings.append(
                {
                    "witness_id": witness["witness_id"],
                    **row,
                    "source_url": witness["source_url"],
                    "difference_from_siku_exact": str(
                        Fraction(row["value"]) - Fraction(baseline)
                    ),
                }
            )
        variants = sorted({row["value"] for row in readings}, key=Fraction)
        cells.append(
            {
                "field": field,
                "limit_index": index,
                "readings": readings,
                "distinct_observed_values": variants,
                "status": (
                    "unadjudicated_variant"
                    if len(variants) > 1
                    else "collated_agreement_not_textual_adjudication"
                ),
                "adjudicated_value": None,
                "computational_override": None,
            }
        )
    return {
        "schema_version": data["schema_version"],
        "source_data_sha256": digest,
        "fixture_reference_sha256": data["fixture_reference_sha256"],
        "baseline_files_sha256": data["baseline_files_sha256"],
        "scope": data["scope"],
        "target_selection": data["target_selection"],
        "declared_target_cells": len(TARGETS),
        "additional_witnesses": [
            {key: value for key, value in witness.items() if key != "observations"}
            for witness in data["witnesses"]
        ],
        "additional_readings": len(TARGETS) * len(WITNESSES),
        "cells_with_observed_variants": [
            {"field": cell["field"], "limit_index": cell["limit_index"]}
            for cell in cells
            if cell["status"] == "unadjudicated_variant"
        ],
        "cells": cells,
        "single_collator": True,
        "independent_second_collator": False,
        "formula_or_previous_values_blinded": False,
        "independent_textual_ancestry_established": False,
        "same_printing_blocks_established": False,
        "majority_or_formula_fit_used_for_adjudication": False,
        "full_additional_tables_transcribed": False,
        "can_supply_complete_computational_profile": False,
        "existing_computational_profiles_modified": False,
        "complete_original_or_calendar_accepted": False,
        "new_real_world_prediction_subjects": 0,
        "predictive_validity_demonstrated": False,
    }
