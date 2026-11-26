from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from tests.fixtures.transports import mcp_payload


def test_calculate_knowledge_registry_and_read_match_reference_samples() -> None:
    registry = calculate_knowledge_registry(domain="astro")
    liureng = calculate_knowledge_read(domain="liureng", category="shen", key="子")
    qimen = calculate_knowledge_read(domain="qimen", category="door", key="休门")
    astro = calculate_knowledge_read(
        domain="astro",
        category="aspect",
        aspect_degree=90,
        object_a="Sun",
        object_b="Jupiter",
    )

    assert registry["domains"][0]["domain"] == "astro"
    assert any(
        category["name"] == "planet"
        for category in registry["domains"][0]["categories"]
    )
    assert "snapshot_text" not in registry and "snapshot_export" not in registry
    assert liureng["title"] == "神后子神"
    assert "类象" in liureng["rendered_text"]
    assert qimen["key"] == "休门"
    assert "休门属水，本宫为坎" in qimen["rendered_text"]
    assert "卷二·门迫宫迫" in qimen["citation"]
    assert astro["title"].startswith("太阳 - 木星")
    assert "相位角：90°" in astro["tips"]
    assert "snapshot_text" not in qimen and "snapshot_export" not in qimen


def test_knowledge_read_auto_resolves_category_from_bare_key() -> None:
    """A unique bare key resolves to its registered category."""
    bazi = calculate_knowledge_read(domain="bazi", key="伤官见官")
    assert "error" not in bazi
    assert bazi["category"] == "education"
    assert bazi["key"] == "伤官见官"

    # Auto-resolution also works for astro and qimen flat-category domains.
    astro = calculate_knowledge_read(domain="astro", key="Mars")
    assert astro["category"] == "planet"
    assert astro["lines"] == ["入庙：白羊、天蝎", "擢升：摩羯"]
    qimen = calculate_knowledge_read(domain="qimen", key="休门")
    assert qimen["category"] == "door"

    # Explicit category still works (regression).
    explicit = calculate_knowledge_read(
        domain="bazi", category="education", key="伤官见官"
    )
    assert explicit["key"] == "伤官见官"


def test_knowledge_read_bare_key_ambiguous_and_unknown() -> None:
    # A key present in more than one category is reported as ambiguous, not
    # silently resolved to one of them.
    ambiguous = calculate_knowledge_read(domain="bazi", key="偏财")
    assert ambiguous["code"] == "knowledge.bazi.ambiguous_key"
    assert set(ambiguous["details"]["candidate_categories"]) == {"ten_gods", "wealth"}

    # A key in no category is unknown, with the available categories surfaced.
    unknown = calculate_knowledge_read(domain="bazi", key="不存在的词条")
    assert unknown["code"] == "knowledge.bazi.unknown_key"
    retired = calculate_knowledge_read(domain="astro", category="planet", key="Uranus")
    assert retired["code"] == "knowledge.astro.unknown_key"
    assert "education" in unknown["details"]["available_categories"]


def test_knowledge_registry_full_domain_order_matches_reference_order() -> None:
    registry = calculate_knowledge_registry()

    assert [item["domain"] for item in registry["domains"]] == [
        "astro",
        "bazi",
        "liureng",
        "qimen",
        "heluo",
        "canping",
        "human_design",
    ]
    sources = {item["domain"]: item["source"] for item in registry["domains"]}
    assert sources["astro"] == sources["qimen"] == "fatebridge_rule_references"
    assert sources["bazi"] == sources["liureng"] == "xingque_hover_docs"
    assert all(
        item["source"] == "fatebridge_numerology_references"
        for item in registry["domains"][4:6]
    )
    assert registry["domains"][6]["source"] == "fatebridge_human_design_line_references"


def test_knowledge_mcp_tools_return_structured_payloads() -> None:
    knowledge_registry_result = mcp_payload("knowledge_catalog", domain="astro")
    knowledge_read_result = mcp_payload(
        "knowledge_read",
        domain="qimen",
        category="door",
        key="休门",
    )

    assert knowledge_registry_result["domains"][0]["domain"] == "astro"
    assert knowledge_read_result["key"] == "休门"
    assert "休门属水，本宫为坎" in knowledge_read_result["rendered_text"]
