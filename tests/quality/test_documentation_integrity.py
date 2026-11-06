"""Exercise documentation checks with broken and valid authoring examples."""

from pathlib import Path

import pytest

from scripts import check_docs


def test_fences_do_not_create_headings_or_links():
    document = check_docs.inspect_markdown(
        '# 标题 `fields`\n\n```json\n{"sample": "[x](missing.md)"}\n```\n'
        "\n# 标题 `fields`\n`[literal](missing.md)`\n"
    )
    assert document.anchors == {"标题-fields", "标题-fields-1"}
    assert document.links == []
    assert document.json_blocks == 1
    assert document.errors == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("```json\n{bad}\n```", "invalid JSON"),
        ("~~~python\nprint('example')", "unclosed code fence"),
        ("````python\n```\n", "unclosed code fence"),
    ],
)
def test_invalid_fences_and_json_report_opening_line(text, expected):
    document = check_docs.inspect_markdown(text)
    assert document.errors[0].startswith("1:")
    assert expected in document.errors[0]


def test_local_links_encoded_paths_and_badges(tmp_path, monkeypatch):
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
    tmp_path, monkeypatch, capsys, text, expected
):
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
def test_invalid_example_json_fails(tmp_path, monkeypatch, capsys, name):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    example: Path = tmp_path / name
    example.parent.mkdir(parents=True)
    example.write_text("{broken}", encoding="utf-8")
    assert check_docs.main([]) == 1
    assert f"{name}: invalid JSON" in capsys.readouterr().out


def test_configuration_and_interpretation_docs_are_checked(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    for name in (
        "configs/scenarios/README.md",
        "docs/interpretation/shared/reference.md",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[retired entry](missing.md)\n", encoding="utf-8")
    assert check_docs.main([]) == 1
    output = capsys.readouterr().out
    assert "configs/scenarios/README.md:1: missing local target" in output
    assert "docs/interpretation/shared/reference.md:1: missing local target" in output


def test_current_links_to_missing_historical_files_or_anchors_still_fail(
    tmp_path, monkeypatch, capsys
):
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


def test_reference_links_and_multiline_html_keep_source_locations():
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
def test_missing_html_and_reference_assets_fail(tmp_path, monkeypatch, text):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(text, encoding="utf-8")
    assert check_docs.main([]) == 1
