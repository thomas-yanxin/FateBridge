from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, cast


class ToolValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


ASTRO_LABELS = {
    "Sun": "太阳",
    "Moon": "月亮",
    "Mercury": "水星",
    "Venus": "金星",
    "Mars": "火星",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Uranus": "天王星",
    "Neptune": "海王星",
    "Pluto": "冥王星",
    "North Node": "北交",
    "South Node": "南交",
    "Pars Fortuna": "福点",
    "Pars Spirit": "灵点",
    "Pars Venus": "爱点",
    "Pars Mercury": "弱点",
    "Pars Mars": "勇点",
    "Pars Jupiter": "赢点",
    "Pars Saturn": "罪点",
    "Pars Father": "父权点",
    "Pars Mother": "母爱点",
    "Pars Brothers": "友情点",
    "Pars Wedding [Male]": "婚姻点（男性）",
    "Pars Wedding [Female]": "婚姻点（女性）",
    "Pars Sons": "子嗣点",
    "Pars Diseases": "灾厄点",
    "Pars Life": "生命点",
    "Pars Radix": "光耀点",
    "Aries": "牡羊",
    "Taurus": "金牛",
    "Gemini": "双子",
    "Cancer": "巨蟹",
    "Leo": "狮子",
    "Virgo": "室女",
    "Libra": "天秤",
    "Scorpio": "天蝎",
    "Sagittarius": "射手",
    "Capricorn": "摩羯",
    "Aquarius": "宝瓶",
    "Pisces": "双鱼",
}

QIMEN_GOD_ALIASES = {
    "腾蛇": "螣蛇",
    "符": "值符",
    "蛇": "螣蛇",
    "阴": "太阴",
    "合": "六合",
    "虎": "白虎",
    "玄": "玄武",
    "地": "九地",
    "天": "九天",
}

QIMEN_STAR_ALIASES = {
    "蓬": "天蓬",
    "任": "天任",
    "冲": "天冲",
    "辅": "天辅",
    "英": "天英",
    "芮": "天芮",
    "禽": "天禽",
    "柱": "天柱",
    "心": "天心",
    "天内": "天芮",
}


def _data_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "knowledge" / name


def _load_json(name: str) -> dict[str, Any]:
    return cast(
        "dict[str, Any]", json.loads(_data_path(name).read_text(encoding="utf-8"))
    )


@lru_cache(maxsize=1)
def load_knowledge_bundles() -> dict[str, dict[str, Any]]:
    bundles = {
        "astro": _load_json("astro.json"),
        "liureng": _load_json("liureng.json"),
        "qimen": _load_json("qimen.json"),
        "bazi": _load_json("bazi.json"),
    }
    # Add new concepts without rewriting the historically sealed base bundle.
    base = bundles["bazi"]["categories"]
    old_keys = {key for entries in base.values() for key in entries}
    supplements = []
    supplement_ids = set()
    for filename in (
        "bazi-foundations.json",
        "bazi-source-contrasts.json",
        "bazi-frontmatter.json",
    ):
        raw = _data_path(filename).read_bytes()
        supplement = json.loads(raw)
        if not isinstance(supplement, dict):
            raise ValueError("Invalid BaZi knowledge supplement")
        categories = supplement.get("categories")
        if (
            supplement.get("schema_version") != 1
            or supplement.get("domain") != "bazi"
            or not isinstance(supplement.get("id"), str)
            or not supplement["id"]
            or type(supplement.get("version")) is not int
            or not isinstance(categories, dict)
            or not categories
        ):
            raise ValueError("Invalid BaZi knowledge supplement")
        if supplement["id"] in supplement_ids:
            raise ValueError("Knowledge supplements cannot repeat component IDs")
        supplement_ids.add(supplement["id"])
        for category, entries in categories.items():
            if not isinstance(category, str) or not category:
                raise ValueError("Knowledge supplement needs named categories")
            if category in base:
                raise ValueError("Knowledge supplement cannot replace a base category")
            if not isinstance(entries, dict) or not entries:
                raise ValueError("Knowledge supplement needs nonempty entry mappings")
            if old_keys.intersection(entries):
                raise ValueError("Knowledge supplement cannot shadow existing keys")
            base[category] = entries
            old_keys.update(entries)
        supplements.append(
            {
                "id": supplement["id"],
                "version": supplement["version"],
                "source_file": "data/knowledge/" + filename,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "categories": [
                    {
                        "name": name,
                        "count": len(entries),
                        "keys_sample": sorted(entries),
                    }
                    for name, entries in categories.items()
                ],
            }
        )
    bundles["bazi"]["supplements"] = supplements
    return bundles


@lru_cache(maxsize=1)
def load_knowledge_index() -> dict[str, Any]:
    try:
        return _load_json("index.json")
    except FileNotFoundError:
        bundles = load_knowledge_bundles()
        return {
            "schema_version": 1,
            "bundle_version": 1,
            "source": "xingque_hover_docs",
            "build_timestamp": None,
            "upstream_source_marker": "xingque_hover_docs",
            "domains": [
                {
                    "domain": "astro",
                    "categories": [
                        {
                            "name": key,
                            "count": len(value),
                            "keys_sample": sorted(value)[:20],
                        }
                        for key, value in bundles["astro"].get("categories", {}).items()
                    ],
                    "missing_categories": [],
                    "fallback_categories": [],
                },
                {
                    "domain": "liureng",
                    "categories": [
                        {
                            "name": "shen",
                            "count": len(bundles["liureng"].get("shen_entries", {})),
                            "keys_sample": sorted(
                                bundles["liureng"].get("shen_entries", {})
                            )[:20],
                        },
                        {
                            "name": "house",
                            "count": len(bundles["liureng"].get("jiang_info", {})),
                            "keys_sample": sorted(
                                bundles["liureng"].get("jiang_info", {})
                            )[:20],
                        },
                    ],
                    "missing_categories": [],
                    "fallback_categories": [],
                },
                {
                    "domain": "qimen",
                    "categories": [
                        {
                            "name": key,
                            "count": len(value),
                            "keys_sample": sorted(value)[:20],
                        }
                        for key, value in bundles["qimen"].get("categories", {}).items()
                    ],
                    "missing_categories": [],
                    "fallback_categories": [],
                },
            ],
        }


def _domain_index(domain: str) -> dict[str, Any]:
    for item in load_knowledge_index().get("domains", []):
        if item.get("domain") == domain:
            return deepcopy(cast("dict[str, Any]", item))
    return {}


def _knowledge_provenance(
    *, domain: str, category: str | None = None, key: str | None = None
) -> dict[str, Any]:
    index = load_knowledge_index()
    provenance = {
        "source_domain": "xingque_hover_docs",
        "domain": domain,
        "category": category,
        "key": key,
        "bundle_version": index.get("bundle_version"),
        "build_timestamp": index.get("build_timestamp"),
        "upstream_source_marker": index.get(
            "upstream_source_marker", "xingque_hover_docs"
        ),
        "coverage": _domain_index(domain),
    }
    supplements = [
        item
        for item in load_knowledge_bundles().get(domain, {}).get("supplements", [])
        if category is None
        or any(entry["name"] == category for entry in item["categories"])
    ]
    if supplements:
        provenance["supplements"] = deepcopy(supplements)
        provenance["coverage_scope"] = "original_index_plus_declared_supplements"
    return provenance


def _normalize_house_key(key: str) -> str:
    text = (key or "").strip()
    if not text:
        return ""
    match = re.search(r"(\d+)", text)
    if match:
        number = int(match.group(1))
        if 1 <= number <= 12:
            return f"House{number}"
    normalized = (
        text.replace("第", "").replace("宫", "").replace("房", "").strip().lower()
    )
    aliases = {
        "asc": "House1",
        "命宫": "House1",
    }
    return aliases.get(normalized, text)


def _normalize_astro_key(category: str, key: str) -> str:
    text = (key or "").strip()
    if category == "house":
        return _normalize_house_key(text)
    if category == "aspect":
        return text
    bundle = load_knowledge_bundles()["astro"]
    labels = bundle.get("labels", {})
    reverse_labels = {
        value: one for one, value in labels.items() if isinstance(value, str)
    }
    return cast(str, reverse_labels.get(text, text))


def _normalize_qimen_key(category: str, key: str) -> str:
    text = (key or "").strip()
    if category == "stem":
        return text[:1]
    if category == "door":
        return text if text.endswith("门") else f"{text}门"
    if category == "star":
        return QIMEN_STAR_ALIASES.get(text, text)
    if category == "god":
        return QIMEN_GOD_ALIASES.get(text, text)
    return text


def _normalize_liureng_branch(key: str) -> str:
    match = re.search(r"[子丑寅卯辰巳午未申酉戌亥]", key or "")
    return match.group(0) if match else ""


def _tips_to_rendered_text(title: str, tips: list[str]) -> str:
    lines = [f"[{title}]"]
    for tip in tips:
        tip_text = f"{tip}".strip()
        if not tip_text:
            continue
        if tip_text == "==":
            lines.append("")
            continue
        lines.append(f"- {tip_text}")
    return "\n".join(lines).strip()


def _strip_qimen_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _render_qimen_blocks(
    title: str, blocks: list[dict[str, Any]]
) -> tuple[list[str], str]:
    lines = [f"[{title}]"]
    flat_lines: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "blank":
            lines.append("")
            flat_lines.append("")
            continue
        if block_type == "divider":
            lines.append("==")
            flat_lines.append("==")
            continue
        if block_type == "subTitle":
            text = _strip_qimen_html(block.get("text", ""))
            if text:
                lines.append(f"## {text}")
                flat_lines.append(f"## {text}")
            continue
        text = _strip_qimen_html(block.get("text", ""))
        if text:
            lines.append(text)
            flat_lines.append(text)
    rendered = "\n".join(line for line in lines if line is not None).strip()
    normalized_lines = [line for line in flat_lines if line.strip()]
    return normalized_lines, rendered


def _build_liureng_house_entry(
    bundle: dict[str, Any], jiang_name: str, tian_branch: str, di_branch: str
) -> dict[str, Any]:
    aliases = bundle.get("jiang_aliases", {})
    jiang_info = bundle.get("jiang_info", {})
    jiang_branch_note = bundle.get("jiang_branch_note", {})
    normalized_name = aliases.get(jiang_name, jiang_name)
    info = jiang_info.get(normalized_name)
    if not info:
        raise ToolValidationError(
            f"Unknown 六壬将神: {jiang_name}",
            code="knowledge.liureng.unknown_jiang",
            details={"jiang_name": jiang_name},
        )
    tian = _normalize_liureng_branch(tian_branch)
    di = _normalize_liureng_branch(di_branch)
    if not tian or not di:
        raise ToolValidationError(
            "六壬将盘悬浮知识需要有效的天盘地支与地盘地支。",
            code="knowledge.liureng.invalid_branch",
            details={"tian_branch": tian_branch, "di_branch": di_branch},
        )
    shen_entries = bundle.get("shen_entries", {})
    tian_entry = shen_entries.get(tian, {"title": f"{tian}神", "tips": []})
    di_entry = shen_entries.get(di, {"title": f"{di}神", "tips": []})
    notes = jiang_branch_note.get(normalized_name, {})
    tips: list[str] = []
    for line in info.get("intros", []):
        tips.append(line)
    for line in info.get("verses", []):
        tips.append(f"**{line}**")
    for line in info.get("extra", []):
        tips.append(line)
    tips.extend(
        [
            "==",
            f"**天盘神：**{tian_entry.get('title', tian)}",
            f"{tian}——{notes.get(tian, '未载于《将》文。')}。",
            "==",
            f"**地盘神：**{di_entry.get('title', di)}",
            f"{di}——{notes.get(di, '未载于《将》文。')}。",
        ]
    )
    return {
        "domain": "liureng",
        "category": "house",
        "key": normalized_name,
        "query_normalized": {
            "jiang_name": normalized_name,
            "tian_branch": tian,
            "di_branch": di,
        },
        "title": jiang_name or normalized_name,
        "tips": tips,
        "lines": [line for line in tips if line and line != "=="],
        "rendered_text": _tips_to_rendered_text(jiang_name or normalized_name, tips),
        "source": "xingque_hover_docs",
        "bundle_version": load_knowledge_index().get("bundle_version"),
        "provenance": _knowledge_provenance(
            domain="liureng", category="house", key=normalized_name
        ),
        "citation": f"Xingque hover knowledge · liureng/house/{normalized_name}",
    }


def build_knowledge_registry(domain: str | None = None) -> dict[str, Any]:
    bundles = load_knowledge_bundles()
    index = load_knowledge_index()
    domains = [domain] if domain else sorted(bundles)
    result_domains: list[dict[str, Any]] = []
    for name in domains:
        bundle = bundles.get(name)
        if not bundle:
            raise ToolValidationError(
                f"Unknown knowledge domain: {name}",
                code="knowledge.unknown_domain",
                details={"domain": name},
            )
        if name == "astro":
            categories = [
                {
                    "name": category,
                    "count": len(entries),
                    "keys": sorted(entries)[:20],
                    "supports": ["read"],
                }
                for category, entries in bundle.get("categories", {}).items()
            ]
        elif name == "qimen":
            categories = [
                {
                    "name": category,
                    "count": len(entries),
                    "keys": sorted(entries)[:20],
                    "supports": ["read"],
                }
                for category, entries in bundle.get("categories", {}).items()
            ]
        elif name == "bazi":
            categories = [
                {
                    "name": category,
                    "count": len(entries),
                    "keys": sorted(entries)[:20],
                    "supports": ["read"],
                }
                for category, entries in bundle.get("categories", {}).items()
            ]
        else:
            categories = [
                {
                    "name": "shen",
                    "count": len(bundle.get("shen_entries", {})),
                    "keys": sorted(bundle.get("shen_entries", {})),
                    "supports": ["read"],
                },
                {
                    "name": "house",
                    "count": len(bundle.get("jiang_info", {})),
                    "keys": sorted(bundle.get("jiang_info", {})),
                    "supports": ["read", "jiang_name+tian_branch+di_branch"],
                },
            ]
        result_domains.append(
            {
                "domain": name,
                "source": "xingque_hover_docs",
                "bundle_version": index.get("bundle_version"),
                "provenance": _knowledge_provenance(domain=name),
                "categories": categories,
            }
        )
    return {
        "source": "xingque_hover_docs",
        "bundle_version": index.get("bundle_version"),
        "provenance": {
            "source_domain": "xingque_hover_docs",
            "bundle_version": index.get("bundle_version"),
            "build_timestamp": index.get("build_timestamp"),
            "upstream_source_marker": index.get(
                "upstream_source_marker", "xingque_hover_docs"
            ),
        },
        "domains": result_domains,
    }


def _resolve_category_for_key(
    categories: dict[str, Any],
    key: str,
    normalizer: Callable[[str, str], str] | None = None,
) -> list[tuple[str, str]]:
    """Find which category/categories under a domain hold ``key``.

    Returns ``(category, normalized_key)`` matches so the caller can tell apart
    "not found" (0), "resolved" (1), and "ambiguous" (>1).
    """
    matches: list[tuple[str, str]] = []
    for cat_name, entries in categories.items():
        if not isinstance(entries, dict):
            continue
        candidate = normalizer(cat_name, key) if normalizer else key
        if candidate in entries:
            matches.append((cat_name, candidate))
    return matches


def _autoresolve_bare_category(domain: str, bundles: dict[str, Any], key: str) -> str:
    """Resolve the category for a bare ``key`` lookup (category omitted).

    Only the flat ``categories``-dict domains (astro, bazi, qimen) can be
    auto-resolved; liureng keeps its own shen/house layout, so callers there
    must still pass a category.
    """
    categories = bundles.get(domain, {}).get("categories", {})
    if not categories:
        raise ToolValidationError(
            f"Category is required for domain '{domain}'",
            code=f"knowledge.{domain}.category_required",
            details={"domain": domain},
        )
    normalizer: Callable[[str, str], str] | None = None
    if domain == "astro":

        def normalizer(cat: str, k: str) -> str:
            return k if cat == "aspect" else _normalize_astro_key(cat, k)

    elif domain == "qimen":
        normalizer = _normalize_qimen_key
    matches = _resolve_category_for_key(categories, key, normalizer)
    if len(matches) == 1:
        return matches[0][0]
    if not matches:
        raise ToolValidationError(
            f"Unknown {domain} knowledge key: {key}",
            code=f"knowledge.{domain}.unknown_key",
            details={"key": key, "available_categories": sorted(categories)},
        )
    raise ToolValidationError(
        f"Ambiguous knowledge key '{key}' in domain '{domain}'; specify a category",
        code=f"knowledge.{domain}.ambiguous_key",
        details={"key": key, "candidate_categories": [c for c, _ in matches]},
    )


def read_knowledge_entry(payload: dict[str, Any]) -> dict[str, Any]:
    bundles = load_knowledge_bundles()
    domain = f"{payload.get('domain') or ''}".strip()
    category = f"{payload.get('category') or ''}".strip()
    key = f"{payload.get('key') or ''}".strip()
    if domain not in bundles:
        raise ToolValidationError(
            f"Unknown knowledge domain: {domain}",
            code="knowledge.unknown_domain",
            details={"domain": domain},
        )
    if not category and key:
        category = _autoresolve_bare_category(domain, bundles, key)
    if domain == "astro":
        bundle = bundles["astro"]
        categories = bundle.get("categories", {})
        if category == "aspect":
            aspect_key = str(
                payload.get("aspect_degree")
                if payload.get("aspect_degree") is not None
                else key
            ).strip()
            entry = categories.get("aspect", {}).get(aspect_key)
            if not entry:
                raise ToolValidationError(
                    f"Unknown astro aspect: {aspect_key}",
                    code="knowledge.astro.unknown_key",
                    details={"category": category, "key": aspect_key},
                )
            object_a = f"{payload.get('object_a') or ''}".strip()
            object_b = f"{payload.get('object_b') or ''}".strip()
            title = entry.get("title", "")
            tips = list(entry.get("tips", []))
            if object_a and object_b:
                title = f"{ASTRO_LABELS.get(object_a, object_a)} - {ASTRO_LABELS.get(object_b, object_b)}：{entry.get('title', '')}"
                if tips and not tips[0].startswith("对象："):
                    tips.insert(
                        0,
                        f"对象：{ASTRO_LABELS.get(object_a, object_a)} 与 {ASTRO_LABELS.get(object_b, object_b)}",
                    )
            return {
                "domain": domain,
                "category": category,
                "key": aspect_key,
                "query_normalized": {
                    "key": aspect_key,
                    "object_a": object_a or None,
                    "object_b": object_b or None,
                },
                "title": title,
                "tips": tips,
                "lines": [tip for tip in tips if tip and tip != "=="],
                "rendered_text": _tips_to_rendered_text(title, tips),
                "source": "xingque_hover_docs",
                "bundle_version": load_knowledge_index().get("bundle_version"),
                "provenance": _knowledge_provenance(
                    domain=domain, category=category, key=aspect_key
                ),
                "citation": f"Xingque hover knowledge · {domain}/{category}/{aspect_key}",
            }
        normalized_key = _normalize_astro_key(category, key)
        entry = categories.get(category, {}).get(normalized_key)
        if not entry:
            raise ToolValidationError(
                f"Unknown astro knowledge key: {key}",
                code="knowledge.astro.unknown_key",
                details={
                    "category": category,
                    "key": key,
                    "normalized_key": normalized_key,
                },
            )
        tips = list(entry.get("tips", []))
        return {
            "domain": domain,
            "category": category,
            "key": normalized_key,
            "query_normalized": {"key": normalized_key},
            "title": entry.get("title", normalized_key),
            "tips": tips,
            "lines": [tip for tip in tips if tip and tip != "=="],
            "rendered_text": _tips_to_rendered_text(
                entry.get("title", normalized_key), tips
            ),
            "source": "xingque_hover_docs",
            "bundle_version": load_knowledge_index().get("bundle_version"),
            "provenance": _knowledge_provenance(
                domain=domain, category=category, key=normalized_key
            ),
            "citation": f"Xingque hover knowledge · {domain}/{category}/{normalized_key}",
        }

    if domain == "liureng":
        bundle = bundles["liureng"]
        if category == "shen":
            normalized_key = _normalize_liureng_branch(key)
            entry = bundle.get("shen_entries", {}).get(normalized_key)
            if not entry:
                raise ToolValidationError(
                    f"Unknown 六壬地支 knowledge key: {key}",
                    code="knowledge.liureng.unknown_key",
                    details={"category": category, "key": key},
                )
            tips = list(entry.get("tips", []))
            return {
                "domain": domain,
                "category": category,
                "key": normalized_key,
                "query_normalized": {"key": normalized_key},
                "title": entry.get("title", normalized_key),
                "tips": tips,
                "lines": [tip for tip in tips if tip and tip != "=="],
                "rendered_text": _tips_to_rendered_text(
                    entry.get("title", normalized_key), tips
                ),
                "source": "xingque_hover_docs",
                "bundle_version": load_knowledge_index().get("bundle_version"),
                "provenance": _knowledge_provenance(
                    domain=domain, category=category, key=normalized_key
                ),
                "citation": f"Xingque hover knowledge · {domain}/{category}/{normalized_key}",
            }
        if category == "house":
            return _build_liureng_house_entry(
                bundle,
                jiang_name=f"{payload.get('jiang_name') or key or ''}".strip(),
                tian_branch=f"{payload.get('tian_branch') or ''}".strip(),
                di_branch=f"{payload.get('di_branch') or ''}".strip(),
            )
        raise ToolValidationError(
            f"Unknown 六壬 knowledge category: {category}",
            code="knowledge.liureng.unknown_category",
            details={"category": category},
        )

    if domain == "bazi":
        bundle = bundles["bazi"]
        categories = bundle.get("categories", {})
        category_data = categories.get(category, {})
        entry = category_data.get(key)
        if not entry:
            raise ToolValidationError(
                f"Unknown 八字 knowledge key: {key}",
                code="knowledge.bazi.unknown_key",
                details={"category": category, "key": key},
            )
        tips = list(entry.get("tips", []))
        provenance = _knowledge_provenance(domain=domain, category=category, key=key)
        curation = entry.get("curation")
        if isinstance(curation, dict):
            from fatebridge.core.knowledge_revalidation import (
                revalidate_structure_curation,
            )

            curation = revalidate_structure_curation(category, key, curation)
            # Copy nested sources so callers cannot mutate the cached bundle.
            provenance = {
                **provenance,
                "source_domain": "fatebridge_curated_bazi",
                "review_status": curation.get(
                    "review_status", "source_scoped_curation_not_full_acceptance"
                ),
                "build_timestamp_scope": "original_upstream_bundle_stamp_not_current_curation",
                "entry_curation": deepcopy(curation),
            }
        else:
            provenance = {**provenance, "review_status": "legacy_unreviewed"}
        return {
            "domain": domain,
            "category": category,
            "key": key,
            "query_normalized": {"key": key},
            "title": entry.get("title", key),
            "tips": tips,
            "lines": [tip for tip in tips if tip and tip != "=="],
            "rendered_text": _tips_to_rendered_text(entry.get("title", key), tips),
            "source": "fatebridge_knowledge",
            "bundle_version": load_knowledge_index().get("bundle_version"),
            "provenance": provenance,
            "citation": (
                curation.get(
                    "citation", f"FateBridge knowledge · {domain}/{category}/{key}"
                )
                if isinstance(curation, dict)
                else f"FateBridge旧资料待逐条核对 · {domain}/{category}/{key}；未据此认证指定原典或现实效力。"
            ),
        }

    bundle = bundles["qimen"]
    normalized_key = _normalize_qimen_key(category, key)
    entry = bundle.get("categories", {}).get(category, {}).get(normalized_key)
    if not entry:
        raise ToolValidationError(
            f"Unknown 奇门 knowledge key: {key}",
            code="knowledge.qimen.unknown_key",
            details={
                "category": category,
                "key": key,
                "normalized_key": normalized_key,
            },
        )
    lines, rendered_text = _render_qimen_blocks(
        entry.get("title", normalized_key), entry.get("blocks", [])
    )
    return {
        "domain": domain,
        "category": category,
        "key": normalized_key,
        "query_normalized": {"key": normalized_key},
        "title": entry.get("title", normalized_key),
        "blocks": entry.get("blocks", []),
        "lines": lines,
        "rendered_text": rendered_text,
        "source": "xingque_hover_docs",
        "bundle_version": load_knowledge_index().get("bundle_version"),
        "provenance": _knowledge_provenance(
            domain=domain, category=category, key=normalized_key
        ),
        "citation": f"Xingque hover knowledge · {domain}/{category}/{normalized_key}",
    }
