"""Opt-in Gate4 editorial drafts; all previous reference versions stay pinned."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from fatebridge.core import human_design_knowledge_v4 as parent
from fatebridge.core import human_design_line_catalogue as base
from fatebridge.core.human_design_references import coherent_human_design_references
from fatebridge.utils.errors import EphemerisSourceError

CATEGORY = "lines_v5"
CATALOGUE_PATH = base.CATALOGUE_PATH.with_name("line-knowledge-gate4-v1.json")
CATALOGUE_SHA256 = "2893e860a30de29b6b5438d8c60398424d916fb277e2aae8cd5be2f4b4f2b269"
HEADINGS = [
    "Pleasure",
    "Acceptance",
    "Irresponsibility",
    "The liar",
    "Seduction",
    "Excess",
]
SCOPE = (
    "第4门六条新增局部转述待独立复核；未取得出版方逐爻正文旁证，不增加完整语义验收。"
)


def _catalogue() -> tuple[dict, dict[Path, bytes], dict]:
    data, snapshot, provenance = parent._catalogue()
    base._check_end(snapshot)
    try:
        raw = CATALOGUE_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != CATALOGUE_SHA256:
            raise ValueError("Gate4 editorial catalogue changed")
        supplement = json.loads(
            raw, object_pairs_hook=base._object, parse_constant=base._nonfinite
        )
        if (
            supplement["schema_version"] != 1
            or supplement["version"] != 5
            or supplement["catalogue_id"] != "human_design_gate4_editorial_v5"
            or supplement["parent_version"] != data["version"]
            or supplement["parent_catalogue_sha256"] != parent.CATALOGUE_SHA256
            or supplement["source_pdf_sha256"] != data["source"]["pdf_sha256"]
            or supplement["required_line_count"] != 384
            or supplement["expected_local_paraphrase_count"] != 24
            or supplement["independently_accepted_line_count"] != 0
            or supplement["publisher_master_authenticated"] is not False
            or supplement["complete384_line_meanings_accepted"] is not False
            or supplement["source_conditions_exhaustively_reviewed"] is not False
            or supplement["publisher_direct_body_corroboration_available"] is not False
            or [r["key"] for r in supplement["rows"]]
            != [f"4.{line}" for line in range(1, 7)]
        ):
            raise ValueError("Invalid Gate4 coverage or source claim")
        for i, row in enumerate(supplement["rows"]):
            original = data["rows"][18 + i]
            meaning = row["editorial_paraphrase"]
            (qualifier,) = row["source_qualifiers"]
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
            ):
                raise ValueError("Invalid Gate4 locator or invented applicability")
            original.update(deepcopy(row))
        data.update(
            version=5,
            catalogue_id=supplement["catalogue_id"],
            local_paraphrase_count=24,
        )
        if base._coverage(data)["local_editorial_paraphrases"] != 24:
            raise ValueError("Invalid actual Gate4 semantic coverage")
        base._check_end(snapshot)
        snapshot[CATALOGUE_PATH] = raw
        provenance.update(
            source_catalogue_version=5,
            source_catalogue_content_sha256=hashlib.sha256(
                base._canonical(data)
            ).hexdigest(),
            scope=base._scope(data) + parent.SCOPE + SCOPE,
        )
        provenance["source_records"].append(
            {
                "domain": base.DOMAIN,
                "key": CATALOGUE_PATH.stem,
                "source_path": "human_design/" + CATALOGUE_PATH.name,
                "loaded_file_sha256": CATALOGUE_SHA256,
                "source_pdf_sha256": supplement["source_pdf_sha256"],
                "source_kind": "versioned_local_gate4_editorial_reference",
                "source_revision": 5,
                "review_status": "six_additional_local_paraphrases_pending_independent_review",
                "scope": SCOPE,
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
    return {
        "name": CATEGORY,
        "count": 384,
        "keys_sample": [f"4.{line}" for line in range(1, 7)],
        "keys_complete": False,
        "key_format": "gate.line；显式v5增加第4门局部转述，默认lines仍为v2",
        "supports": ["key"],
        "reference_only": True,
        "coverage": base._coverage(data),
        "provenance": provenance,
    }, snapshot


def read_reference(*, key: str | None) -> dict:
    with coherent_human_design_references():
        entry = parent.read_reference(key=key)
        data, snapshot, provenance = _catalogue()
        gate, line = map(int, entry["key"].split("."))
        record = entry["reference_details"]["record"]
        record.update(deepcopy(data["rows"][(gate - 1) * 6 + line - 1]))
        meaning = record["editorial_paraphrase"]
        entry["category"] = CATEGORY
        entry["title"] = f"人类图{entry['key']}（v5）：" + (
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
        for annotation in record["source_context_annotations"] or []:
            tips.append(annotation["editorial_summary_zh"])
        if record.get("source_qualifiers"):
            tips.append(
                "引导语尚未转成可计算的个人条件，适用性未知；未列条件不表示无条件。"
            )
        tips.extend(
            [record["selection_policy"], base._scope(data), parent.SCOPE, SCOPE]
        )
        entry.update(
            tips=tips,
            lines=list(tips),
            rendered_text="\n".join([entry["title"], *tips]),
            provenance=provenance,
        )
        base._check_end(snapshot)
        return entry
