"""Source-bound reference access, without selecting a person's applicable rule."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, NoReturn

from fatebridge.core.knowledge_store import ToolValidationError
from fatebridge.utils.errors import NumerologySourceError

DOMAINS = ("heluo", "canping")
DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
CATALOGUE_PATH = DATA_ROOT / "knowledge/numerology-sources-v1.json"
CATALOGUE_CONTENT_SHA256 = (
    "84ee5417cd1f5dd2e085b33a8f2ac8b615ff605ad44d7d82088f24ccb98d1d12"
)
SOURCE = "fatebridge_numerology_references"
POLICY_ID = "numerology_source_reference_v1"
SCOPE = (
    "此处提供具名来源与已存局部读稿，不选择个人适用条款。"
    "本次实际取法、栏目及条款角色仍须核对同run计算回执；"
    "继承文本、疑读与待核关系保留，不能据目录授予全书或现实预测认证。"
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _heluo_reference_notes(record: dict[str, Any]) -> list[str]:
    """Carry the existing record's qualifications into summary-only reads."""
    status = record["text_provenance"]
    notes: list[str] = []
    for field, notes_field, label in [
        ("review_status", "header_reading_notes", "爻辞"),
        ("commentary_review_status", "commentary_reading_notes", "注文"),
    ]:
        review = status.get(field, "")
        # Unresolved readings are already rendered with their notes by the
        # existing glyph warning. Other editorial qualifications matter too.
        if "unresolved" not in review:
            notes.extend(f"{label}读文说明：{n}" for n in status.get(notes_field, []))
        if "independent_second_review_pending" in review:
            notes.append(f"{label}的独立复核尚未完成。")
    branch = record.get("commentary_branch_selection")
    if branch:
        notes.append(f"注文取用说明：{branch['reason']}")
    selection = record.get("poem_selection")
    if selection:
        notes.append(f"爻诗取用说明：{selection['reason']}")
        for poem in record.get("poem_sections", []):
            notes.extend(
                f"第{poem['index']}首读文说明：{n}"
                for n in poem.get("reading_notes", [])
            )
        if "independent_second_review_pending" in status.get("poem_review_status", ""):
            notes.append("爻诗的独立复核尚未完成。")
    supplement = record.get("poem_review_supplement")
    if supplement:
        notes.append("后续五首复核范围：" + supplement["scope_note"])
        for entry in supplement["entries"]:
            notes.extend(
                f"第{entry['poem_index']}首后续复核：{note}"
                for note in entry["review_notes"]
            )
    xiang = record.get("inherited_xiang_reference", {})
    if "unverified" in xiang.get("status", ""):
        notes.append("继承象辞的特定来源仍待核；本诗卷目校不将其转为已核原文。")
    for reference in record.get("commentary_cross_references", []):
        parts = [
            f"引卦原句：{reference['source_quote']}",
            f"原条件：{reference['condition_text']}",
            f"所引卦：{reference['target_hexagram']}",
        ]
        if reference.get("target_quote"):
            parts.append(f"所引文字：{reference['target_quote']}")
        if reference.get("source_condition_label"):
            parts.append(f"所属条件段：{reference['source_condition_label']}")
        if reference.get("source_context_text"):
            parts.append(f"原段上下文：{reference['source_context_text']}")
        if reference.get("target_line_source_status") == "not_printed":
            parts.append("原文未印目标爻位，不把结构对照补作原印爻位")
        if reference.get("applicability") is None:
            parts.append("引用条件的适用性未裁定")
        if reference.get("automatic_application") is False:
            parts.append("不自动应用")
        if reference.get("replaces_chart") is False:
            parts.append("不替代正式卦盘")
        parts.append("本条引文不单独证明目标卦全文")
        notes.append("有条件引文说明：" + "；".join(parts) + "。")
    return notes


def _catalogue() -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(CATALOGUE_PATH.read_bytes())
        if sha256(canonical_bytes(data)).hexdigest() != CATALOGUE_CONTENT_SHA256:
            raise ValueError("Reference catalogue identity changed")
        return data
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_numerology_knowledge_sources") from exc


def _source(domain: str, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        entries = [
            e
            for e in _catalogue()["sources"]
            if e["domain"] == domain and e["key"] == key
        ]
        if len(entries) != 1:
            raise ValueError("Unknown registered source")
        entry = entries[0]
        path = DATA_ROOT / entry["source_path"]
        raw = path.read_bytes()
        data = json.loads(raw)
        digest = sha256(canonical_bytes(data)).hexdigest()
        if digest != entry["canonical_content_sha256"]:
            raise ValueError(
                "Source words or identity differ from reviewed reference revision"
            )
        meta = {
            **deepcopy(entry),
            "loaded_file_sha256": sha256(raw).hexdigest(),
            "source_title": data.get("source_title"),
            "source_url": data.get("source_url"),
            "source_pdf_sha256": data.get("source_pdf_sha256"),
            "source_revision": data.get("version"),
            "review_status": data.get(
                "review_status", "inherited_transcription_unverified"
            ),
            "scope": data.get("scope"),
        }
        if "sources" in data:
            meta["source_witnesses"] = deepcopy(data["sources"])
        return data, meta
    except NumerologySourceError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_numerology_knowledge_sources") from exc


def _snapshots(
    domain: str, keys: list[str] | None = None
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    available = [e["key"] for e in _catalogue()["sources"] if e["domain"] == domain]
    return {key: _source(domain, key) for key in (available if keys is None else keys)}


def _provenance(
    domain: str,
    snapshots: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    *,
    category: str | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    return {
        "source_domain": SOURCE,
        "domain": domain,
        "category": category,
        "key": key,
        "reference_policy_id": POLICY_ID,
        "source_catalogue_version": _catalogue()["version"],
        "source_catalogue_content_sha256": CATALOGUE_CONTENT_SHA256,
        "source_records": [deepcopy(meta) for _, meta in snapshots.values()],
        "reference_only": True,
        "personal_applicability_assessed": False,
        "whole_books_collated": False,
        "independent_whole_corpus_review_completed": False,
        "real_world_efficacy_validated": False,
        "scope": SCOPE,
    }


def _category(
    name: str,
    keys: list[str],
    *,
    key_format: str,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ordered = sorted(keys)
    result = dict(
        name=name,
        count=len(keys),
        keys_sample=ordered[:20],
        keys_complete=len(keys) <= 20,
        supports=["read"],
        key_format=key_format,
        reference_only=True,
    )
    if len(keys) <= 20:
        result["keys"] = ordered
    if coverage is not None:
        result["coverage"] = coverage
    return result


def _categories(domain: str, snapshots: dict) -> list[dict]:
    result = [
        _category(
            "source_collections",
            list(snapshots),
            key_format="所列来源键；返回完整结构化来源对象",
        )
    ]
    if domain == "heluo":
        inherited = snapshots["heluoTiaowen"][0]
        keys = [
            f"{gua}:{pos}"
            for gua, row in inherited.items()
            for pos in row.get("yao", {})
        ]
        result.append(
            _category(
                "line_texts",
                keys,
                key_format="计算返回的完整卦名:爻位，例如乾為天:1",
                coverage=dict(
                    header_collated=len(snapshots["yaoci_collation"][0]["entries"]),
                    commentary_collated=len(
                        snapshots["commentary_collation"][0]["entries"]
                    ),
                    header_pending=len(keys)
                    - len(snapshots["yaoci_collation"][0]["entries"]),
                    commentary_pending=len(keys)
                    - len(snapshots["commentary_collation"][0]["entries"]),
                    poem_groups_collated=len(snapshots["poem_collation"][0]["entries"]),
                    poem_groups_pending=len(keys)
                    - len(snapshots["poem_collation"][0]["entries"]),
                    total_line_keyspace=len(keys),
                    scope="键空间包含待核的继承文本，不是已校勘覆盖数；各部分状态分别返回。",
                ),
            )
        )
    else:
        data = snapshots["text_collation"][0]
        keys = [
            f"{e['element']}.{e['number']}.{kind}"
            for e in data["entries"]
            for kind in e["cells"]
        ]
        uncertain = sum(
            len(e.get("reading_uncertainties", {})) for e in data["entries"]
        )
        result.extend(
            [
                _category(
                    "text_cells",
                    keys,
                    key_format="部别.编号.male|female|luck|unselected；可核对本地缺行键，不补文",
                    coverage=dict(
                        examined_cells=len(keys),
                        clear_reading_cells=len(keys) - uncertain,
                        unresolved_reading_cells=uncertain,
                        total_cells=data["total_cells"],
                        scope="已列样例不等于所有键；本地缺行、圈空、未选栏目与疑读分列。",
                    ),
                ),
                _category(
                    "schedule_clauses",
                    [c["id"] for c in snapshots["schedule_basis"][0]["clauses"]],
                    key_format="原句ID",
                ),
                _category(
                    "schedule_profiles",
                    ["bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"],
                    key_format="配运政策ID；仅返回参考角色，不生成交运日期",
                ),
            ]
        )
    return result


def build_registry(domain: str) -> dict[str, Any]:
    if domain not in DOMAINS:
        raise ToolValidationError(
            "Unknown numerology knowledge domain",
            code="knowledge.unknown_domain",
            details={"domain": domain},
        )
    snapshots = _snapshots(domain)
    provenance = _provenance(domain, snapshots)
    return {
        "source": SOURCE,
        "bundle_version": None,
        "provenance": provenance,
        "domains": [
            {
                "domain": domain,
                "source": SOURCE,
                "bundle_version": None,
                "provenance": deepcopy(provenance),
                "categories": _categories(domain, snapshots),
            }
        ],
    }


def _unknown(domain: str, category: str, key: str) -> NoReturn:
    raise ToolValidationError(
        f"Unknown {domain} reference key: {category}/{key}",
        code=f"knowledge.{domain}.unknown_key",
        details={"domain": domain, "category": category, "key": key},
    )


def _cell_key(key: str) -> tuple[str, int, str | None] | None:
    match = re.fullmatch(
        r"([水火木金土])\.([0-9]+)\.(male|female|luck|unselected)", key
    )
    if match is None:
        return None
    element, number, kind = match.groups()
    return element, int(number), None if kind == "unselected" else kind


def read_reference(
    *, domain: str, category: str | None, key: str | None
) -> dict[str, Any]:
    """Retain actual corpus fields and conditions; no birth inputs or arithmetic."""
    category, key = str(category or "").strip(), str(key or "").strip()
    if domain not in DOMAINS:
        _unknown(domain, category, key)
    if not category:
        available = [e["key"] for e in _catalogue()["sources"] if e["domain"] == domain]
        matches = ["source_collections"] if key in available else []
        if domain == "canping" and _cell_key(key):
            matches.append("text_cells")
        if domain == "heluo" and re.fullmatch(r".+:[1-6]", key):
            matches.append("line_texts")
        if domain == "canping":
            if key in {"bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"}:
                matches.append("schedule_profiles")
            elif not matches:
                basis, _ = _source(domain, "schedule_basis")
                if key in {c["id"] for c in basis["clauses"]}:
                    matches.append("schedule_clauses")
        matches = sorted(set(matches))
        if len(matches) != 1:
            _unknown(domain, category, key)
        category = matches[0]
    needed = {
        "source_collections": [key],
        "line_texts": [
            "heluoTiaowen",
            "yaoci_collation",
            "commentary_collation",
            "poem_collation",
        ],
        "text_cells": ["canpingTiaowen", "text_collation", "text_witnesses"],
        "schedule_clauses": ["schedule_basis"],
        "schedule_profiles": ["schedule_basis"],
    }
    permitted = (
        {"source_collections", "line_texts"}
        if domain == "heluo"
        else {
            "source_collections",
            "text_cells",
            "schedule_clauses",
            "schedule_profiles",
        }
    )
    if category not in permitted:
        _unknown(domain, category, key)
    if category == "source_collections" and not any(
        e["domain"] == domain and e["key"] == key for e in _catalogue()["sources"]
    ):
        _unknown(domain, category, key)
    snapshots = _snapshots(domain, needed[category])
    title = f"{domain} · {category} · {key}"
    tips = []
    citation = ""
    if category == "source_collections" and key in snapshots:
        record, meta = snapshots[key]
        title = meta["source_title"] or f"{domain} · {key}（继承或具名来源对象）"
        tips = [
            "本条目录摘要；完整来源对象在reference_details.record。",
            f"来源状态：{meta['review_status']}",
            SCOPE,
        ]
        citation = f"{title}；来源文件{meta['source_path']}；内容修订身份见provenance.source_records"
    elif domain == "heluo" and category == "line_texts":
        from fatebridge.core.heluo import yao_text

        gua, _, pos = key.rpartition(":")
        if pos not in snapshots["heluoTiaowen"][0].get(gua, {}).get("yao", {}):
            _unknown(domain, category, key)
        line_record = yao_text(gua, int(pos))
        if line_record is None:
            _unknown(domain, category, key)
        record = line_record
        title = f"河洛·{gua}·第{pos}爻（参考）"
        status = record["text_provenance"]
        tips = [
            f"爻辞（{status['yaoci_status']}）：{record['yaoci']}",
            f"注文（{status['commentary_status']}）：{record['detail']}",
            f"诗歌（{status['poem_status']}）：{record['shige']}",
            f"继承摘要（{status['verdict_status']}）：{record['verdict']}",
            SCOPE,
        ]
        # A summary-only reader must see the same unresolved reading that a
        # complete source record reports, scoped to its header or commentary.
        pending_notes = []
        for field, notes_field, label in [
            ("review_status", "header_reading_notes", "爻辞"),
            ("commentary_review_status", "commentary_reading_notes", "注文"),
        ]:
            if "unresolved" in status.get(field, ""):
                pending_notes.append(
                    f"{label}字形未决：" + "；".join(status.get(notes_field, []))
                )
        tips.extend(pending_notes)
        tips.extend(_heluo_reference_notes(record))
        citation = f"{title}；各部分原典网址、书影身份与页码分别见reference_details.record.text_provenance"
    elif domain == "canping" and category == "text_cells":
        from fatebridge.core.canping_texts import lookup_record

        parsed = _cell_key(key)
        if parsed is None:
            _unknown(domain, category, key)
        element, number, kind = parsed
        key = f"{element}.{number}.{kind or 'unselected'}"
        record = lookup_record(element, number, kind)
        selection = record["selection"]
        title = f"参评·{key}（{selection['column'] or '未选栏目'}；参考）"
        tips = [
            f"栏目状态：{selection['cell_status']}；本地行状态：{selection['row_status']}。"
        ]
        tips.append(
            f"实际文字：{record['text']}"
            if record["text"]
            else "本条没有所选可读正文；不从其他栏目、编号或版本补入。"
        )
        if selection.get("reading_uncertainties"):
            tips.extend(selection["reading_uncertainties"])
        if selection.get("editorial_unknown_marker") == "□":
            tips.append("□是编辑未定字标记，不认作原书圈空。")
        if selection.get("number_attribution_status") == "provisional_inherited_key":
            tips.append(
                "原图编号仍有未定字，查询键仅沿用暂定归属；可读正文不证明编号已核。"
            )
        if selection.get("row_status") == "retired_inherited_number":
            tips.append(
                f"旧转录号已退役，所核新号为{selection['corrected_number']}；不据此改写实际计算所得编号。"
            )
        witnesses = selection.get("witnesses", [])
        if any(w.get("number_occurrence_ambiguous") for w in witnesses):
            tips.append(
                "同一文明書局本同号有多处正文，按原页并列；号文归属未裁定，不据第一条替换主选文。"
            )
            for witness in witnesses:
                pages = "、".join(str(p) for p in witness["pdf_pages"])
                tips.append(
                    f"文明書局本对读（单次目读，PDF第{pages}页）：{witness['text']}；未替换主选文。"
                )
        tips.append(SCOPE)
        meta = snapshots["text_collation"][1]
        citation = f"{meta['source_title']}；{meta['source_url']}；PDF页{selection.get('source_pdf_page', '未定位')}；另本对读身份另列，不替主本认证。"
    elif domain == "canping" and category in {"schedule_clauses", "schedule_profiles"}:
        from fatebridge.core.canping_schedule_basis import (
            APPLIED,
            SUMMARIES,
            clause_role,
            source_readings,
        )

        data = source_readings()
        if category == "schedule_clauses":
            clause = next((c for c in data["clauses"] if c["id"] == key), None)
            if clause is None:
                _unknown(domain, category, key)
            source = data["sources"][clause["source_id"]]
            record = {
                **clause,
                "source": source,
                "role_by_profile": {p: clause_role(p, clause) for p in APPLIED},
            }
            tips = [
                f"原文：{clause['text']}",
                "各政策参考角色："
                + "；".join(f"{p}={r}" for p, r in record["role_by_profile"].items()),
                SCOPE,
            ]
            citation = f"{source['title']}；{source['edition']}；PDF第{clause['pdf_page']}页；{source['url']}"
        else:
            if key not in APPLIED:
                _unknown(domain, category, key)
            record = {
                "profile_id": key,
                "summary": SUMMARIES[key],
                "applied_clause_ids_for_profile": list(APPLIED[key]),
                "clauses": [
                    {**c, "role_for_profile": clause_role(key, c)}
                    for c in data["clauses"]
                ],
                "sources": deepcopy(data["sources"]),
                "actual_start_at": None,
                "calendar_mapping_requires_personal_input": key != "legacy_minggong_v1",
                "actual_calendar_mapping_evaluated": False,
                "personal_applicability_assessed": False,
                "scope": "所列是政策参考角色；没有个人输入，不返回个人实际日期或当前适用角色。",
            }
            tips = [
                "政策参考说明（文中的本次指所述政策，不是已选择个人方案）："
                + SUMMARIES[key],
                SCOPE,
            ]
            citation = "；".join(
                f"{s['title']}；{s['edition']}；{s['url']}"
                for s in data["sources"].values()
            )
    else:
        _unknown(domain, category, key)
    provenance = _provenance(domain, snapshots, category=category, key=key)
    return deepcopy(
        {
            "domain": domain,
            "category": category,
            "key": key,
            "query_normalized": {"key": key},
            "title": title,
            "tips": tips,
            "lines": list(tips),
            "rendered_text": "\n".join([f"[{title}]", *tips]),
            "source": SOURCE,
            "bundle_version": None,
            "provenance": provenance,
            "citation": citation,
            "reference_only": True,
            "reference_details": {
                "policy_id": POLICY_ID,
                "reference_only": True,
                "personal_applicability_assessed": False,
                "record": record,
            },
        }
    )
