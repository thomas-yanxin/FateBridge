"""A schema declaration label must not hide a new own-body computation."""

import ast
from pathlib import Path

import pytest

import scripts.check_algorithm_inventory as inventory
from scripts.check_algorithm_inventory import is_field_declaration


@pytest.mark.parametrize(
    "source,expected",
    [
        ("class Fact(Base):\n    value: str | None = None", True),
        ("class Fact(Base):\n    value: int", True),
        (
            "class Fact(Base):\n    value: int | None = Field(None, ge=-1, json_schema_extra={'present': True})",
            True,
        ),
        ("class Fact(Base):\n    pass", True),
        ("class Fact(Base):\n    'Only a declaration.'", True),
        (
            "class Fact(Base):\n    value: Annotated[bool, BeforeValidator(check)] = None",
            True,
        ),  # Annotation/inherited validators remain separate executable duties.
        ("class Fact(Base):\n    def calculate(self):\n        return 1", False),
        ("class Fact(Base):\n    value: int = calculate()", False),
        ("class Fact(Base):\n    value: int = Field(default_factory=calculate)", False),
        ("class Fact(Base):\n    value: int = Field(**options)", False),
        ("class Fact(Base):\n    value = None", False),
        ("@decorate\nclass Fact(Base):\n    value: str | None = None", False),
        ("class Fact(Base, metaclass=Custom):\n    value: int", False),
        ("class Fact(Base):\n    values.item: int", False),
    ],
)
def test_own_declaration_shape_has_an_explicit_boundary(
    source: str, expected: bool
) -> None:
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.ClassDef)
    assert is_field_declaration(node) is expected


def test_module_bindings_do_not_absorb_function_class_or_conditional_state() -> None:
    source = (
        "TABLE = ('a', 'b')\n"
        "Name: str\n"
        "class Fact:\n"
        "    field = 1\n"
        "def calculate():\n"
        "    local = 2\n"
        "if enabled:\n"
        "    conditional = 3\n"
    )
    assert inventory.module_bindings(ast.parse(source)) == {"TABLE": 1, "Name": 2}


@pytest.mark.parametrize(
    "role,symbol,anchor,expected",
    [
        ("模块规则与配置：表", "TABLE", 1, []),
        ("模块规则与配置：表", "TABLE", None, []),
        (
            "计算函数",
            "TABLE",
            1,
            ["line 1: missing ../src/sample.py::TABLE"],
        ),
        (
            "模块规则与配置：表",
            "TABLE",
            2,
            ["line 1: TABLE anchor L2 != L1"],
        ),
        (
            "模块规则与配置：表",
            "calculate",
            2,
            ["line 1: missing ../src/sample.py::calculate"],
        ),
    ],
)
def test_module_rows_keep_their_role_and_source_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    symbol: str,
    anchor: int | None,
    expected,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/sample.py").write_text(
        "TABLE = ('a', 'b')\ndef calculate():\n    return 1\n"
    )
    (tmp_path / "docs").mkdir()
    document = tmp_path / "docs/inventory.md"
    fragment = f"#L{anchor}" if anchor is not None else ""
    document.write_text(
        f"| {role} | 已声明职责（`{symbol}`） | "
        f"[sample](../src/sample.py{fragment}) | consumer | source | scope |\n"
    )
    monkeypatch.setattr(inventory, "INVENTORY", document)
    counts, issues = inventory.check_inventory(document)
    assert counts["source_groups"] == counts["unique_symbols"] == 1
    # This source fixture intentionally omits the separate live catalog prose.
    assert [issue for issue in issues if issue.startswith("line ")] == expected


def test_unreviewed_queue_preserves_real_source_identities(tmp_path: Path) -> None:
    source_root = tmp_path / "src/fatebridge"
    source_root.mkdir(parents=True)
    (source_root / "sample.py").write_text(
        '"Module documentation."\n'
        "import external\n"
        "TABLE = ('old',)\n"
        "TABLE = ('current',)\n"
        "VALUE: int\n"
        "class Holder:\n"
        "    @property\n"
        "    def value(self):\n"
        "        return 1\n"
        "    @value.setter\n"
        "    def value(self, new):\n"
        "        pass\n"
        "def covered():\n"
        "    return 2\n"
        "if enabled:\n"
        "    def conditional():\n"
        "        return 3\n"
        "    state = 4\n"
        "touch()\n"
    )
    (tmp_path / "docs").mkdir()
    document = tmp_path / "docs/inventory.md"
    document.write_text(
        "| 模块规则与配置：表 | 已读（`TABLE`） | "
        "[source](../src/fatebridge/sample.py#L4) | consumer | source | scope |\n"
        "| 计算 | 已读（`covered`） | "
        "[source](../src/fatebridge/sample.py#L13) | consumer | source | scope |\n"
    )

    report = inventory.unreviewed_inventory(document, source_root)

    assert [(item["symbol"], item["line"]) for item in report["definitions"]] == [
        ("Holder", 6),
        ("Holder.value", 8),
        ("Holder.value", 11),
        ("conditional", 16),
    ]
    assert [(item["symbol"], item["line"]) for item in report["module_bindings"]] == [
        ("TABLE", 3),
        ("VALUE", 5),
    ]
    assert [(item["kind"], item["line"]) for item in report["module_statements"]] == [
        ("Assign", 3),
        ("AnnAssign", 5),
        ("If", 15),
        ("Expr", 19),
    ]
    assert all(
        item["path"] == "src/fatebridge/sample.py"
        for records in report.values()
        for item in records
    )
