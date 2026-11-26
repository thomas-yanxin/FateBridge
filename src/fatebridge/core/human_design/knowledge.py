"""Consolidated Human Design 384-line knowledge catalogue (Gates 1-64)."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from fatebridge.core.knowledge_store import ToolValidationError
from fatebridge.utils.errors import EphemerisSourceError

DOMAIN = "human_design"
SOURCE = "fatebridge_human_design_line_references"
POLICY_ID = "human_design_line_reference_v1"

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "human_design"
CATALOGUE_PATH = DATA_DIR / "line-knowledge-v1.json"
GATE_SUPPLEMENTS: tuple[tuple[int, str, Path], ...] = (
    (2, "human_design_gate2_editorial_v1", DATA_DIR / "line-knowledge-gate2-v1.json"),
    (3, "human_design_gate3_editorial_v1", DATA_DIR / "line-knowledge-gate3-v1.json"),
    (4, "human_design_gate4_editorial_v1", DATA_DIR / "line-knowledge-gate4-v1.json"),
    (5, "human_design_gate5_editorial_v1", DATA_DIR / "line-knowledge-gate5-v1.json"),
    (6, "human_design_gate6_editorial_v1", DATA_DIR / "line-knowledge-gate6-v1.json"),
)
CONTEXT_CLAUSES_PATH = DATA_DIR / "context-clauses-2001-v1.json"

KEY_RE = re.compile(r"([1-9]|[1-5][0-9]|6[0-4])\.([1-6])", flags=re.ASCII)


def _path_stamp(path: Path) -> tuple[str, int, int]:
    st = path.stat()
    return (str(path), st.st_mtime_ns, st.st_size)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate Human Design reference key")
        result[key] = value
    return result


def _reject_nonfinite(_value: str) -> None:
    raise ValueError("Nonfinite Human Design reference number")


def _load_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        path.read_bytes(),
        object_pairs_hook=_strict_object,
        parse_constant=_reject_nonfinite,
    )
    return data


@lru_cache(maxsize=4)
def _depth_data() -> dict[str, Any]:
    raw = (
        files("fatebridge.data")
        .joinpath("human_design")
        .joinpath("rave-2001-depth.json")
        .read_bytes()
    )
    data: dict[str, Any] = json.loads(
        raw, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite
    )
    return data


@lru_cache(maxsize=4)
def _additional_polarities() -> list[dict[str, Any]]:
    raw = (
        files("fatebridge.data")
        .joinpath("human_design")
        .joinpath("additional-polarities-2001.json")
        .read_bytes()
    )
    facts: list[dict[str, Any]] = json.loads(
        raw, object_pairs_hook=_strict_object, parse_constant=_reject_nonfinite
    )["facts"]
    return facts


def _coverage(rows: list[dict[str, Any]], full_accepted: bool) -> dict[str, Any]:
    curated = sum(row["editorial_paraphrase"] is not None for row in rows)
    return {
        "line_locators": len(rows),
        "local_editorial_paraphrases": curated,
        "meanings_pending": len(rows) - curated,
        "independently_accepted_line_meanings": sum(
            row["complete_line_meaning_accepted"] for row in rows
        ),
        "full_source_meanings_accepted": full_accepted,
    }


def _scope(counts: dict[str, Any]) -> str:
    return (
        f"来源参考，不选择个人适用极性。索引保留全部{counts['line_locators']}线；"
        f"{counts['local_editorial_paraphrases']}条为本地简短转述，{counts['meanings_pending']}条爻义待整理，"
        f"独立完整语义验收{counts['independently_accepted_line_meanings']}条。"
        "须核对同run实际gate/line、fixing_state及触发依据，不以角色通用线主题代替具体爻义。"
        "来源条件未穷尽核对，未记录不表示无条件。出版母本与完整384线未认证，现实效力未检验。"
    )


@lru_cache(maxsize=4)
def _load_consolidated_catalogue(
    _stamps: tuple[tuple[str, int, int], ...],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        base = _load_json(CATALOGUE_PATH)
        expected = [(gate, line) for gate in range(1, 65) for line in range(1, 7)]
        if (
            base["schema_version"] != 1
            or base["required_line_count"] != 384
            or [(r["gate"], r["line"]) for r in base["rows"]] != expected
            or [r["key"] for r in base["rows"]] != [f"{g}.{l}" for g, l in expected]
            or base["independently_accepted_line_count"] != 0
            or base["publisher_master_authenticated"] is not False
            or base["complete384_line_meanings_accepted"] is not False
        ):
            raise ValueError("Incomplete or falsely certified line catalogue")
        for row in base["rows"]:
            if (
                row["independent_semantic_review_completed"] is not False
                or row["complete_line_meaning_accepted"] is not False
                or row["source_pdf_page_one_based"] != 7 + 2 * (row["gate"] - 1)
            ):
                raise ValueError("Invalid source locator or review claim")
            if row["editorial_paraphrase"] is None:
                if row["meaning_status"] != "not_yet_curated":
                    raise ValueError("Unknown meaning silently promoted")
            else:
                meaning = row["editorial_paraphrase"]
                if (
                    row["meaning_status"]
                    != "local_editorial_paraphrase_pending_independent_review"
                    or set(meaning) != {"theme_zh", "exaltation", "detriment"}
                    or any(type(v) is not str or not v for v in meaning.values())
                ):
                    raise ValueError("Invalid editorial paraphrase")

        source_records: list[dict[str, Any]] = [
            {
                "domain": DOMAIN,
                "key": "rave2001_line_locators_and_editorial_v1",
                "source_path": f"human_design/{CATALOGUE_PATH.name}",
                "source_kind": "fixed_public_copy_locators_and_local_editorial_paraphrases",
                "source_title": base["source"]["title"],
                "source_revision": 1,
                "review_status": "local_paraphrases_pending_independent_review",
            }
        ]

        # Merge Gate 2-6 supplements into the single canonical `lines` catalogue.
        for gate, expected_id, sup_path in GATE_SUPPLEMENTS:
            sup = _load_json(sup_path)
            if (
                sup["schema_version"] != 1
                or sup.get("independently_accepted_line_count") != 0
                or sup.get("publisher_master_authenticated") is not False
                or sup.get("complete384_line_meanings_accepted") is not False
                or [r["key"] for r in sup["rows"]]
                != [f"{gate}.{l}" for l in range(1, 7)]
            ):
                raise ValueError(f"Invalid supplement {sup_path.name}")
            if "supplement_id" in sup and sup["supplement_id"] != expected_id:
                raise ValueError(f"Unexpected supplement_id in {sup_path.name}")
            for line_idx, sup_row in enumerate(sup["rows"]):
                target_row = base["rows"][(gate - 1) * 6 + line_idx]
                meaning = sup_row["editorial_paraphrase"]
                if (
                    target_row["editorial_paraphrase"] is not None
                    or sup_row["source_pdf_page_one_based"]
                    != target_row["source_pdf_page_one_based"]
                    or sup_row["independent_semantic_review_completed"] is not False
                    or sup_row["complete_line_meaning_accepted"] is not False
                    or sup_row["meaning_status"]
                    != "local_editorial_paraphrase_pending_independent_review"
                    or set(meaning) != {"theme_zh", "exaltation", "detriment"}
                ):
                    raise ValueError(f"Supplement conflict at {sup_row['key']}")
                for cond in sup_row.get("source_conditions") or []:
                    if (
                        cond.get("personal_condition_satisfied") is not None
                        or cond.get("automatic_application") is not False
                    ):
                        raise ValueError("Source condition silently applied")
                for qual in sup_row.get("source_qualifiers") or []:
                    if (
                        qual.get("personal_condition_satisfied") is not None
                        or qual.get("automatic_application") is not False
                    ):
                        raise ValueError("Source qualifier silently applied")
                target_row.update(sup_row)
            source_records.append(
                {
                    "domain": DOMAIN,
                    "key": sup_path.stem,
                    "source_path": f"human_design/{sup_path.name}",
                    "source_kind": f"local_gate{gate}_editorial_reference",
                    "review_status": "six_local_paraphrases_pending_independent_review",
                }
            )

        # Merge structural context clauses (2.3, 6.3, 7.2, 12.6, 42.1).
        clauses = _load_json(CONTEXT_CLAUSES_PATH)
        if (
            clauses["schema_version"] != 1
            or clauses["independently_accepted_line_count"] != 0
            or clauses["complete384_line_meanings_accepted"] is not False
        ):
            raise ValueError("Invalid context clauses catalogue")
        clauses_by_key = {a["key"]: a for a in clauses["annotations"]}
        for row in base["rows"]:
            annotation = clauses_by_key.get(row["key"])
            if annotation is None:
                row["source_context_annotations"] = None
            else:
                if (
                    annotation["source_pdf_page_one_based"]
                    != row["source_pdf_page_one_based"]
                    or annotation["personal_condition_satisfied"] is not None
                    or annotation["automatic_application"] is not False
                    or annotation["complete_line_meaning_accepted"] is not False
                    or annotation["independent_semantic_review_completed"] is not False
                ):
                    raise ValueError("Invalid context annotation")
                row["source_context_annotations"] = [annotation]
        source_records.extend(
            [
                {
                    "domain": DOMAIN,
                    "key": CONTEXT_CLAUSES_PATH.stem,
                    "source_path": f"human_design/{CONTEXT_CLAUSES_PATH.name}",
                    "source_kind": "bounded_local_source_context_annotations",
                    "review_status": "five_local_clause_annotations_not_full_line_acceptance",
                },
                {
                    "domain": DOMAIN,
                    "key": "rave2001_original_polarity_facts",
                    "source_path": "human_design/rave-2001-depth.json",
                    "source_kind": "existing_frozen_polarity_catalogue",
                    "review_status": "inherited_factual_reference",
                },
                {
                    "domain": DOMAIN,
                    "key": "rave2001_additional_planet_facts",
                    "source_path": "human_design/additional-polarities-2001.json",
                    "source_kind": "existing_two_explicit_additional_planets",
                    "review_status": "bounded_source_clause_facts",
                },
            ]
        )

        coverage = _coverage(base["rows"], base["complete384_line_meanings_accepted"])
        provenance = {
            "source_domain": SOURCE,
            "domain": DOMAIN,
            "reference_policy_id": POLICY_ID,
            "source_catalogue_version": 7,
            "reference_only": True,
            "personal_applicability_assessed": False,
            "whole_books_collated": False,
            "independent_whole_corpus_review_completed": False,
            "real_world_efficacy_validated": False,
            "scope": _scope(coverage),
            "source_records": source_records,
        }
        return base, coverage, provenance
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        RecursionError,
        IndexError,
    ) as exc:
        raise EphemerisSourceError("human_design_reference_invalid") from exc


def _catalogue() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        stamps = (
            _path_stamp(CATALOGUE_PATH),
            *(_path_stamp(p) for _, _, p in GATE_SUPPLEMENTS),
            _path_stamp(CONTEXT_CLAUSES_PATH),
        )
    except OSError as exc:
        raise EphemerisSourceError("human_design_reference_invalid") from exc
    return _load_consolidated_catalogue(stamps)


def build_registry() -> dict[str, Any]:
    """Return the single consolidated Human Design `lines` category without deepcopy."""
    data, coverage, provenance = _catalogue()
    category = {
        "name": "lines",
        "count": len(data["rows"]),
        "keys_sample": [r["key"] for r in data["rows"][:12]],
        "keys_complete": False,
        "key_format": "gate.line；门1..64，线1..6；例如1.1",
        "supports": ["key"],
        "reference_only": True,
        "coverage": dict(coverage),
    }
    return {
        "source": SOURCE,
        "bundle_version": None,
        "provenance": provenance,
        "domains": [
            {
                "domain": DOMAIN,
                "source": SOURCE,
                "bundle_version": None,
                "provenance": provenance,
                "categories": [category],
            }
        ],
    }


def read_reference(*, category: str | None, key: str | None) -> dict[str, Any]:
    if category not in (None, "lines"):
        raise ToolValidationError(
            "人类图参考分类须为 lines",
            code="knowledge.human_design.unknown_category",
            details={"category": category},
        )
    if not isinstance(key, str) or not KEY_RE.fullmatch(key.strip()):
        raise ToolValidationError(
            "人类图参考键须为门.线，门1至64、线1至6",
            code="knowledge.human_design.unknown_key",
            details={"key": key},
        )
    normalized = key.strip()
    gate, line = map(int, normalized.split("."))
    data, coverage, provenance = _catalogue()
    locator = deepcopy(data["rows"][(gate - 1) * 6 + line - 1])
    entry = _depth_data()["gates"][gate - 1]
    glyphs = dict(entry["line_polarities"][line - 1])
    extras = [
        dict(r)
        for r in _additional_polarities()
        if (r["gate"], r["line"]) == (gate, line)
    ]
    planets = {
        role: (
            [glyphs[role + "_planet"]] if glyphs[role + "_planet"] is not None else []
        )
        + [r["additional_planet"] for r in extras if r["role"] == role]
        for role in ("exaltation", "detriment")
    }
    available = [role for role in ("exaltation", "detriment") if planets[role]]
    selection_policy = (
        "先读同run实际门线与fixing_state。固定只强调相应极性，不排除另一极性；"
        "两极同时触发则并列，未固定保留原文已有可能。不代选，不据参考重新推算个人固定状态。"
    )
    record: dict[str, Any] = {
        **locator,
        "gate_name": entry["name"],
        "catalogue_glyph_polarity": glyphs,
        "source_polarity_planets": planets,
        "source_available_polarities": available,
        "additional_polarity_facts": extras,
        "actual_fixing_state": None,
        "selected_polarity": None,
        "personal_applicability_assessed": False,
        "condition_review_status": locator.get(
            "condition_review_status", "not_assessed"
        ),
        "source_conditions": locator.get("source_conditions"),
        "selection_policy": selection_policy,
        "fixing_reading_rule_source": {
            "author": "Lynda Bunnell",
            "published_by": "IHDS blog / Ruth Brennan",
            "published_on": "2024-06-12",
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
        for role, label in (("exaltation", "上升"), ("detriment", "下降")):
            if meaning.get(role) is not None:
                tips.append(f"{label}极性简述：{meaning[role]}")
        tips.append("本地转述尚待独立复核；不能称作完整线义验收。")
    else:
        tips.append(
            "本条尚无已整理爻义；不以角色第几线的一般主题代替此门此线的具体原意。"
        )
    tips.extend(record.get("source_reading_notes") or [])
    for condition in record.get("source_conditions") or []:
        tips.extend(
            [
                condition["local_clause_paraphrase_zh"],
                "本查询未核验该个人条件；须结合同run实际固定状态与永久通道证据，不自动应用。",
            ]
        )
    for annotation in record.get("source_context_annotations") or []:
        tips.append(annotation["editorial_summary_zh"])
    if record.get("source_qualifiers"):
        tips.append("引导语尚未转成可计算的个人条件；未列条件不表示无条件。")
    tips.extend([selection_policy, _scope(coverage)])
    return {
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
        "citation": (
            f"Ra Uru Hu, The Complete Rave I'Ching, 2001公开副本，PDF第"
            f"{record['source_pdf_page_one_based']}页。固定取用规则另据Lynda Bunnell 2024署名说明。"
        ),
        "provenance": dict(provenance),
        "reference_only": True,
        "reference_details": {
            "policy_id": POLICY_ID,
            "reference_only": True,
            "personal_applicability_assessed": False,
            "record": record,
        },
    }
