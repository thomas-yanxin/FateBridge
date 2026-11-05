"""Keep a given-position example, hand derivations and edition witnesses separate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v24"
MANIFEST_SHA = "ccd2d9b5cbaef1ace5a1233367b5baa5c3d2f9aace4e91a5443d72a002fcc485"


def source_data(corpus: Path = CORPUS) -> dict[str, Any]:
    raw = (corpus / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError("始击来源清单指纹不符")
    manifest = json.loads(raw)
    for item in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("始击原文/书影/初录指纹不符")
    for item in manifest["prior_references"]:
        if (
            hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("此前来源材料指纹不符")
    witnesses = json.loads((corpus / "wujing-focus-readings.json").read_text())
    manual = json.loads((corpus / "manual-ring-pairs.json").read_text())
    if [r["ju"] for r in witnesses] != [37, 43, 44] or len(manual) != 4:
        raise ValueError("不得删减已有争议与手工算路")
    return {
        "manifest": manifest,
        "readings": json.loads((corpus / "source-readings.json").read_text()),
        "witnesses": witnesses,
        "manual_pairs": manual,
    }


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    source = source_data(corpus)
    from fatebridge.core.metaphysics.taiyi_shiji import rotate_shiji
    from fatebridge.core.metaphysics.taiyi_source_alignment import (
        count_source_assessment,
    )
    from fatebridge.core.metaphysics.taiyi_year import cyclic_core

    comparisons = []
    for row in source["manual_pairs"]:
        actual = rotate_shiji(row["wenchang"], row["jishen"])
        pairs = [[p["heaven_spirit"], p["earth_spirit"]] for p in actual["pairs"]]
        comparisons.append(
            {
                **row,
                "actual_pairs": pairs,
                "actual_shiji": actual["derived_shiji"],
                "matches": pairs == row["pairs"]
                and actual["derived_shiji"] == row["expected_shiji"],
            }
        )
    witnesses = []
    for row in source["witnesses"]:
        actual = cyclic_core(row["ju"], yin=row["yin"])
        selected = count_source_assessment(actual)
        witnesses.append(
            {
                **row,
                "comparison": [
                    {
                        "field": key,
                        "source_value": value,
                        "actual_value": actual[key],
                        "matches": value == actual[key],
                    }
                    for key, value in row["fields"].items()
                ],
                "jinjing_source_shiji": next(
                    p["source_value"]
                    for p in selected["positions"]
                    if p["field"] == "shiji"
                ),
                "jinjing_source_guest_count": next(
                    p["source_table_count"]
                    for p in selected["counts"]
                    if p["camp"] == "guest"
                ),
                "jinjing_disagreements_retained": selected["summary"],
            }
        )
    return {
        "source_manifest_sha256": MANIFEST_SHA,
        "given_position_examples": [
            r
            for r in comparisons
            if r["kind"] == "explicit_primary_given_positions_example"
        ],
        "manual_applications_of_existing_rows": [
            r
            for r in comparisons
            if r["kind"] != "explicit_primary_given_positions_example"
        ],
        "manual_rotation_pairs": sum(len(r["pairs"]) for r in comparisons),
        "given_same_position_example_alone_discriminates_rotation_direction": False,
        "witness_observations": sum(len(r["comparison"]) for r in witnesses),
        "witness_matching_observations": sum(
            p["matches"] for r in witnesses for p in r["comparison"]
        ),
        "witnesses": witnesses,
        "siku_source_replaced": False,
        "siku_three_shiji_differences_resolved": False,
        "production_numeric_correction_claimed": False,
        "new_dated_cases": 0,
        "classical_acceptance_passed": False,
        "full_ancient_calendar_reconstructed": False,
        "real_world_efficacy": "not_tested",
        "scope": source["manifest"]["scope"],
    }
