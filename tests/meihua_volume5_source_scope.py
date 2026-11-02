"""Exact additive source scope; the old seasonal and guard bodies stay intact."""

import ast
from pathlib import Path

SEASONAL = "core/meihua_seasonal_reading.py"
NEW = {
    "core/meihua_volume5_strength.py",
    "data/meihua/volume5-four-state-nlc1925-v1.json",
}


def dump(node):
    return ast.dump(node, include_attributes=False)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assert_only_volume5_comparison_added(root, before_path):
    old = ast.parse(Path(before_path).read_bytes())
    current = ast.parse((Path(root) / SEASONAL).read_bytes())
    func = next(
        n
        for n in current.body
        if isinstance(n, ast.FunctionDef) and n.name == "build_seasonal_qualification"
    )
    for text in [
        "from .meihua_volume5_strength import build_volume5_strength_comparison",
        'result["volume5_table_comparison"] = build_volume5_strength_comparison(role_rows, seasonal)',
    ]:
        wanted = dump(ast.parse(text).body[0])
        found = [n for n in func.body if dump(n) == wanted]
        require(len(found) == 1, "Volume-five comparison insertion changed")
        func.body.remove(found[0])
    require(
        dump(old) == dump(current),
        "Existing seasonal AST changed beyond the one comparison insertion",
    )


def assert_old_iso_guard_body_preserved(current_path, before_path):
    old = ast.parse(Path(before_path).read_bytes())
    current = ast.parse(Path(current_path).read_bytes())
    funcs = [
        n
        for n in current.body
        if isinstance(n, ast.FunctionDef) and n.name == "reviewed_iso_clock_guards"
    ]
    expected = ast.parse(
        """def reviewed_iso_clock_guards(original_data, root, prior, previous):
    from tests.meihua_volume5_source_evolution import reviewed_volume5_guards
    return reviewed_volume5_guards(original_data, root, prior, previous, _reviewed_iso_clock_guards_v66)
"""
    ).body[0]
    require(
        len(funcs) == 1 and dump(funcs[0]) == dump(expected),
        "Volume-five guard wrapper widened",
    )
    current.body.remove(funcs[0])
    prior = [
        n
        for n in current.body
        if isinstance(n, ast.FunctionDef) and n.name == "_reviewed_iso_clock_guards_v66"
    ]
    require(len(prior) == 1, "Original v66 guard is missing")
    prior[0].name = "reviewed_iso_clock_guards"
    require(dump(old) == dump(current), "Original v66 guard body changed")
