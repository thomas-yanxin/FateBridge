"""场景路由文档必须恰好覆盖 CATALOG 全部工具——防止新增工具变成无场景归属的『闲置工具』。"""

import pathlib
import re

from fatebridge.services.tool_catalog import CATALOG

DOC = (
    pathlib.Path(__file__).resolve().parents[1].parent / "docs" / "scenario-routing.md"
)


def _checklist_keys() -> set[str]:
    text = DOC.read_text(encoding="utf-8")
    assert "## 覆盖核对清单" in text, "scenario-routing.md 缺少『覆盖核对清单』节"
    section = text.split("## 覆盖核对清单", 1)[1]
    return set(re.findall(r"^- `([a-z0-9_]+)`", section, re.MULTILINE))


def test_checklist_covers_every_catalog_tool_exactly():
    listed = _checklist_keys()
    catalog = {spec.key for spec in CATALOG}
    missing = catalog - listed  # 工具存在但清单漏登记 = 新孤儿
    extra = listed - catalog  # 清单写了不存在的工具 = 笔误/已删
    assert not missing, f"未在场景路由清单登记的工具（闲置风险）: {sorted(missing)}"
    assert not extra, f"清单里存在但 CATALOG 已无的工具: {sorted(extra)}"


def test_checklist_has_no_duplicate_keys():
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## 覆盖核对清单", 1)[1]
    keys = re.findall(r"^- `([a-z0-9_]+)`", section, re.MULTILINE)
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert not dupes, f"清单中有重复工具: {dupes}"


# 裸 MCP/REST 接入的 Agent 只读 ToolSpec.summary（不读本路由文档），所以最易闲置的
# 长尾「问事 / 数算」族工具，其 summary 必须自带「何时调 / 区别于哪个」的路由信号，
# 否则 §C.7 的取舍写得再好，机读层依然把它们当无差别的「X分析」。
ROUTING_SIGNAL_REQUIRED = {
    "meihua_analysis",
    "sixyao",
    "qimen",
    "taiyi",
    "jinkou",
    "suzhan",
    "sanshiunited",
    "liureng_gods",
    "liureng_runyear",
    "tongshefa",
    "canping",
    "heluo",
}


def test_longtail_summaries_carry_routing_signal():
    specs = {spec.key: spec for spec in CATALOG}
    offenders = []
    for key in sorted(ROUTING_SIGNAL_REQUIRED):
        summary = specs[key].summary or ""
        # 路由信号 = 一个「何时用 / 对比其他工具」的从句，而非裸「X分析。」
        has_clause = ("：" in summary or "；" in summary) and len(summary) >= 24
        if not has_clause:
            offenders.append((key, summary))
    assert not offenders, (
        "这些长尾工具的 summary 仍是空洞一行、缺路由信号（裸 MCP agent 无法路由）: "
        f"{offenders}"
    )


def _section_c_present_names() -> set[str]:
    """场景路由矩阵正文里精确出现（表格单元或注释行均可）的 catalog 工具名集合。"""
    text = DOC.read_text(encoding="utf-8")
    cbody = text.split("## 场景路由矩阵", 1)[1].split("## 长尾与专家级工具", 1)[0]
    callable_names = set()
    for spec in CATALOG:
        callable_names.add(spec.key)
        if getattr(spec, "mcp_name", None):
            callable_names.add(spec.mcp_name)
    present = set()
    for tok in re.findall(r"[a-z][a-z0-9_]*", cbody):
        if tok in callable_names:
            present.add(tok)
    return present


def _section_d_e_key_names() -> set[str]:
    """长尾与专家级工具 + 支撑与元工具 两节中出现的 catalog key 集合。
    这些工具不要求进场景路由矩阵正文。"""
    text = DOC.read_text(encoding="utf-8")
    if "## 长尾与专家级工具" not in text:
        return set()
    d_e_body = text.split("## 长尾与专家级工具", 1)[1].split("## 覆盖核对清单", 1)[0]
    callable_keys = {spec.key for spec in CATALOG}
    exempt: set[str] = set()
    for tok in re.findall(r"`([a-z][a-z0-9_]*)`", d_e_body):
        if tok in callable_keys:
            exempt.add(tok)
    return exempt


def test_every_section_c_tool_appears_in_section_c_body():
    """场景路由矩阵覆盖守护：CATALOG 中不属于长尾/支撑的工具，必须出现在
    场景路由矩阵正文某处（表格单元或文字注释）；否则 Agent 读矩阵时看不到＝闲置。
    REST/MCP 孪生工具共享 operation_label_zh，任一出现即视为该能力已路由。"""
    present = _section_c_present_names()
    exempt = _section_d_e_key_names()  # 长尾/支撑工具不要求进矩阵
    present_labels = {
        spec.operation_label_zh
        for spec in CATALOG
        if spec.key in present or getattr(spec, "mcp_name", None) in present
    }
    missing = []
    for spec in CATALOG:
        if spec.key in exempt:
            continue
        names = {spec.key, getattr(spec, "mcp_name", None)}
        if names & present:
            continue
        if spec.operation_label_zh in present_labels:
            continue
        missing.append(spec.key)
    assert not missing, (
        "这些工具在场景路由清单登记，却没出现在场景路由矩阵正文中"
        f"（Agent 读表看不到＝闲置）: {sorted(missing)}"
    )


def test_doc_notes_mcp_name_when_it_differs_from_key():
    """key≠mcp_name 的工具（如西占流派盘），其 MCP 名必须在文档里注明，
    否则技能照 §C 表抄 key 喂 MCP 会 unknown_tool。"""
    text = DOC.read_text(encoding="utf-8")
    missing = []
    for spec in CATALOG:
        mcp = getattr(spec, "mcp_name", None)
        if mcp and mcp != spec.key and mcp not in text:
            missing.append((spec.key, mcp))
    assert not missing, (
        "key≠mcp_name 的工具，其 MCP 名未在 scenario-routing.md 注明（照表抄名会失败）: "
        f"{sorted(missing)}"
    )
