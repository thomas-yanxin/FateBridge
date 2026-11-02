"""Explicit v3 editorial references; the default v2 catalogue remains pinned."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from fatebridge.core import human_design_line_catalogue as base
from fatebridge.core.human_design_references import coherent_human_design_references
from fatebridge.utils.errors import EphemerisSourceError

CATEGORY = "lines_v3"
MANIFEST_PATH = base.CATALOGUE_PATH.with_name("line-knowledge-manifest-v3.json")
MANIFEST_SHA256 = "60f844ca3a00ee1ad9b3836a94f68d74553089a3127e8240dc9694b2e3f99ec3"
SUPPLEMENT_PATH = base.CATALOGUE_PATH.with_name("line-knowledge-gate3-v1.json")
SAMPLE_SHA256 = "bbdb7bfa006bd0e8245c419bd607ee7b0c6919ec00c25faaecc15290cd1f0568"
HEADINGS = [
    "Synthesis",
    "Immaturity",
    "Survival",
    "Charisma",
    "Victimization",
    "Surrender",
]


def _catalogue() -> tuple[dict, dict[Path, bytes], dict]:
    parent, snapshot = base._catalogue()
    data = deepcopy(parent)
    try:
        raw = MANIFEST_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            raise ValueError("Version3 reference manifest changed")
        manifest = json.loads(
            raw, object_pairs_hook=base._object, parse_constant=base._nonfinite
        )
        if (
            manifest["schema_version"] != 1
            or manifest["version"] != 3
            or manifest["catalogue_id"] != "human_design_line_knowledge_v3"
            or manifest["parent_version"] != parent["version"]
            or manifest["parent_manifest_sha256"] != base.MANIFEST_SHA256
            or manifest["required_line_count"] != 384
            or manifest["expected_local_paraphrase_count"] != 18
            or manifest["independently_accepted_line_count"] != 0
            or manifest["publisher_master_authenticated"] is not False
            or manifest["complete384_line_meanings_accepted"] is not False
            or manifest["publisher_sample_sha256"] != SAMPLE_SHA256
            or manifest["corroborated_headings_only"] != HEADINGS
            or len(manifest["supplements"]) != 1
        ):
            raise ValueError("Invalid v3 scope or certification")
        binding = manifest["supplements"][0]
        if binding["file"] != "line-knowledge-gate3-v1.json" or binding["keys"] != [
            f"3.{i}" for i in range(1, 7)
        ]:
            raise ValueError("Invalid supplementary keys or path")
        added = SUPPLEMENT_PATH.read_bytes()
        if hashlib.sha256(added).hexdigest() != binding["sha256"]:
            raise ValueError("Version3 supplement changed")
        supplement = json.loads(
            added, object_pairs_hook=base._object, parse_constant=base._nonfinite
        )
        if (
            supplement["schema_version"] != 1
            or supplement["supplement_id"] != "human_design_gate3_editorial_v1"
            or supplement["base_catalogue_sha256"] != base.CATALOGUE_SHA256
            or supplement["source_pdf_sha256"] != parent["source"]["pdf_sha256"]
            or supplement["independently_accepted_line_count"] != 0
            or supplement["publisher_master_authenticated"] is not False
            or supplement["complete384_line_meanings_accepted"] is not False
            or supplement["publisher_sample"]["sha256"] != SAMPLE_SHA256
            or supplement["publisher_sample"]["body_of_six_lines_available"]
            is not False
            or [r["key"] for r in supplement["rows"]] != binding["keys"]
        ):
            raise ValueError("Invalid v3 supplement identity or coverage")
        for i, row in enumerate(supplement["rows"]):
            original = data["rows"][12 + i]
            meaning = row["editorial_paraphrase"]
            (qualifier,) = row["source_qualifiers"]
            corroboration = row["heading_corroboration"]
            if (
                original["editorial_paraphrase"] is not None
                or row["source_pdf_page_one_based"]
                != original["source_pdf_page_one_based"]
                or row["source_layout_block_sha256"]
                != original["source_layout_block_sha256"]
                or row["source_line_heading"] != HEADINGS[i]
                or row["meaning_status"]
                != "local_editorial_paraphrase_pending_independent_review"
                or row["independent_semantic_review_completed"] is not False
                or row["complete_line_meaning_accepted"] is not False
                or set(meaning) != {"theme_zh", "exaltation", "detriment"}
                or any(type(v) is not str or not v for v in meaning.values())
                or row["source_conditions"] is not None
                or row["condition_review_status"]
                != "introductory_qualifier_locally_reviewed_not_exhaustive"
                or qualifier["source_role"] != "introductory_qualifier"
                or type(qualifier["editorial_summary_zh"]) is not str
                or not qualifier["editorial_summary_zh"]
                or qualifier["mechanical_predicate"] is not None
                or qualifier["personal_condition_satisfied"] is not None
                or qualifier["automatic_application"] is not False
                or qualifier["evaluation_status"]
                != "not_automated_nonmechanical_source_qualifier"
                or corroboration["sample_sha256"] != SAMPLE_SHA256
                or corroboration["sample_pdf_page_one_based"] != 2
                or corroboration["listed_body_page"] != [6, 7, 10, 11, 13, 14][i]
                or corroboration["literal_heading_matches"] is not True
                or corroboration["full_line_body_available_in_sample"] is not False
                or corroboration["full_line_semantics_corroborated"] is not False
            ):
                raise ValueError(
                    "V3 overwrite, invented applicability or unverified semantic claim"
                )
            original.update(deepcopy(row))
        data.update(
            version=3, catalogue_id=manifest["catalogue_id"], local_paraphrase_count=18
        )
        if base._coverage(data)["local_editorial_paraphrases"] != 18:
            raise ValueError("Invalid actual semantic coverage")
        provenance = base._provenance(parent, snapshot)
        snapshot.update({MANIFEST_PATH: raw, SUPPLEMENT_PATH: added})
        provenance.update(
            source_catalogue_version=3,
            source_catalogue_content_sha256=hashlib.sha256(
                base._canonical(data)
            ).hexdigest(),
            scope=base._scope(data),
        )
        provenance["source_records"].extend(
            [
                {
                    "domain": base.DOMAIN,
                    "key": path.stem,
                    "source_path": "human_design/" + path.name,
                    "loaded_file_sha256": hashlib.sha256(snapshot[path]).hexdigest(),
                    "source_kind": "versioned_local_gate3_editorial_reference",
                    "source_revision": 3,
                    "review_status": "six_additional_local_paraphrases_pending_independent_review",
                }
                for path in (MANIFEST_PATH, SUPPLEMENT_PATH)
            ]
        )
        provenance["source_records"].append(
            {
                "domain": base.DOMAIN,
                "key": "jovian_ra_1_6_sample_contents_only",
                "source_title": "The Third Gate - The Power of Mutation, RA1.6 public sample",
                "source_url": supplement["publisher_sample"]["url"],
                "source_pdf_sha256": SAMPLE_SHA256,
                "source_kind": "publisher_sample_contents_locally_checked_not_loaded_on_lookup",
                "review_status": "six_headings_only_not_full_line_bodies",
                "scope": "仅目录六条线名与2001副本相符；正文页不在四页样本内，不认证完整爻义或出版母版。",
            }
        )
        return data, snapshot, provenance
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        RecursionError,
        IndexError,
    ) as exc:
        raise EphemerisSourceError("human_design_reference_invalid") from exc


def _registry_category() -> tuple[dict, dict[Path, bytes]]:
    data, snapshot, provenance = _catalogue()
    result = {
        "name": CATEGORY,
        "count": 384,
        "keys_sample": [f"3.{i}" for i in range(1, 7)],
        "keys_complete": False,
        "key_format": "gate.line；显式v3参考，默认lines仍为v2",
        "supports": ["key"],
        "reference_only": True,
        "coverage": base._coverage(data),
        "provenance": provenance,
    }
    return result, snapshot


def registry_category() -> dict:
    result, snapshot = _registry_category()
    base._check_end(snapshot)
    return result


def read_reference(*, key: str | None) -> dict:
    with coherent_human_design_references():
        entry = base.read_reference(category="lines", key=key)
        data, snapshot, provenance = _catalogue()
        gate, line = map(int, entry["key"].split("."))
        row = deepcopy(data["rows"][(gate - 1) * 6 + line - 1])
        record = entry["reference_details"]["record"]
        record.update(row)
        meaning = record["editorial_paraphrase"]
        entry["category"] = CATEGORY
        entry["title"] = f"人类图{entry['key']}（v3）：" + (
            meaning["theme_zh"] if meaning else "极性索引／爻义待整理"
        )
        tips = [
            f"门线：{entry['key']}；源PDF第{record['source_pdf_page_one_based']}页。"
        ]
        if meaning:
            tips.extend(
                [
                    "上升极性局部转述：" + meaning["exaltation"],
                    "下降极性局部转述：" + meaning["detriment"],
                ]
            )
        else:
            tips.append("此线具体爻义尚未整理；不以角色通用线主题替代。")
        tips.extend(record["source_reading_notes"])
        for condition in record.get("source_conditions") or []:
            tips.append(condition["local_clause_paraphrase_zh"])
        if record.get("source_qualifiers"):
            tips.append(
                "引导语尚未转成可计算的个人条件，适用性未知；未列条件不表示无条件。"
            )
        tips.extend([record["selection_policy"], base._scope(data)])
        entry.update(
            tips=tips,
            lines=list(tips),
            rendered_text="\n".join([entry["title"], *tips]),
            provenance=provenance,
        )
        if gate == 3:
            entry[
                "citation"
            ] += "；六条线名另与Jovian Archive的RA1.6四页公开样本目录核对，仅核对线名。"
        base._check_end(snapshot)
        return entry
