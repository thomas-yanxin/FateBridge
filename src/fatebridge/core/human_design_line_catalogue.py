"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.human_design_additional_polarities import facts_for
from fatebridge.core.human_design_depth import depth_reference
from fatebridge.core.human_design_references import (
    coherent_human_design_references,
    reference_sha256,
)
from fatebridge.core.knowledge_store import ToolValidationError
from fatebridge.utils.errors import EphemerisSourceError

DOMAIN = "human_design"


SOURCE = "fatebridge_human_design_line_references"


POLICY_ID = "human_design_line_reference_v1"


FIXING_READING_SOURCE = "https://ihumandesignschool.com/how-to-use-the-rave-iching/"


CATALOGUE_PATH = (
    Path(__file__).resolve().parents[1] / "data/human_design/line-knowledge-v1.json"
)


CATALOGUE_SHA256 = "e0be8121e433f1513fdd45ac560acd4c7519f67cf12d11bd86b966b0e011430e"


MANIFEST_PATH = CATALOGUE_PATH.with_name("line-knowledge-manifest-v2.json")


MANIFEST_SHA256 = "c33d3b6099e96b66c0e2dbe898dc97e5a5a8ab125a1c64596863c63f31440d79"


SUPPLEMENT_PATH = CATALOGUE_PATH.with_name("line-knowledge-gate2-v1.json")


KEY = re.compile(r"([1-9]|[1-5][0-9]|6[0-4])\.([1-6])", flags=re.ASCII)


def _coverage(data: dict) -> dict:
    rows = data["rows"]
    curated = sum(r["editorial_paraphrase"] is not None for r in rows)
    return {
        "line_locators": len(rows),
        "local_editorial_paraphrases": curated,
        "meanings_pending": len(rows) - curated,
        "independently_accepted_line_meanings": sum(
            r["complete_line_meaning_accepted"] for r in rows
        ),
        "full_source_meanings_accepted": data["complete384_line_meanings_accepted"],
    }


def _scope(data: dict) -> str:
    counts = _coverage(data)
    return (
        f"来源参考，不选择个人适用极性。索引保留全部{counts['line_locators']}线；"
        f"{counts['local_editorial_paraphrases']}条为本地简短转述，{counts['meanings_pending']}条爻义待整理，"
        f"独立完整语义验收{counts['independently_accepted_line_meanings']}条。"
        "须核对同run实际gate/line、fixing_state及触发依据，不以角色通用线主题代替具体爻义。"
        "来源条件未穷尽核对，未记录不表示无条件。出版母本与完整384线未认证，现实效力未检验。"
    )


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate Human Design reference key")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError("Nonfinite Human Design reference number")


def _base_catalogue() -> tuple[dict, bytes]:
    try:
        raw = CATALOGUE_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != CATALOGUE_SHA256:
            raise ValueError("Human Design editorial reference identity changed")
        data = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
        expected = [(gate, line) for gate in range(1, 65) for line in range(1, 7)]
        if (
            data["schema_version"] != 1
            or data["version"] != 1
            or data["required_line_count"] != 384
            or data["source"]["pdf_sha256"] != depth_reference()["source"]["pdf_sha256"]
            or data["source_factual_catalogue_sha256"]
            != reference_sha256("rave-2001-depth.json")
            or [(r["gate"], r["line"]) for r in data["rows"]] != expected
            or [r["key"] for r in data["rows"]]
            != [f"{g}.{line}" for g, line in expected]
            or data["local_paraphrase_count"] != 6
            or data["independently_accepted_line_count"] != 0
            or data["publisher_master_authenticated"] is not False
            or data["complete384_line_meanings_accepted"] is not False
        ):
            raise ValueError("Incomplete or falsely certified line catalogue")
        curated = []
        for row in data["rows"]:
            if (
                row["independent_semantic_review_completed"] is not False
                or row["complete_line_meaning_accepted"] is not False
                or not re.fullmatch(r"[0-9a-f]{64}", row["source_layout_block_sha256"])
                or row["source_pdf_page_one_based"] != 7 + 2 * (row["gate"] - 1)
            ):
                raise ValueError("Invalid source locator or review claim")
            if row["editorial_paraphrase"] is None:
                if row["meaning_status"] != "not_yet_curated":
                    raise ValueError("Unknown meaning silently promoted")
            else:
                meanings = row["editorial_paraphrase"]
                if (
                    row["meaning_status"]
                    != "local_editorial_paraphrase_pending_independent_review"
                    or set(meanings) != {"theme_zh", "exaltation", "detriment"}
                    or any(type(v) is not str or not v for v in meanings.values())
                ):
                    raise ValueError("Invalid editorial paraphrase")
                curated.append(row["key"])
        if curated != [f"1.{line}" for line in range(1, 7)]:
            raise ValueError("Unreviewed semantic coverage changed")
        return data, raw
    except (OSError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise EphemerisSourceError("human_design_reference_invalid") from exc


def _catalogue() -> tuple[dict, dict[Path, bytes]]:
    data, base_raw = _base_catalogue()
    try:
        raw = MANIFEST_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            raise ValueError("Composite reference revision changed")
        manifest = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
        snapshot = {CATALOGUE_PATH: base_raw, MANIFEST_PATH: raw}
        if (
            manifest["schema_version"] != 1
            or manifest["version"] != 2
            or manifest["catalogue_id"] != "human_design_line_knowledge_v2"
            or manifest["base"]
            != {"file": "line-knowledge-v1.json", "sha256": CATALOGUE_SHA256}
            or manifest["required_line_count"] != len(data["rows"])
            or manifest["independently_accepted_line_count"] != 0
            or manifest["publisher_master_authenticated"] is not False
            or manifest["complete384_line_meanings_accepted"] is not False
            or len(manifest["supplements"]) != 1
        ):
            raise ValueError("Invalid composite identity or certification")
        binding = manifest["supplements"][0]
        if binding["file"] != "line-knowledge-gate2-v1.json":
            raise ValueError("Undeclared supplement path")
        supplement_raw = SUPPLEMENT_PATH.read_bytes()
        if hashlib.sha256(supplement_raw).hexdigest() != binding["sha256"]:
            raise ValueError("Supplement identity changed")
        snapshot[SUPPLEMENT_PATH] = supplement_raw
        supplement = json.loads(
            supplement_raw, object_pairs_hook=_object, parse_constant=_nonfinite
        )
        if (
            supplement["schema_version"] != 1
            or supplement["supplement_id"] != "human_design_gate2_editorial_v1"
            or supplement["base_catalogue_sha256"] != CATALOGUE_SHA256
            or supplement["source_pdf_sha256"] != data["source"]["pdf_sha256"]
            or supplement["independently_accepted_line_count"] != 0
            or supplement["publisher_master_authenticated"] is not False
            or supplement["complete384_line_meanings_accepted"] is not False
            or [r["key"] for r in supplement["rows"]] != binding["keys"]
            or binding["keys"] != [f"2.{line}" for line in range(1, 7)]
        ):
            raise ValueError("Invalid supplementary coverage or certification")
        for row in supplement["rows"]:
            gate, line = map(int, row["key"].split("."))
            original = data["rows"][(gate - 1) * 6 + line - 1]
            meanings = row["editorial_paraphrase"]
            if (
                original["editorial_paraphrase"] is not None
                or row["source_pdf_page_one_based"]
                != original["source_pdf_page_one_based"]
                or row["source_layout_block_sha256"]
                != original["source_layout_block_sha256"]
                or row["independent_semantic_review_completed"] is not False
                or row["complete_line_meaning_accepted"] is not False
                or row["meaning_status"]
                != "local_editorial_paraphrase_pending_independent_review"
                or set(meanings) != {"theme_zh", "exaltation", "detriment"}
                or any(type(v) is not str or not v for v in meanings.values())
            ):
                raise ValueError(
                    "Supplement overwrites or falsely certifies a source row"
                )
            if row["key"] == "2.3":
                conditions = row["source_conditions"]
                if (
                    len(conditions) != 1
                    or conditions[0]["personal_condition_satisfied"] is not None
                    or conditions[0]["automatic_application"] is not False
                ):
                    raise ValueError("Source condition silently applied to a person")
            original.update(deepcopy(row))
        data["version"] = manifest["version"]
        data["catalogue_id"] = manifest["catalogue_id"]
        data["local_paraphrase_count"] = _coverage(data)["local_editorial_paraphrases"]
        if (
            data["local_paraphrase_count"]
            != manifest["expected_local_paraphrase_count"]
        ):
            raise ValueError("Declared coverage differs from actual records")
        return data, snapshot
    except (OSError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise EphemerisSourceError("human_design_reference_invalid") from exc


def _provenance(data: dict, snapshot: dict[Path, bytes]) -> dict:
    return {
        "source_domain": SOURCE,
        "domain": DOMAIN,
        "reference_policy_id": POLICY_ID,
        "source_catalogue_version": data["version"],
        "source_catalogue_content_sha256": hashlib.sha256(_canonical(data)).hexdigest(),
        "reference_only": True,
        "personal_applicability_assessed": False,
        "whole_books_collated": False,
        "independent_whole_corpus_review_completed": False,
        "real_world_efficacy_validated": False,
        "scope": _scope(data),
        "source_records": [
            {
                "domain": DOMAIN,
                "key": "rave2001_line_locators_and_editorial_v1",
                "source_path": "human_design/line-knowledge-v1.json",
                "loaded_file_sha256": hashlib.sha256(
                    snapshot[CATALOGUE_PATH]
                ).hexdigest(),
                "source_kind": "fixed_public_copy_locators_and_local_editorial_paraphrases",
                "source_title": data["source"]["title"],
                "source_url": data["source"]["url"],
                "source_pdf_sha256": data["source"]["pdf_sha256"],
                "source_revision": 1,
                "review_status": "six_local_paraphrases_pending_independent_review",
                "scope": "384线块定位完整；极性星体继承已绑定的事实目录，不把384条定位认作384条完整语义审校。",
            },
            *[
                {
                    "domain": DOMAIN,
                    "key": path.stem,
                    "source_path": f"human_design/{path.name}",
                    "loaded_file_sha256": hashlib.sha256(snapshot[path]).hexdigest(),
                    "source_kind": kind,
                    "review_status": "local_editorial_reference_pending_independent_review",
                }
                for path, kind in [
                    (MANIFEST_PATH, "composite_catalogue_manifest"),
                    (
                        SUPPLEMENT_PATH,
                        "six_gate2_local_paraphrases_with_one_explicit_source_condition",
                    ),
                ]
            ],
            {
                "domain": DOMAIN,
                "key": "rave2001_original_polarity_facts",
                "source_path": "human_design/rave-2001-depth.json",
                "loaded_file_sha256": reference_sha256("rave-2001-depth.json"),
                "source_kind": "existing_frozen_polarity_catalogue",
                "review_status": "inherited_factual_reference_not_new_full_visual_collation",
            },
            {
                "domain": DOMAIN,
                "key": "rave2001_additional_planet_facts",
                "source_path": "human_design/additional-polarities-2001.json",
                "loaded_file_sha256": reference_sha256(
                    "additional-polarities-2001.json"
                ),
                "source_kind": "existing_two_explicit_additional_planets",
                "review_status": "bounded_source_clause_facts",
            },
        ],
    }


def _check_end(snapshot: dict[Path, bytes]) -> None:
    try:
        if any(path.read_bytes() != raw for path, raw in snapshot.items()):
            raise ValueError("Source component changed during lookup")
    except (OSError, ValueError) as exc:
        raise EphemerisSourceError("human_design_reference_changed") from exc


def read_reference(*, category: str | None, key: str | None) -> dict:
    if category not in (None, "lines"):
        raise ToolValidationError(
            "人类图参考分类须为lines、lines_v3、lines_v4、lines_v5、lines_v6或lines_v7",
            code="knowledge.human_design.unknown_category",
            details={"category": category},
        )
    if not isinstance(key, str) or not KEY.fullmatch(key.strip()):
        raise ToolValidationError(
            "人类图参考键须为门.线，门1至64、线1至6",
            code="knowledge.human_design.unknown_key",
            details={"key": key},
        )
    normalized = key.strip()
    gate, line = map(int, normalized.split("."))
    with coherent_human_design_references():
        data, raw = _catalogue()
        locator = deepcopy(data["rows"][(gate - 1) * 6 + line - 1])
        entry = depth_reference()["gates"][gate - 1]
        glyphs = deepcopy(entry["line_polarities"][line - 1])
        extras = facts_for(gate, line)
        planets = {
            role: (
                [glyphs[role + "_planet"]]
                if glyphs[role + "_planet"] is not None
                else []
            )
            + [r["additional_planet"] for r in extras if r["role"] == role]
            for role in ("exaltation", "detriment")
        }
        record = {
            **locator,
            "gate_name": entry["name"],
            "catalogue_glyph_polarity": glyphs,
            "source_polarity_planets": planets,
            "additional_polarity_facts": extras,
            "actual_fixing_state": None,
            "selected_polarity": None,
            "personal_applicability_assessed": False,
            "condition_review_status": locator.get(
                "condition_review_status", "not_assessed"
            ),
            "source_conditions": locator.get("source_conditions"),
            "selection_policy": "先读同run实际门线与fixing_state。固定只强调相应极性，不排除另一极性；两极同时触发则并列，未固定保留原文已有可能。不代选，不据参考重新推算个人固定状态。",
            "fixing_reading_rule_source": {
                "author": "Lynda Bunnell",
                "published_by": "IHDS blog / Ruth Brennan",
                "published_on": "2024-06-12",
                "url": FIXING_READING_SOURCE,
                "scope": "固定为极性侧重，不是另一极性永不发生；只支持此解释规则，不认证完整线义。",
            },
        }
        meaning = record["editorial_paraphrase"]
        title = f"人类图{normalized}：" + (
            meaning["theme_zh"] if meaning else "极性索引／爻义待整理"
        )
        tips = [
            f"门线：{normalized}；源PDF第{record['source_pdf_page_one_based']}页。",
            "原典极性星体（含明文附加星体）："
            + "；".join(f"{r}={','.join(v) or '未列'}" for r, v in planets.items()),
        ]
        if meaning:
            tips.extend(
                [
                    "上升极性简述：" + meaning["exaltation"],
                    "下降极性简述：" + meaning["detriment"],
                    "本地转述尚待独立复核；不能称作完整线义验收。",
                ]
            )
        else:
            tips.append(
                "本条尚无已整理爻义；不以角色第几线的一般主题代替此门此线的具体原意。"
            )
        tips.extend(record["source_reading_notes"])
        for condition in record["source_conditions"] or []:
            tips.extend(
                [
                    condition["local_clause_paraphrase_zh"],
                    "本查询未核验该个人条件；须结合同run实际固定状态与永久通道证据，不自动应用。",
                ]
            )
        tips.extend(
            [
                record["selection_policy"],
                "这不是本次个人固定状态或现实事件预测。",
                _scope(data),
            ]
        )
        result = {
            "domain": DOMAIN,
            "category": "lines",
            "key": normalized,
            "query_normalized": {"key": normalized},
            "title": title,
            "tips": tips,
            "lines": list(tips),
            "rendered_text": "\n".join([title, *tips]),
            "source": SOURCE,
            "bundle_version": None,
            "citation": f"Ra Uru Hu, The Complete Rave I'Ching, 2001公开副本，PDF第{record['source_pdf_page_one_based']}页；{data['source']['url']}。固定取用规则另据Lynda Bunnell2024署名说明：{FIXING_READING_SOURCE}",
            "provenance": _provenance(data, raw),
            "reference_only": True,
            "reference_details": {
                "policy_id": POLICY_ID,
                "reference_only": True,
                "personal_applicability_assessed": False,
                "record": record,
            },
        }
        _check_end(raw)
        return result
