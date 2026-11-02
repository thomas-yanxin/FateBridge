"""A portable label decoder cannot erase raw old failures or weaken binding."""

import ast
import json
import shutil
from pathlib import Path

import pytest

from tests import meihua_fractional_source_evolution as fractional
from tests import meihua_iso_clock_source_evolution as iso
from tests import meihua_source_evolution_reference as evolution
from tests.meihua_guard_originals import historical_package_root
from tests.meihua_iso_clock_source_scope import (
    APP_PATH,
    CORE_PATH,
    assert_only_clock_label_decoder_changed,
    assert_prior_fractional_helper_preserved,
)
from tests.test_meihua_source_evolution import FROZEN, clone_package


def test_raw_v65_rejection_is_retained_while_the_complete_scope_expands():
    data = iso.load()
    raw = json.loads((iso.FOLDER / "original-v65-source-guards.json").read_bytes())
    assert raw["before"] == {"passed": True, "full": 124, "named": 30}
    assert not raw["after_before_guard_transition"]["passed"]
    assert not data["raw_v65_source_guard_relabelled_passed"]
    root = historical_package_root()
    full, named = evolution.reviewed_source_guards(FROZEN, root)
    assert len(full) == 127 and sum(map(len, named.values())) == 30
    assert {APP_PATH, CORE_PATH} <= full.keys()

    with pytest.raises(ValueError, match="Fractional source file changed"):
        fractional._reviewed_fractional_guards_v65(
            FROZEN, root, evolution._reviewed_source_guards_v64
        )


@pytest.mark.parametrize(
    "name", [APP_PATH, CORE_PATH, "utils/civil_clock.py", "core/requests/divination.py"]
)
def test_full_file_guards_reject_unreviewed_source(name, tmp_path):
    root = clone_package(tmp_path)
    file = root / name
    file.write_bytes(file.read_bytes() + b"\n# unreviewed\n")
    with pytest.raises(ValueError, match="source file changed"):
        evolution.reviewed_source_guards(FROZEN, root)


@pytest.mark.parametrize(
    "needle,replacement,error",
    [
        (
            'scope["calendar_stability"] != "not_assessed"',
            "False",
            "Preexisting clock binding AST",
        ),
        (
            "parsed = parse_meihua_clock_label(value)",
            "parsed = datetime.fromisoformat(value)",
            "Fractional parser call changed",
        ),
        (
            'nominal = parse_meihua_clock_label(clock["local_datetime"])',
            'nominal = datetime.fromisoformat(clock["local_datetime"])',
            "Fractional parser call changed",
        ),
    ],
)
def test_exact_two_call_scope_passes_before_rejecting_other_edits(
    needle, replacement, error, tmp_path
):
    root = clone_package(tmp_path)
    before = iso.INPUT_FOLDER / "before-binding.py"
    assert_only_clock_label_decoder_changed(root, before)
    file = root / APP_PATH
    source = file.read_text()
    assert needle in source
    file.write_text(source.replace(needle, replacement, 1))
    with pytest.raises(ValueError, match=error):
        assert_only_clock_label_decoder_changed(root, before)


def test_old_fractional_guard_body_cannot_be_weakened(tmp_path):
    from tests.meihua_guard_originals import original_helper

    current = original_helper("meihua_fractional_source_evolution.py")
    before = iso.FOLDER / "before-fractional-helper.py"
    assert_prior_fractional_helper_preserved(current, before)
    source = current.read_text()
    needle = "len(full) == 124 and sum(map(len, named.values())) == 30"
    assert needle in source
    file = tmp_path / "helper.py"
    file.write_text(source.replace(needle, "True", 1))
    with pytest.raises(ValueError, match="Prior fractional guard body changed"):
        assert_prior_fractional_helper_preserved(file, before)


@pytest.mark.parametrize(
    "name",
    [
        "binding.json",
        "before-fractional-helper.py",
        "before-310-protocol.json",
        "after-native23927.json.gz",
    ],
)
def test_frozen_evidence_is_rechecked_even_after_a_previous_load(
    name, tmp_path, monkeypatch
):
    iso.load()
    folder = tmp_path / "reference"
    shutil.copytree(iso.FOLDER, folder)
    file = folder / name
    file.write_bytes(file.read_bytes() + b" ")
    monkeypatch.setattr(iso, "FOLDER", folder)
    with pytest.raises(ValueError, match="Clock ISO evolution reference changed"):
        iso.load()


def test_adapted_date_helpers_preserve_upstream_bodies_and_full_license():
    root = historical_package_root()
    source = (root / CORE_PATH).read_text()
    current = ast.parse(source)
    upstream = ast.parse((iso.INPUT_FOLDER / "python312-pydatetime.py").read_bytes())
    for name in [
        "_is_ascii_digit",
        "_find_isoformat_datetime_separator",
        "_parse_isoformat_date",
    ]:
        now = next(
            n for n in current.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        old = next(
            n
            for n in upstream.body
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
        assert ast.dump(
            ast.Module(body=now.body, type_ignores=[]), include_attributes=False
        ) == ast.dump(
            ast.Module(body=old.body, type_ignores=[]), include_attributes=False
        )
    comments = source.split(
        "# --- Full upstream CPython license, retained verbatim as comments ---\n", 1
    )[1]
    restored = (
        "\n".join(
            line[2:] if line.startswith("# ") else "" for line in comments.splitlines()
        )
        + "\n"
    )
    assert restored == (iso.INPUT_FOLDER / "python312-LICENSE").read_text()
    assert not any(
        isinstance(n, ast.Attribute) and n.attr == "fromisoformat"
        for n in ast.walk(current)
    )
