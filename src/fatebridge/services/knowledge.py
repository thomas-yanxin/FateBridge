"""
FateBridge bundled knowledge services.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fatebridge.core.knowledge_store import (
    ToolValidationError,
    build_knowledge_registry,
    read_knowledge_entry,
)
from fatebridge.services.snapshot_builders import (
    build_snapshot_export as _build_snapshot_export,
)
from fatebridge.services.snapshot_builders import (
    render_snapshot_lines as _render_snapshot_text,
)
from fatebridge.utils.errors import handle_calculation_error


def _validation_error_payload(exc: ToolValidationError) -> Dict[str, Any]:
    # Include status_code/error_code so the HTTP transport (_execute_service)
    # maps this to a 400 instead of the default 500.
    return {
        "error": str(exc),
        "error_code": exc.code or "validation_error",
        "code": exc.code,
        "details": exc.details,
        "status_code": 400,
        "retryable": False,
    }


_QUERY_LABELS = {
    "key": "归一化主键",
    "object_a": "对象 A",
    "object_b": "对象 B",
    "jiang_name": "将神",
    "tian_branch": "天盘地支",
    "di_branch": "地盘地支",
}


def _build_knowledge_registry_snapshot_text(
    registry: Dict[str, Any], *, domain: Optional[str]
) -> str:
    provenance = registry.get("provenance") or {}
    domains = registry.get("domains") or []
    overview_lines = [
        f"领域过滤：{domain or '全部'}",
        f"域数量：{len(domains)}",
        f"来源：{registry.get('source', '未提供')}",
    ]
    if registry.get("bundle_version") is not None:
        overview_lines.append(f"Bundle 版本：{registry['bundle_version']}")

    sections: List[tuple[str, List[str]]] = [("目录概览", overview_lines)]
    for item in domains:
        if not isinstance(item, dict):
            continue
        category_lines = [
            f"域：{item.get('domain', '未知')}",
            f"分类数：{len(item.get('categories') or [])}",
        ]
        for category in item.get("categories") or []:
            if not isinstance(category, dict):
                continue
            supports = "/".join(category.get("supports") or []) or "无"
            keys = (
                "、".join(category.get("keys") or category.get("keys_sample") or [])
                or "无"
            )
            category_lines.append(
                f"{category.get('name', '未命名')}："
                f"{category.get('count', 0)} 条；"
                f"支持={supports}；"
                f"样例={keys}"
            )
            if category.get("reference_only"):
                category_lines.append(
                    f"键列表：{'完整' if category.get('keys_complete') else '样例，非全部键'}；"
                    f"查询格式：{category.get('key_format')}；个人适用性未评估。"
                )
        sections.append((item.get("domain", "未知"), category_lines))

    source_lines = [
        f"来源：{provenance.get('source_domain', registry.get('source', '未提供'))}",
    ]
    if provenance.get("bundle_version") is not None:
        source_lines.append(f"Bundle 版本：{provenance['bundle_version']}")
    if provenance.get("upstream_source_marker"):
        source_lines.append(f"上游标记：{provenance['upstream_source_marker']}")
    if provenance.get("build_timestamp"):
        source_lines.append(f"构建时间：{provenance['build_timestamp']}")
    sections.append(("来源", source_lines))
    return _render_snapshot_text(sections)


def _build_knowledge_snapshot_text(entry: Dict[str, Any]) -> str:
    query_normalized = entry.get("query_normalized") or {}
    provenance = entry.get("provenance") or {}
    query_lines = [
        f"领域：{entry.get('domain', '未知')}",
        f"分类：{entry.get('category', '未知')}",
        f"键：{entry.get('key', '未提供')}",
    ]
    if entry.get("title"):
        query_lines.append(f"标题：{entry['title']}")
    for field, label in _QUERY_LABELS.items():
        value = query_normalized.get(field)
        if value in {None, ""}:
            continue
        query_lines.append(f"{label}：{value}")

    body_lines: list[str] = []
    if entry.get("title"):
        body_lines.append(f"标题：{entry['title']}")
    tips = entry.get("tips")
    if isinstance(tips, list) and tips:
        for tip in tips:
            text = f"{tip}".strip()
            if not text:
                body_lines.append("")
                continue
            if text == "==":
                body_lines.append("")
                continue
            body_lines.append(text)
    else:
        for line in entry.get("lines") or []:
            text = f"{line}".strip()
            if text:
                body_lines.append(text)

    source_lines = [
        f"来源：{entry.get('source', '未提供')}",
        f"引文：{entry.get('citation', '未提供')}",
    ]
    if entry.get("bundle_version") is not None:
        source_lines.append(f"Bundle 版本：{entry['bundle_version']}")
    if provenance.get("upstream_source_marker"):
        source_lines.append(f"上游标记：{provenance['upstream_source_marker']}")
    if provenance.get("build_timestamp"):
        label = "上游包构建时间" if provenance.get("entry_curation") else "构建时间"
        source_lines.append(f"{label}：{provenance['build_timestamp']}")

    curation = provenance.get("entry_curation")
    if isinstance(curation, dict):
        source_lines.append(f"出处核对状态：{provenance.get('review_status')}")
        source_lines.append(
            f"词条修订：{curation.get('method_id')} / {curation.get('entry_revision')}"
        )
        source_lines.append(f"词条整理日期：{curation.get('curated_on')}")
        source_lines.append(f"核验范围：{curation.get('validation_status')}")
        for reference in curation.get("source_refs") or []:
            pages = ",".join(str(p) for p in reference.get("source_pdf_pages") or [])
            locator = reference.get("source_locator") or f"PDF {pages}"
            source_lines.append(
                f"原典：{reference.get('author')}《{reference.get('title')}》；{reference.get('edition')}；{locator}"
            )
            source_lines.append(f"原典网址：{reference.get('source_url')}")
            source_lines.append(f"归属范围：{reference.get('support_scope')}")
        for reference in curation.get("implementation_refs") or []:
            source_lines.append(f"实现：{reference.get('source_path')}")
            source_lines.append(f"实现说明范围：{reference.get('support_scope')}")

    if provenance.get("reference_policy_id") == "numerology_source_reference_v1":
        source_lines.append(f"参考范围：{provenance.get('scope')}")
        source_lines.append("所载是来源参考；实际个人取法及适用条款仍须同run计算回执。")
        for record in provenance.get("source_records") or []:
            source_lines.append(
                f"来源对象：{record.get('key')}；{record.get('source_title') or '继承或具名来源对象'}；"
                f"修订：{record.get('source_revision') if record.get('source_revision') is not None else '未提供'}；状态：{record.get('review_status')}"
            )
            if record.get("source_url"):
                source_lines.append(f"来源网址：{record['source_url']}")

    if provenance.get("reference_policy_id") == "human_design_line_reference_v1":
        source_lines.append(f"参考范围：{provenance.get('scope')}")
        for record in provenance.get("source_records") or []:
            source_lines.append(
                f"来源对象：{record.get('key')}；状态：{record.get('review_status')}"
            )
            if record.get("source_url"):
                source_lines.append(f"来源网址：{record['source_url']}")

    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("知识正文", body_lines),
            ("来源", source_lines),
        ]
    )


def calculate_knowledge_registry(
    *,
    domain: Optional[str] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Return bundled hover-knowledge domains and categories.
    """
    try:
        from fatebridge.core import human_design_knowledge
        from fatebridge.core.numerology_knowledge import (
            DOMAINS,
            SCOPE,
            SOURCE,
            build_registry,
        )

        domain_key = domain.strip() if isinstance(domain, str) else domain
        if domain_key == human_design_knowledge.DOMAIN:
            registry = human_design_knowledge.build_registry()
        elif domain_key in DOMAINS:
            registry = build_registry(domain_key)
        elif domain is None or domain == "":
            base_registry = build_knowledge_registry(domain=domain)
            added = [build_registry(name) for name in DOMAINS]
            added.append(human_design_knowledge.build_registry())
            registry = {
                **base_registry,
                "source": "fatebridge_mixed_knowledge",
                "bundle_version": None,
                "domains": [
                    *base_registry["domains"],
                    *(item for r in added for item in r["domains"]),
                ],
                "provenance": {
                    "source_domain": "fatebridge_mixed_knowledge",
                    "components": [
                        base_registry["provenance"],
                        *(r["provenance"] for r in added),
                    ],
                    "added_reference_source": SOURCE,
                    "added_reference_scope": SCOPE,
                },
            }
        else:
            registry = build_knowledge_registry(domain=domain)
        snapshot_text = _build_knowledge_registry_snapshot_text(registry, domain=domain)
        snapshot_export = _build_snapshot_export(
            technique="knowledge_registry",
            snapshot_text=snapshot_text,
            selected_sections=selected_sections,
        )
        return {
            **registry,
            "snapshot_text": snapshot_text,
            "snapshot_export": snapshot_export,
        }
    except ToolValidationError as exc:
        return _validation_error_payload(exc)
    except Exception as exc:
        return handle_calculation_error(exc, "知识目录")


def calculate_knowledge_read(
    *,
    domain: str,
    category: Optional[str] = None,
    key: Optional[str] = None,
    selected_sections: Optional[List[str]] = None,
    aspect_degree: Optional[int | str] = None,
    object_a: Optional[str] = None,
    object_b: Optional[str] = None,
    jiang_name: Optional[str] = None,
    tian_branch: Optional[str] = None,
    di_branch: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Read bundled knowledge or a source-bound 河洛／参评 reference.

    ``category`` may be omitted; when it is, the category is auto-resolved from
    ``key`` for domains that support exact-key resolution.
    """
    try:
        from fatebridge.core import human_design_knowledge
        from fatebridge.core.numerology_knowledge import DOMAINS, read_reference

        payload = {
            "domain": domain,
            "category": category,
            "key": key,
            "aspect_degree": aspect_degree,
            "object_a": object_a,
            "object_b": object_b,
            "jiang_name": jiang_name,
            "tian_branch": tian_branch,
            "di_branch": di_branch,
        }
        domain_key = domain.strip() if isinstance(domain, str) else domain
        if domain_key == human_design_knowledge.DOMAIN:
            irrelevant = {
                name: value
                for name, value in payload.items()
                if name not in {"domain", "category", "key"} and value is not None
            }
            if irrelevant:
                raise ToolValidationError(
                    "人类图线参考只接受category与key定位，不接受相位或其他域对象",
                    code="knowledge.human_design.irrelevant_fields",
                    details={"fields": sorted(irrelevant)},
                )
            entry = human_design_knowledge.read_reference(category=category, key=key)
        elif domain_key in DOMAINS:
            entry = read_reference(domain=domain_key, category=category, key=key)
        else:
            entry = read_knowledge_entry(payload)
        snapshot_text = _build_knowledge_snapshot_text(entry)
        snapshot_export = _build_snapshot_export(
            technique="knowledge",
            snapshot_text=snapshot_text,
            selected_sections=selected_sections,
        )
        return {
            **entry,
            "snapshot_text": snapshot_text,
            "snapshot_export": snapshot_export,
        }
    except ToolValidationError as exc:
        return _validation_error_payload(exc)
    except Exception as exc:
        return handle_calculation_error(exc, "知识读取")
