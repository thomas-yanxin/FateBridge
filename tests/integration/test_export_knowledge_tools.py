import json

from fatebridge.services.export_tools import (
    calculate_export_parse,
    calculate_export_registry,
)
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from tests.fixtures.transports import mcp_text


def test_calculate_export_registry_matches_fatebridge_shape():
    result = calculate_export_registry(technique="qimen")

    assert result["settings_key"] == "fatebridge.ai.export.settings.v1"
    assert result["settings_version"] == 6
    assert result["selected_technique"]["key"] == "qimen"
    assert "奇门演卦" in result["selected_technique"]["preset_sections"]
    assert result["default_normalized_settings"]["sections"] == {}


def test_calculate_export_registry_includes_knowledge_and_ziwei_rules():
    registry = calculate_export_registry()
    selected = calculate_export_registry(technique="knowledge")
    registry_selected = calculate_export_registry(technique="knowledge_registry")

    technique_keys = {item["key"] for item in registry["techniques"]}

    assert "knowledge" in technique_keys
    assert "knowledge_registry" in technique_keys
    assert "ziwei_rules" in technique_keys
    assert selected["selected_technique"]["preset_sections"] == [
        "查询信息",
        "知识正文",
        "来源",
    ]
    assert registry_selected["selected_technique"]["preset_sections"] == [
        "目录概览",
        "astro",
        "liureng",
        "qimen",
        "来源",
    ]


def test_calculate_export_parse_uses_current_titles_and_filters_forbidden_sections():
    content = "\n".join(
        [
            "[起盘信息]",
            "排盘参数",
            "",
            "[右侧栏目]",
            "这里不该进入最终导出",
            "",
            "[八宫详解]",
            "这里是八宫详解内容",
            "",
            "[奇门演卦]",
            "这里是奇门演卦内容",
        ]
    )

    result = calculate_export_parse(
        technique="qimen",
        content=content,
        selected_sections=["起盘信息", "八宫详解", "奇门演卦"],
    )

    assert result["section_titles_detected"] == [
        "起盘信息",
        "右侧栏目",
        "八宫详解",
        "奇门演卦",
    ]
    assert result["selected_sections"] == ["起盘信息", "八宫详解", "奇门演卦"]
    assert "这里不该进入最终导出" not in result["export_text"]
    assert "这里是八宫详解内容" in result["export_text"]
    assert "这里是奇门演卦内容" in result["export_text"]
    assert result["settings_used"]["sections"]["qimen"] == [
        "起盘信息",
        "八宫详解",
        "奇门演卦",
    ]


def test_calculate_knowledge_registry_and_read_match_reference_samples():
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
    assert "[目录概览]" in registry["snapshot_text"]
    assert "[astro]" in registry["snapshot_text"]
    assert "[来源]" in registry["snapshot_text"]
    assert registry["snapshot_export"]["export_text"] == registry["snapshot_text"]
    assert liureng["title"] == "神后子神"
    assert "类象" in liureng["rendered_text"]
    assert qimen["key"] == "休门"
    assert "休养" in qimen["rendered_text"]
    assert astro["title"].startswith("太阳 - 木星")
    assert "相位角：90°" in astro["tips"]
    assert "[查询信息]" in qimen["snapshot_text"]
    assert "[知识正文]" in qimen["snapshot_text"]
    assert "[来源]" in qimen["snapshot_text"]
    assert qimen["snapshot_export"]["export_text"] == qimen["snapshot_text"]


def test_knowledge_read_auto_resolves_category_from_bare_key():
    # Bare key, no category: the formerly-failing 八字 case should now resolve.
    bazi = calculate_knowledge_read(domain="bazi", key="伤官见官")
    assert "error" not in bazi
    assert bazi["category"] == "education"
    assert bazi["key"] == "伤官见官"

    # Auto-resolution also works for astro and qimen flat-category domains.
    astro = calculate_knowledge_read(domain="astro", key="Mars")
    assert astro["category"] == "planet"
    qimen = calculate_knowledge_read(domain="qimen", key="休门")
    assert qimen["category"] == "door"

    # Explicit category still works (regression).
    explicit = calculate_knowledge_read(
        domain="bazi", category="education", key="伤官见官"
    )
    assert explicit["key"] == "伤官见官"


def test_knowledge_read_bare_key_ambiguous_and_unknown():
    # A key present in more than one category is reported as ambiguous, not
    # silently resolved to one of them.
    ambiguous = calculate_knowledge_read(domain="bazi", key="偏财")
    assert ambiguous["code"] == "knowledge.bazi.ambiguous_key"
    assert set(ambiguous["details"]["candidate_categories"]) == {"ten_gods", "wealth"}

    # A key in no category is unknown, with the available categories surfaced.
    unknown = calculate_knowledge_read(domain="bazi", key="不存在的词条")
    assert unknown["code"] == "knowledge.bazi.unknown_key"
    assert "education" in unknown["details"]["available_categories"]


def test_calculate_knowledge_registry_supports_selected_export_sections():
    result = calculate_knowledge_registry(
        selected_sections=["目录概览", "qimen"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["目录概览", "qimen"]
    assert "[目录概览]" in result["snapshot_export"]["export_text"]
    assert "[qimen]" in result["snapshot_export"]["export_text"]
    assert "[astro]" not in result["snapshot_export"]["export_text"]
    assert "[liureng]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_knowledge_registry_full_domain_order_matches_reference_order():
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
    # Original four-domain order and identities remain an exact prefix; the
    # added domains are source-bound references, not extra legacy hover data.
    assert [item["domain"] for item in registry["domains"][:4]] == [
        "astro",
        "bazi",
        "liureng",
        "qimen",
    ]
    assert all(
        item["source"] == "xingque_hover_docs" for item in registry["domains"][:4]
    )
    assert all(
        item["source"] == "fatebridge_numerology_references"
        for item in registry["domains"][4:6]
    )
    assert registry["domains"][6]["source"] == "fatebridge_human_design_line_references"


def test_export_and_knowledge_mcp_tools_return_json_strings():
    content = "\n".join(
        [
            "[起盘信息]",
            "排盘参数",
            "",
            "[八宫详解]",
            "这里是八宫详解内容",
            "",
            "[奇门演卦]",
            "这里是奇门演卦内容",
        ]
    )

    export_registry_result = json.loads(mcp_text("export_registry", technique="qimen"))
    export_parse_result = json.loads(
        mcp_text(
            "export_parse",
            technique="qimen",
            content=content,
            selected_sections=["起盘信息", "八宫详解", "奇门演卦"],
        )
    )
    knowledge_registry_result = json.loads(
        mcp_text(
            "knowledge_registry",
            domain="astro",
            selected_sections=["目录概览", "astro"],
        )
    )
    knowledge_read_result = json.loads(
        mcp_text(
            "knowledge_read",
            domain="qimen",
            category="door",
            key="休门",
            selected_sections=["知识正文"],
        )
    )

    assert export_registry_result["selected_technique"]["key"] == "qimen"
    assert "奇门演卦" in export_registry_result["selected_technique"]["preset_sections"]
    assert "这里是奇门演卦内容" in export_parse_result["export_text"]
    assert knowledge_registry_result["domains"][0]["domain"] == "astro"
    assert knowledge_registry_result["snapshot_export"]["selected_sections"] == [
        "目录概览",
        "astro",
    ]
    assert "[astro]" in knowledge_registry_result["snapshot_export"]["export_text"]
    assert knowledge_read_result["key"] == "休门"
    assert "休养" in knowledge_read_result["rendered_text"]
    assert knowledge_read_result["snapshot_export"]["selected_sections"] == ["知识正文"]
    assert "[知识正文]" in knowledge_read_result["snapshot_export"]["export_text"]
