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
    assert check_docs.main() == 0


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
    assert check_docs.main() == 1
    assert f"README.md:1: {expected}" in capsys.readouterr().out


def test_invalid_example_json_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    examples: Path = tmp_path / "docs" / "examples"
    examples.mkdir(parents=True)
    (examples / "broken.json").write_text("{broken}", encoding="utf-8")
    assert check_docs.main() == 1
    assert "docs/examples/broken.json: invalid JSON" in capsys.readouterr().out
