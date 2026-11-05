"""Index independent manuscript strands without inventing per-palace readings.

This source audit deliberately imports no production Taiyi calculations. Literal
occurrence in a four-palace column cannot adjudicate a specific source cell.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v21"
SIKU_CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v20"
MANIFEST_SHA256 = "e3e341c7d4b6d3f0c6f2b1ffc8cfde8d3b7e94d6a5a506af18dcc11cc66276e4"
CORRECTION_MANIFEST_SHA256 = (
    "cfe688efa34d9383b262228d9075f568597b4ab09f2ca3ee7df0f45937827e23"
)
SIKU_MANIFEST_SHA256 = (
    "ce8639f43579def116d76649c4606f992808a7669d63722d8cdde001887889a4"
)
EYE_FRAGMENT = re.compile(r"天目(?:內迫|外迫|迫|囚|格)")
# Identifiers of the six differences already published by the V20 geometry
# audit. They select source evidence here; they are not new expected geometry.
PRIOR_DIFFERENCES = ("酉-3", "子-4", "丑-7", "巳-2", "午-8", "坤-6")


def _verified_json_files(
    directory: Path, fingerprint: str, *, manifest_name: str = "manifest.json"
) -> dict[str, Any]:
    raw = (directory / manifest_name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != fingerprint:
        raise ValueError(f"来源清单指纹不符：{directory.name}")
    manifest: dict[str, Any] = json.loads(raw)
    entries = (
        manifest["files"].items()
        if "files" in manifest
        else ((row["file"], row["sha256"]) for row in manifest["source_files"])
    )
    for name, expected in entries:
        if Path(name).name != name:
            raise ValueError("来源清单只接受同目录文件")
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"来源文件指纹不符：{name}")
    for row in manifest.get("prior_source_references", []):
        if (
            hashlib.sha256((SIKU_CORPUS.parent / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError(f"既有来源指纹不符：{row['file']}")
    return manifest


def source_data(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = _verified_json_files(corpus, MANIFEST_SHA256)
    _verified_json_files(
        corpus,
        CORRECTION_MANIFEST_SHA256,
        manifest_name="correction-manifest.json",
    )
    correction = json.loads((corpus / "metadata-correction.json").read_text())
    columns = json.loads((corpus / "physical-columns.json").read_text())
    names = json.loads((corpus / "same-edition-names.json").read_text())
    positions = {row["position"] for row in names["rows"]}
    keys = [(row["position"], row["half"]) for row in columns["columns"]]
    expected_keys = {(p, half) for p in positions for half in ("first", "second")}
    if len(positions) != 16 or len(keys) != 32 or set(keys) != expected_keys:
        raise ValueError("明钞本须保留十六神的全部32物理栏")
    if any(
        row["individual_cell_assignment"] != "not_adjudicated"
        for row in columns["columns"]
    ):
        raise ValueError("本初录未裁定逐宫格子，不可冒充已校定本")
    return {
        "manifest": manifest,
        "columns": columns,
        "names": names,
        "transcription_attribution_correction": correction,
    }


def literal_locations(column: dict[str, Any], text: str) -> list[dict[str, Any]]:
    """Locate text in physical strands, without assigning a palace or meaning."""
    found = []
    for group in column["groups"]:
        for strand, raw in enumerate(group["strands_right_to_left"], start=1):
            for match in re.finditer(re.escape(text), raw):
                found.append(
                    {
                        **column["locator"],
                        "group_from_top": group["group_from_top"],
                        "strand_from_right": strand,
                        "text_offset": match.start(),
                        "raw_strand": raw,
                    }
                )
    return found


def audit(corpus: Path = CORPUS, siku_corpus: Path = SIKU_CORPUS) -> dict[str, Any]:
    ncl = source_data(corpus)
    _verified_json_files(siku_corpus, SIKU_MANIFEST_SHA256)
    cells = json.loads((siku_corpus / "matrix-columns.json").read_text())["cells"]
    columns = ncl["columns"]["columns"]
    by_key = {(c["position"], c["half"]): c for c in columns}
    eye_references = []
    blanks = []
    lacunae = []
    for cell in cells:
        half = "first" if cell["taiyi_number"] <= 4 else "second"
        column = by_key[(cell["wenchang_position"], half)]
        for field in ("condition_column", "result_column"):
            raw = cell[field]["text"]
            common = {
                "siku_cell_id": cell["id"],
                "siku_column": field,
                "siku_locator": cell[field]["locator"],
                "ncl_column_id": column["id"],
                "ncl_locator": column["locator"],
                "ncl_palace_assignment": "not_adjudicated",
                "cell_conflict_resolved": False,
            }
            if raw is None:
                blanks.append(
                    {
                        **common,
                        "siku_text": None,
                        "ncl_physical_groups": column["groups"],
                        "blank_filled": False,
                    }
                )
                continue
            if "〔缺〕" in raw:
                lacunae.append(
                    {
                        **common,
                        "siku_text": raw,
                        "ncl_physical_groups": column["groups"],
                        "lacuna_filled": False,
                    }
                )
            for fragment in re.split("[／；]", raw):
                if EYE_FRAGMENT.fullmatch(fragment):
                    eye_references.append(
                        {
                            **common,
                            "siku_text": fragment,
                            "literal_occurrences_in_ncl_half_column": literal_locations(
                                column, fragment
                            ),
                            "literal_occurrence_counts_as_geometry_match": False,
                        }
                    )
    differences = [
        row for row in eye_references if row["siku_cell_id"] in PRIOR_DIFFERENCES
    ]
    return {
        "completion_claim": False,
        "source_manifest_sha256": MANIFEST_SHA256,
        "correction_manifest_sha256": CORRECTION_MANIFEST_SHA256,
        "siku_manifest_sha256": SIKU_MANIFEST_SHA256,
        "source_edition": ncl["columns"]["source_edition"],
        "source_urls": [
            "https://commons.wikimedia.org/wiki/File:NCL-06604_太乙金鏡式經.pdf",
            "https://commons.wikimedia.org/wiki/File:CADAL06056494_太乙金鏡式經·卷一~卷四.djvu",
        ],
        "required_physical_columns": 32,
        "recorded_physical_columns": len(columns),
        "required_target_cells": 128,
        "adjudicated_ncl_cells": 0,
        "unadjudicated_ncl_cells": 128,
        "source_eye_fragments_indexed": len(eye_references),
        "literal_occurrence_policy": "仅是同神、同四宫半表的字串索引；同栏出现不是同宫或同条件，不能据此增加计算相符数、裁定六处几何差异或补四库空缺。",
        "eye_fragment_references": eye_references,
        "previously_reported_six_differences": differences,
        "siku_blank_columns_retained": blanks,
        "siku_lacunae_retained": lacunae,
        "ncl_physical_columns": columns,
        "same_edition_name_evidence": ncl["names"],
        "transcription_attribution": ncl["transcription_attribution_correction"],
        "new_dated_cases": 0,
        "copied_text_counted_as_calculated_hits": 0,
        "new_geometric_matches_claimed": 0,
        "production_arithmetic_changed": False,
        "matrix_128_cells_accepted": False,
        "whole_classic_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }
