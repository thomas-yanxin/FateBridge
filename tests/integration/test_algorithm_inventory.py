"""A schema declaration label must not hide a new own-body computation."""

import ast

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
def test_own_declaration_shape_has_an_explicit_boundary(source, expected):
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.ClassDef)
    assert is_field_declaration(node) is expected


def test_module_bindings_do_not_absorb_function_class_or_conditional_state():
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
    tmp_path, monkeypatch, role, symbol, anchor, expected
):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/sample.py").write_text(
        "TABLE = ('a', 'b')\ndef calculate():\n    return 1\n"
    )
    (tmp_path / "docs").mkdir()
    document = tmp_path / "docs/inventory.md"
    document.write_text(
        f"| {role} | 已声明职责（`{symbol}`） | "
        f"[sample](../src/sample.py#L{anchor}) | consumer | source | scope |\n"
    )
    monkeypatch.setattr(inventory, "INVENTORY", document)
    counts, issues = inventory.check_inventory(document)
    assert counts["source_groups"] == counts["unique_symbols"] == 1
    # This source fixture intentionally omits the separate live catalog prose.
    assert [issue for issue in issues if issue.startswith("line ")] == expected
