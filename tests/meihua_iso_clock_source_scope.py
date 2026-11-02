"""Preserve old predicates while changing only timestamp decoding calls."""

import ast
from pathlib import Path

APP_PATH = "application/meihua_clock_binding.py"
CORE_PATH = "core/meihua_clock_iso.py"


def dump(node):
    return ast.dump(node, include_attributes=False)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assert_only_clock_label_decoder_changed(root, before_path):
    current = ast.parse((Path(root) / APP_PATH).read_bytes())
    old = ast.parse(Path(before_path).read_bytes())
    target = dump(
        ast.parse(
            "from fatebridge.core.meihua_clock_iso import parse_meihua_clock_label"
        ).body[0]
    )
    imports = [n for n in current.body if dump(n) == target]
    require(len(imports) == 1, "Clock ISO decoder import changed")
    current.body.remove(imports[0])
    civil = [
        n
        for n in current.body
        if isinstance(n, ast.ImportFrom) and n.module == "fatebridge.utils.civil_clock"
    ]
    expected = ast.parse(
        "from fatebridge.utils.civil_clock import format_utc_offset, resolve_civil_clock, utc_instant"
    ).body[0]
    require(
        len(civil) == 1 and dump(civil[0]) == dump(expected),
        "Clock ISO civil imports changed",
    )
    civil[0].names.insert(1, ast.alias(name="parse_iso_datetime", asname=None))
    for name, after, before in [
        (
            "require_meihua_clock_binding",
            'nominal = parse_meihua_clock_label(clock["local_datetime"])',
            'nominal = datetime.fromisoformat(clock["local_datetime"])',
        ),
        (
            "_clock_datetime",
            "parsed = parse_meihua_clock_label(value)",
            "parsed = parse_iso_datetime(value)",
        ),
    ]:
        func = next(
            n for n in current.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        wanted = dump(ast.parse(after).body[0])
        found = [n for n in func.body if dump(n) == wanted]
        require(
            len(found) == 1,
            "Fractional parser call changed outside declared ISO decoder: " + name,
        )
        func.body[func.body.index(found[0])] = ast.parse(before).body[0]
    require(
        dump(current) == dump(old),
        "Preexisting clock binding AST changed beyond the two decoder calls",
    )


def assert_prior_fractional_helper_preserved(current_path, before_path):
    current = ast.parse(Path(current_path).read_bytes())
    old = ast.parse(Path(before_path).read_bytes())
    wrappers = [
        n
        for n in current.body
        if isinstance(n, ast.FunctionDef) and n.name == "reviewed_fractional_guards"
    ]
    expected = ast.parse("""def reviewed_fractional_guards(original_data, root, prior):
    from tests.meihua_iso_clock_source_evolution import reviewed_iso_clock_guards
    return reviewed_iso_clock_guards(original_data, root, prior, _reviewed_fractional_guards_v65)
""").body[0]
    require(
        len(wrappers) == 1 and dump(wrappers[0]) == dump(expected),
        "Clock ISO guard wrapper widened",
    )
    current.body.remove(wrappers[0])
    previous = [
        n
        for n in current.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "_reviewed_fractional_guards_v65"
    ]
    require(len(previous) == 1, "Prior fractional guard is missing")
    previous[0].name = "reviewed_fractional_guards"
    require(dump(current) == dump(old), "Prior fractional guard body changed")
