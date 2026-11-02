"""Opt-in structural source annotations; no new full-line semantic acceptance."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from fatebridge.core import human_design_knowledge_v3 as parent
from fatebridge.core import human_design_line_catalogue as base
from fatebridge.core.human_design_references import coherent_human_design_references
from fatebridge.utils.errors import EphemerisSourceError

CATEGORY = "lines_v4"
CATALOGUE_PATH = base.CATALOGUE_PATH.with_name("context-clauses-2001-v1.json")
CATALOGUE_SHA256 = "cc82bc7418315c90edc182c3e510842b1e79cdd583aaf587f99a664b286b5d4b"
KEYS = ["2.3", "6.3", "7.2", "12.6", "42.1"]
SCOPE = (
    "另有5条局部结构条款注释（含既有2.3），不增加完整爻义覆盖。"
    "连接只作各完整盘的图结构观察，不自动判定原文现实效果；42.1保留两种拓扑观察，"
    "不把‘特别是在’改成必要条件。6.3不计算生育结果。"
)


def _catalogue() -> tuple[dict, dict[Path, bytes], dict]:
    data, snapshot, provenance = parent._catalogue()
    base._check_end(snapshot)
    try:
        raw = CATALOGUE_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != CATALOGUE_SHA256:
            raise ValueError("Context annotation catalogue changed")
        catalogue = json.loads(
            raw, object_pairs_hook=base._object, parse_constant=base._nonfinite
        )
        if (
            catalogue["schema_version"] != 1
            or catalogue["version"] != 4
            or catalogue["catalogue_id"] != "human_design_line_context_annotations_v4"
            or catalogue["parent_version"] != data["version"]
            or catalogue["parent_manifest_sha256"] != parent.MANIFEST_SHA256
            or catalogue["source_pdf_sha256"] != data["source"]["pdf_sha256"]
            or catalogue["local_paraphrase_count"] != 18
            or catalogue["independently_accepted_line_count"] != 0
            or catalogue["publisher_master_authenticated"] is not False
            or catalogue["complete384_line_meanings_accepted"] is not False
            or catalogue["source_conditions_exhaustively_reviewed"] is not False
            or [r["key"] for r in catalogue["annotations"]] != KEYS
        ):
            raise ValueError("Invalid context annotation scope or parent")
        by_key = {r["key"]: r for r in catalogue["annotations"]}
        for row in data["rows"]:
            annotation = by_key.get(row["key"])
            row["source_context_annotations"] = None
            if annotation is None:
                continue
            if (
                annotation["source_pdf_page_one_based"]
                != row["source_pdf_page_one_based"]
                or annotation["source_layout_block_sha256"]
                != row["source_layout_block_sha256"]
                or annotation["personal_condition_satisfied"] is not None
                or annotation["automatic_application"] is not False
                or annotation["complete_line_meaning_accepted"] is not False
                or annotation["independent_semantic_review_completed"] is not False
                or annotation["selected_source_interpretation"] is not None
                or annotation["source_interpretation_resolved"] is not False
            ):
                raise ValueError("Invalid locator or invented applicability")
            row["source_context_annotations"] = [deepcopy(annotation)]
        data.update(version=4, catalogue_id=catalogue["catalogue_id"])
        base._check_end(snapshot)
        snapshot[CATALOGUE_PATH] = raw
        provenance.update(
            source_catalogue_version=4,
            source_catalogue_content_sha256=hashlib.sha256(
                base._canonical(data)
            ).hexdigest(),
            scope=base._scope(data) + SCOPE,
            local_structural_clause_annotations=5,
            newly_annotated_source_lines=4,
        )
        provenance["source_records"].append(
            {
                "domain": base.DOMAIN,
                "key": CATALOGUE_PATH.stem,
                "source_path": "human_design/" + CATALOGUE_PATH.name,
                "loaded_file_sha256": CATALOGUE_SHA256,
                "source_pdf_sha256": catalogue["source_pdf_sha256"],
                "source_kind": "bounded_local_source_context_annotations",
                "source_revision": 4,
                "review_status": "five_local_clause_annotations_not_full_line_acceptance",
                "scope": SCOPE,
            }
        )
        return data, snapshot, provenance
    except (OSError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise EphemerisSourceError("human_design_reference_invalid") from exc


def _registry_category() -> tuple[dict, dict[Path, bytes]]:
    data, snapshot, provenance = _catalogue()
    return {
        "name": CATEGORY,
        "count": 384,
        "keys_sample": KEYS,
        "keys_complete": False,
        "key_format": "gate.line；显式v4结构条款注释，默认lines仍为v2",
        "supports": ["key"],
        "reference_only": True,
        "coverage": base._coverage(data),
        "provenance": provenance,
    }, snapshot


def read_reference(*, key: str | None) -> dict:
    with coherent_human_design_references():
        # Validate the key through the unchanged parent contract.
        entry = parent.read_reference(key=key)
        data, snapshot, provenance = _catalogue()
        gate, line = map(int, entry["key"].split("."))
        row = deepcopy(data["rows"][(gate - 1) * 6 + line - 1])
        entry["reference_details"]["record"].update(row)
        entry["category"] = CATEGORY
        entry["title"] = entry["title"].replace("（v3）", "（v4）")
        tips = list(entry["tips"])
        tips.extend(
            a["editorial_summary_zh"] for a in row["source_context_annotations"] or []
        )
        tips.append(SCOPE)
        entry.update(
            tips=tips,
            lines=list(tips),
            rendered_text="\n".join([entry["title"], *tips]),
            provenance=provenance,
        )
        base._check_end(snapshot)
        return entry
