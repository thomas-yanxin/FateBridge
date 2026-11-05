"""Real external module imports and real escaping symlinks stay rejected."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import scripts.audit_astrodice_apparent_source as original
from fatebridge.core import astro
from fatebridge.core.astro import runtime


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("escape", [False, True])
def test_actual_external_sampler_module_and_root_internal_escaping_symlink_are_rejected(
    tmp_path, monkeypatch, escape
):
    project = tmp_path / "project"
    script = project / "scripts/audit.py"
    script.parent.mkdir(parents=True)
    source = Path(original.__file__)
    script.write_bytes(source.read_bytes())
    grader = imported("actual_source_path_guard", script)

    outside = tmp_path / "outside/runtime.py"
    outside.parent.mkdir()
    outside.write_bytes(Path(runtime.__file__).read_bytes())
    if escape:
        module_path = project / "src/fatebridge/core/astro/runtime.py"
        module_path.parent.mkdir(parents=True)
        module_path.symlink_to(outside)
    else:
        module_path = outside
    foreign_runtime = imported("actual_external_runtime", module_path)
    assert Path(foreign_runtime.__file__).samefile(outside)
    assert (
        not Path(foreign_runtime.__file__).resolve().is_relative_to(project.resolve())
    )
    # This is a real imported module, not forged __file__/empty source metadata.
    monkeypatch.setattr(astro, "runtime", foreign_runtime)

    fixture = tmp_path / "fixture"
    fixture.mkdir()
    kernel = fixture / "synthetic-guard-only.bin"
    kernel.write_bytes(b"guard must reject before numerical calls")
    (fixture / "geometric-reference.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "kernel_path": kernel.name,
                        "kernel_sha256": hashlib.sha256(
                            kernel.read_bytes()
                        ).hexdigest(),
                    }
                ]
            }
        )
    )
    reference = fixture / "reference.json"
    # Deliberately no numeric payload: success past the guard cannot be confused
    # with a numerical pass; the exact guard error must be raised first.
    reference.write_text(json.dumps({"rows": [{"window_index": 0}]}))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", kernel.name)
    monkeypatch.setenv("SE_EPHE_PATH", str(fixture))
    with pytest.raises(ValueError, match="^Native sampler imported outside project$"):
        grader.audit(fixture, fixture, reference, 0)


def test_real_import_alias_for_same_project_is_admitted_without_faking_module_identity(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    script = project / "scripts/audit.py"
    script.parent.mkdir(parents=True)
    source = Path(original.__file__)
    script.write_bytes(source.read_bytes())
    actual_module = project / "src/fatebridge/core/astro/runtime.py"
    actual_module.parent.mkdir(parents=True)
    actual_module.write_bytes(Path(runtime.__file__).read_bytes())
    alias = tmp_path / "alias"
    alias.symlink_to(project, target_is_directory=True)
    grader = imported("actual_aliased_source_guard", alias / "scripts/audit.py")
    aliased_runtime = imported(
        "actual_aliased_runtime", alias / "src/fatebridge/core/astro/runtime.py"
    )
    assert Path(aliased_runtime.__file__).samefile(actual_module)
    assert Path(aliased_runtime.__file__).resolve().is_relative_to(project.resolve())
    monkeypatch.setattr(astro, "runtime", aliased_runtime)

    fixture = tmp_path / "fixture"
    fixture.mkdir()
    kernel = fixture / "synthetic-guard-only.bin"
    kernel.write_bytes(b"no qualified numeric source is claimed")
    (fixture / "geometric-reference.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "kernel_path": kernel.name,
                        "kernel_sha256": hashlib.sha256(
                            kernel.read_bytes()
                        ).hexdigest(),
                    }
                ]
            }
        )
    )
    reference = fixture / "reference.json"
    reference.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "id": "alias-path-only",
                        "role": "test",
                        "body": "Mercury",
                        "date_tdb": "2000-01-01T12:00:00",
                        "native_numeric_argument": 2451545.0,
                        "window_index": 0,
                    }
                ]
            }
        )
    )
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", kernel.name)
    monkeypatch.setenv("SE_EPHE_PATH", str(fixture))
    result = grader.audit(fixture, fixture, reference, 0)
    # Only path admission succeeds. Unqualified reference data still stays unknown.
    assert result["status"] == original.UNKNOWN
    assert result["exit_code"] == 2
    assert result["layers"]["position"]["status"] == original.UNKNOWN
    assert result["layers"]["rate"]["status"] == original.UNKNOWN
    assert result["full_goal_complete"] is False
