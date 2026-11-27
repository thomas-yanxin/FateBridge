"""Exercise documentation checks with broken and valid authoring examples."""

import json
from pathlib import Path

import pytest

from fatebridge.services.tool_catalog import CATALOG
from scripts import check_docs


def test_fences_do_not_create_headings_or_links() -> None:
    document = check_docs.inspect_markdown(
        '# 标题 `fields`\n\n```json\n{"sample": "[x](missing.md)"}\n```\n'
        "\n# 标题 `fields`\n`[literal](missing.md)`\n"
    )
    assert document.anchors == {"标题-fields", "标题-fields-1"}
    assert document.links == []
    assert document.json_blocks == 1
    assert document.errors == []


def test_explicit_html_ids_are_link_targets_outside_literal_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(
        '[section](#source-axis)\n<a\n id="source-axis"></a>\n'
        '<h2 id="named-heading">Heading</h2>\n'
        '`<a id="inline-code"></a>`\n'
        '```html\n<a id="fenced-code"></a>\n```\n',
        encoding="utf-8",
    )
    document = check_docs.inspect_markdown((tmp_path / "README.md").read_text())
    assert document.anchors == {"source-axis", "named-heading"}
    assert check_docs.main([]) == 0
    with (tmp_path / "README.md").open("a", encoding="utf-8") as stream:
        stream.write("[literal](#fenced-code)\n")
    assert check_docs.main([]) == 1


@pytest.mark.parametrize(
    "text,expected",
    [
        ("```json\n{bad}\n```", "invalid JSON"),
        ("~~~python\nprint('example')", "unclosed code fence"),
        ("````python\n```\n", "unclosed code fence"),
    ],
)
def test_invalid_fences_and_json_report_opening_line(text: str, expected: str) -> None:
    document = check_docs.inspect_markdown(text)
    assert document.errors[0].startswith("1:")
    assert expected in document.errors[0]


def test_local_links_encoded_paths_and_badges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(
        "[part](docs/a%20b.md#标题-fields)\n"
        "[duplicate](docs/a%20b.md#标题-fields-1)\n"
        "[![badge](https://example.com/badge.svg)](LICENSE)\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a b.md").write_text(
        "# 标题 `fields`\n\n# 标题 `fields`\n", encoding="utf-8"
    )
    (tmp_path / "LICENSE").touch()
    monkeypatch.chdir(tmp_path.parent)
    assert check_docs.main([]) == 0


@pytest.mark.parametrize(
    "text,expected",
    [
        ("[missing](missing.md)", "missing local target"),
        ("[anchor](#absent)", "missing heading anchor"),
        ("[![badge](https://example.com/b.svg)](absent)", "missing local target"),
    ],
)
def test_broken_links_fail_with_source_location(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    text: str,
    expected: str,
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(text, encoding="utf-8")
    assert check_docs.main([]) == 1
    assert f"README.md:1: {expected}" in capsys.readouterr().out


@pytest.mark.parametrize(
    "name",
    [
        "docs/examples/broken.json",
        "docs/examples/study/broken.json",
        "examples/study/broken.json",
    ],
)
def test_invalid_example_json_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    example: Path = tmp_path / name
    example.parent.mkdir(parents=True)
    example.write_text("{broken}", encoding="utf-8")
    assert check_docs.main([]) == 1
    assert f"{name}: invalid JSON" in capsys.readouterr().out


def test_interpretation_docs_are_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    path = tmp_path / "docs/interpretation/shared/reference.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[retired entry](missing.md)\n", encoding="utf-8")
    assert check_docs.main([]) == 1
    output = capsys.readouterr().out
    assert "docs/interpretation/shared/reference.md:1: missing local target" in output


def test_current_links_to_missing_historical_files_or_anchors_still_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    archive = tmp_path / "docs/validation"
    archive.mkdir(parents=True)
    (archive / "report.md").write_text("# 存在的标题\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[缺文件](docs/validation/missing.md)\n"
        "[缺标题](docs/validation/report.md#absent)\n",
        encoding="utf-8",
    )
    assert check_docs.main([]) == 1
    output = capsys.readouterr().out
    assert "missing local target" in output
    assert "missing heading anchor" in output


def test_reference_links_and_multiline_html_keep_source_locations() -> None:
    document = check_docs.inspect_markdown(
        "[guide][Getting Started]\n![logo][logo]\n[logo][]\n"
        '<a\n href="docs/start.md#setup">Start</a>\n'
        '<img src="images/logo.png">\n'
        '```html\n<img src="not-an-asset.png">\n```\n'
        '[getting started]: <docs/start.md#setup> "Setup"\n'
        "[logo]: images/logo.png\n[missing][unknown]\n"
    )
    assert document.links == [
        (4, "docs/start.md#setup"),
        (6, "images/logo.png"),
        (1, "docs/start.md#setup"),
        (2, "images/logo.png"),
        (3, "images/logo.png"),
    ]
    assert document.errors == ["12: undefined link reference: unknown"]


@pytest.mark.parametrize(
    "text",
    ['<img src="missing.png">', "[logo][asset]\n\n[asset]: missing.png"],
)
def test_missing_html_and_reference_assets_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(text, encoding="utf-8")
    assert check_docs.main([]) == 1


EXAMPLE_TOOL_MAP = {
    "examples/demo-subject.json": "astrology_chart",
    "docs/examples/fengshui-home.json": "fengshui_assess",
    "docs/examples/fengshui-xuankong.json": "fengshui_xuankong_house_chart",
    "docs/examples/liuyao-conditional-demo.json": "liuyao",
}

RETIRED_DOC_SYMBOLS = (
    "discover_capabilities",
    "describe_capability",
    "read_result",
    "detail=standard",
    'detail="standard"',
    "selected_sections",
    "snapshot_export",
    "result_delivery",
    "projection_warnings",
    "desktop_bagua_btb_v1",
    "user_expert_policy_v1",
    "workstation_layout",
    "surface_layouts",
    "environmental_context",
    "analysis_progress",
    "unsupported_queries",
)


def test_example_json_files_validate_against_live_request_models() -> None:
    """Every published JSON example maps to a live tool and validates cleanly."""
    root = check_docs.ROOT
    discovered = {
        path.relative_to(root).as_posix()
        for folder in (root / "examples", root / "docs" / "examples")
        for path in folder.rglob("*.json")
    }
    assert discovered == set(EXAMPLE_TOOL_MAP)
    specs = {spec.name: spec for spec in CATALOG}
    for rel_path, tool_name in sorted(EXAMPLE_TOOL_MAP.items()):
        payload = json.loads((root / rel_path).read_text(encoding="utf-8"))
        specs[tool_name].request_model.model_validate(payload)


def test_maintained_docs_contain_no_retired_api_symbols() -> None:
    """Maintained Markdown pages must not reintroduce retired APIs or fields."""
    hits: list[str] = []
    for path in check_docs.markdown_paths():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(check_docs.ROOT)
        for symbol in RETIRED_DOC_SYMBOLS:
            if symbol in text:
                hits.append(f"{rel}: {symbol}")
    assert not hits, "Found retired symbols in maintained docs:\n" + "\n".join(hits)
