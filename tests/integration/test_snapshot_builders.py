"""锁定 service 层共享快照原语的契约。

这些函数由十余个 service 模块复用（见 ``snapshot_builders``），其换行/空行
规则直接决定 ``snapshot_text`` 输出，进而影响 golden 快照。本测试把规则固化为
直接断言，作为 golden 之外的第二道防线。
"""

from fatebridge.services.snapshot_builders import (
    build_snapshot_export,
    render_snapshot_lines,
    render_snapshot_text,
)


class TestRenderSnapshotText:
    def test_blocks_separated_by_blank_line(self) -> None:
        out = render_snapshot_text([("起盘", "甲子"), ("断语", "吉")])
        assert out == "[起盘]\n甲子\n\n[断语]\n吉"

    def test_empty_body_renders_title_only(self) -> None:
        out = render_snapshot_text([("空", "   "), ("有", "x")])
        assert out == "[空]\n\n[有]\nx"

    def test_single_section(self) -> None:
        assert render_snapshot_text([("唯一", "内容")]) == "[唯一]\n内容"


class TestRenderSnapshotLines:
    def test_lines_joined_within_block(self) -> None:
        out = render_snapshot_lines([("段", ["第一行", "第二行"]), ("尾", ["末"])])
        assert out == "[段]\n第一行\n第二行\n\n[尾]\n末"

    def test_none_lines_dropped(self) -> None:
        out = render_snapshot_lines([("段", ["有", None, "效"])])
        assert out == "[段]\n有\n效"

    def test_empty_block_keeps_title_only(self) -> None:
        out = render_snapshot_lines([("空", []), ("满", ["x"])])
        assert out == "[空]\n\n[满]\nx"


def test_string_and_lines_agree_on_equivalent_input() -> None:
    """同样的内容，字符串正文与单行列表正文应得到一致输出。"""
    text = render_snapshot_text([("a", "1"), ("b", "2")])
    lines = render_snapshot_lines([("a", ["1"]), ("b", ["2"])])
    assert text == lines == "[a]\n1\n\n[b]\n2"


def test_build_snapshot_export_delegates_to_parser() -> None:
    snap = render_snapshot_text([("起盘信息", "样例")])
    export = build_snapshot_export(technique="qimen", snapshot_text=snap)
    assert export["technique"]["key"] == "qimen"
    assert "起盘信息" in export["export_text"]


def test_export_omits_text_duplicates() -> None:
    """``snapshot_export`` 不再回携 ``raw_text``/``filtered_text``。

    ``raw_text`` 恒等于顶层 ``snapshot_text``，``filtered_text`` 的语义已由
    ``export_text``（含安全回退）+ 各 section 的 ``included`` 标记完整覆盖。两者
    都是纯重复，移除后每次工具响应可省下一到两份正文（西占盘 ~13%）。
    """
    from fatebridge.core.export_parser import parse_export_content

    snap = render_snapshot_text([("起盘信息", "样例"), ("断语", "吉")])
    export = parse_export_content(technique="qimen", content=snap)

    # 被刻意移除的重复键
    assert "raw_text" not in export
    assert "filtered_text" not in export

    # 被保留的、真正被消费的导出文本不受影响
    assert export["export_text"]
    # section 的 included 标记仍承载“严格过滤命中与否”的信号
    assert all("included" in section for section in export["sections"])


def test_export_section_omits_derivable_body() -> None:
    """各 section 只保留 ``content``（含 ``[标题]`` 头），不再双存 ``body``。

    ``content`` 是渲染层 (render_sections_to_text) 的唯一数据源、且承载
    ``export_text`` 所需的小节标题；``body`` 仅是 ``content`` 去掉首行标题，可派生
    且无任何消费者。删去 ``body`` 再省一份小节正文（西占盘 ~8%）。
    """
    from fatebridge.core.export_parser import parse_export_content

    snap = render_snapshot_text([("起盘信息", "样例正文"), ("断语", "吉")])
    export = parse_export_content(technique="qimen", content=snap)

    sections = export["sections"]
    assert sections, "应至少解析出一个 section"
    for section in sections:
        assert "body" not in section
        assert "content" in section
        # content 仍带 [标题] 头，保证 export_text 拼接出的小节标题不丢
        assert section["raw_title"] in section["content"]
    # 标题头进入了导出文本（与既有 export_text 契约一致）
    assert "[起盘信息]" in export["export_text"]
    assert "样例正文" in export["export_text"]
