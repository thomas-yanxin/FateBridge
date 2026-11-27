"""Look up bundled knowledge with explicit reference and curation provenance."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, JsonValue, TypeAdapter, ValidationError
from typing_extensions import TypedDict

from fatebridge.core.knowledge_rule_tables import (
    KnowledgeCard,
    astro_rule_cards,
    qimen_rule_cards,
)

RULE_REFERENCE_DOMAINS = {"astro", "qimen"}
RULE_REFERENCE_SOURCE = "fatebridge_rule_references"


class ToolValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.code: str = code
        self.details: dict[str, JsonValue] = details or {}


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


def _data_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "knowledge" / filename


class GeneralSpiritText(TypedDict, total=False):
    intros: list[str]
    verses: list[str]
    extra: list[str]


class SupplementCategory(TypedDict):
    name: str
    count: int
    keys_sample: list[str]


class KnowledgeSupplementReceipt(TypedDict):
    id: str
    version: int
    source_file: str
    categories: list[SupplementCategory]


class KnowledgeBundle(TypedDict, total=False):
    domain: str
    description: str
    schema_version: int
    source: str
    generated_at: str
    categories: dict[str, dict[str, KnowledgeCard]]
    jiang_aliases: dict[str, str]
    jiang_info: dict[str, GeneralSpiritText]
    jiang_branch_note: dict[str, dict[str, str]]
    shen_entries: dict[str, KnowledgeCard]
    shen_info: dict[str, JsonValue]
    supplements: list[KnowledgeSupplementReceipt]


class KnowledgeSupplement(TypedDict):
    domain: Literal["bazi"]
    schema_version: int
    id: Annotated[str, Field(min_length=1)]
    version: int
    categories: Annotated[dict[str, dict[str, KnowledgeCard]], Field(min_length=1)]


KNOWLEDGE_JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(
    dict[str, JsonValue],
)
KNOWLEDGE_BUNDLE: TypeAdapter[KnowledgeBundle] = TypeAdapter(KnowledgeBundle)
KNOWLEDGE_SUPPLEMENT: TypeAdapter[KnowledgeSupplement] = TypeAdapter(
    KnowledgeSupplement
)


@lru_cache(maxsize=1)
def load_knowledge_bundles() -> dict[str, KnowledgeBundle]:
    bundles: dict[str, KnowledgeBundle] = {
        "astro": {"categories": astro_rule_cards(ASTRO_LABELS)},
        "liureng": KNOWLEDGE_BUNDLE.validate_json(
            _data_path("liureng.json").read_bytes(), strict=True
        ),
        "qimen": {"categories": qimen_rule_cards()},
        "bazi": KNOWLEDGE_BUNDLE.validate_json(
            _data_path("bazi.json").read_bytes(), strict=True
        ),
    }
    # note (knowledge bundles): Supplements extend the sealed base without changing its source bytes.
    base = bundles["bazi"]["categories"]
    old_keys = {key for entries in base.values() for key in entries}
    supplements: list[KnowledgeSupplementReceipt] = []
    supplement_ids: set[str] = set()
    for filename in (
        "bazi-foundations.json",
        "bazi-source-contrasts.json",
        "bazi-frontmatter.json",
    ):
        raw = _data_path(filename).read_bytes()
        try:
            supplement = KNOWLEDGE_SUPPLEMENT.validate_json(raw, strict=True)
        except ValidationError as error:
            raise ValueError("Invalid BaZi knowledge supplement") from error
        if supplement["schema_version"] != 1:
            raise ValueError("Invalid BaZi knowledge supplement")
        supplement_id = supplement["id"]
        if supplement_id in supplement_ids:
            raise ValueError("Knowledge supplements cannot repeat component IDs")
        supplement_ids.add(supplement_id)
        categories = supplement["categories"]
        for category, entries in categories.items():
            if not category:
                raise ValueError("Knowledge supplement needs named categories")
            if category in base:
                raise ValueError("Knowledge supplement cannot replace a base category")
            if not entries:
                raise ValueError("Knowledge supplement needs nonempty entry mappings")
            if old_keys.intersection(entries):
                raise ValueError("Knowledge supplement cannot shadow existing keys")
            base[category] = entries
            old_keys.update(entries)
        supplements.append(
            {
                "id": supplement_id,
                "version": supplement["version"],
                "source_file": "data/knowledge/" + filename,
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
def load_knowledge_index() -> dict[str, JsonValue]:
    return KNOWLEDGE_JSON_OBJECT.validate_json(_data_path("index.json").read_bytes())


@lru_cache(maxsize=1)
def _domain_index_by_name() -> dict[str, dict[str, Any]]:
    domain_index = load_knowledge_index().get("domains")
    assert isinstance(domain_index, list)
    by_name: dict[str, dict[str, Any]] = {}
    for domain_record in domain_index:
        assert isinstance(domain_record, dict)
        name = domain_record.get("domain")
        if isinstance(name, str):
            by_name[name] = domain_record
    return by_name


def _domain_index(domain: str) -> dict[str, Any]:
    if domain in RULE_REFERENCE_DOMAINS:
        return {
            "domain": domain,
            "categories": [
                {"name": name, "count": len(entries), "keys_sample": sorted(entries)}
                for name, entries in load_knowledge_bundles()[domain][
                    "categories"
                ].items()
            ],
        }
    return dict(_domain_index_by_name().get(domain, {}))


class KnowledgeProvenance(TypedDict, total=False):
    source_domain: str
    domain: str
    category: str | None
    key: str | None
    bundle_version: JsonValue
    build_timestamp: JsonValue
    upstream_source_marker: JsonValue
    coverage: dict[str, Any]
    reference_only: bool
    personal_applicability_assessed: bool
    supplements: list[KnowledgeSupplementReceipt]
    coverage_scope: str
    review_status: JsonValue
    build_timestamp_scope: str
    entry_curation: dict[str, JsonValue]


def _knowledge_provenance(
    *, domain: str, category: str | None = None, key: str | None = None
) -> KnowledgeProvenance:
    if domain in RULE_REFERENCE_DOMAINS:
        return {
            "source_domain": RULE_REFERENCE_SOURCE,
            "domain": domain,
            "category": category,
            "key": key,
            "coverage": _domain_index(domain),
            "reference_only": True,
            "personal_applicability_assessed": False,
        }
    index = load_knowledge_index()
    provenance: KnowledgeProvenance = {
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
        supplement
        for supplement in load_knowledge_bundles()
        .get(domain, {})
        .get("supplements", [])
        if category is None
        or any(
            category_record["name"] == category
            for category_record in supplement["categories"]
        )
    ]
    if supplements:
        provenance["supplements"] = list(supplements)
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
        "命": "House1",
    }
    return aliases.get(normalized, text)


def _normalize_astro_key(category: str, key: str) -> str:
    text = (key or "").strip()
    if category == "house":
        return _normalize_house_key(text)
    if category == "aspect":
        return text
    reverse_labels = {label: name for name, label in ASTRO_LABELS.items()}
    return reverse_labels.get(text, text)


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
        tip_text = tip.strip()
        if not tip_text:
            continue
        if tip_text == "==":
            lines.append("")
            continue
        lines.append(f"- {tip_text}")
    return "\n".join(lines).strip()


def _build_liureng_house_entry(
    bundle: KnowledgeBundle, jiang_name: str, tian_branch: str, di_branch: str
) -> dict[str, Any]:
    aliases = bundle.get("jiang_aliases", {})
    jiang_info = bundle.get("jiang_info", {})
    jiang_branch_note = bundle.get("jiang_branch_note", {})
    normalized_name = aliases.get(jiang_name, jiang_name)
    general_spirit = jiang_info.get(normalized_name)
    if not general_spirit:
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
    tips.extend(general_spirit.get("intros", []))
    for line in general_spirit.get("verses", []):
        tips.append(f"**{line}**")
    tips.extend(general_spirit.get("extra", []))
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
        if name != "liureng":
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
                "source": (
                    RULE_REFERENCE_SOURCE
                    if name in RULE_REFERENCE_DOMAINS
                    else "xingque_hover_docs"
                ),
                **(
                    {}
                    if name in RULE_REFERENCE_DOMAINS
                    else {"bundle_version": index.get("bundle_version")}
                ),
                "provenance": _knowledge_provenance(domain=name),
                "categories": categories,
            }
        )
    if domain in RULE_REFERENCE_DOMAINS:
        return {
            "source": RULE_REFERENCE_SOURCE,
            "provenance": _knowledge_provenance(domain=domain),
            "domains": result_domains,
        }
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


def _autoresolve_bare_category(
    domain: str, categories: Mapping[str, dict[str, KnowledgeCard]], lookup_key: str
) -> str:
    """Resolve a key against the complete category inventory for its domain."""
    if not categories:
        raise ToolValidationError(
            f"Category is required for domain '{domain}'",
            code=f"knowledge.{domain}.category_required",
            details={"domain": domain},
        )
    candidate_categories: list[str] = []
    for category, entries in categories.items():
        if domain == "astro":
            normalized_key = _normalize_astro_key(category, lookup_key)
        elif domain == "qimen":
            normalized_key = _normalize_qimen_key(category, lookup_key)
        else:
            normalized_key = lookup_key
        if normalized_key in entries:
            candidate_categories.append(category)
    if len(candidate_categories) == 1:
        return candidate_categories[0]
    elif not candidate_categories:
        raise ToolValidationError(
            f"Unknown {domain} knowledge key: {lookup_key}",
            code=f"knowledge.{domain}.unknown_key",
            details={
                "key": lookup_key,
                "available_categories": [name for name in sorted(categories)],
            },
        )
    else:
        raise ToolValidationError(
            f"Ambiguous knowledge key '{lookup_key}' in domain '{domain}'; specify a category",
            code=f"knowledge.{domain}.ambiguous_key",
            details={
                "key": lookup_key,
                "candidate_categories": [name for name in candidate_categories],
            },
        )


def read_knowledge_entry(
    payload: Mapping[str, str | int | None],
) -> dict[str, Any]:
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
        category = _autoresolve_bare_category(
            domain, bundles[domain].get("categories", {}), key
        )
    if domain in RULE_REFERENCE_DOMAINS:
        bundle = bundles[domain]
        categories = bundle.get("categories", {})
        is_aspect = domain == "astro" and category == "aspect"
        if is_aspect and payload.get("aspect_degree") is not None:
            key = str(payload["aspect_degree"])
        normalizer = _normalize_astro_key if domain == "astro" else _normalize_qimen_key
        normalized_key = normalizer(category, key)
        entry = categories.get(category, {}).get(normalized_key)
        if not entry:
            raise ToolValidationError(
                f"Unknown {domain} knowledge key: {key}",
                code=f"knowledge.{domain}.unknown_key",
                details={
                    "category": category,
                    "key": key,
                    "normalized_key": normalized_key,
                },
            )
        query: dict[str, str | None] = {"key": normalized_key}
        title = entry["title"]
        tips = list(entry["tips"])
        if is_aspect:
            object_a = f"{payload.get('object_a') or ''}".strip()
            object_b = f"{payload.get('object_b') or ''}".strip()
            query.update(object_a=object_a or None, object_b=object_b or None)
            if object_a and object_b:
                first = ASTRO_LABELS.get(object_a, object_a)
                second = ASTRO_LABELS.get(object_b, object_b)
                title = f"{first} - {second}：{title}"
                tips.insert(0, f"对象：{first} 与 {second}")
        return {
            "domain": domain,
            "category": category,
            "key": normalized_key,
            "query_normalized": query,
            "title": title,
            "tips": tips,
            "lines": tips,
            "rendered_text": _tips_to_rendered_text(title, tips),
            "source": RULE_REFERENCE_SOURCE,
            "provenance": _knowledge_provenance(
                domain=domain, category=category, key=normalized_key
            ),
            "citation": entry["citation"],
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
        category_entries = categories.get(category, {})
        entry = category_entries.get(key)
        if not entry:
            raise ToolValidationError(
                f"Unknown 八字 knowledge key: {key}",
                code="knowledge.bazi.unknown_key",
                details={"category": category, "key": key},
            )
        tips = list(entry.get("tips", []))
        provenance = _knowledge_provenance(domain=domain, category=category, key=key)
        curation = entry.get("curation")
        if curation is not None:
            # note (knowledge cache): Readers must not be able to mutate the cached references.
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
                if curation is not None
                else f"FateBridge旧资料待逐条核对 · {domain}/{category}/{key}。"
            ),
        }

    raise ToolValidationError(
        f"Unknown knowledge domain: {domain}",
        code="knowledge.unknown_domain",
        details={"domain": domain},
    )
