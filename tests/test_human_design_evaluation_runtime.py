"""Select the actual desktop model runtime, preserving explicit operator choices."""

from types import SimpleNamespace

import pytest

from fatebridge import diagnostics as d


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    monkeypatch.setattr(d.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", "Codex Desktop")
    monkeypatch.delenv("CODEX_CLI_PATH", raising=False)
    monkeypatch.setattr(d.shutil, "which", lambda _: "/old/PATH/codex")
    binary = (
        tmp_path
        / "ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
    )
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    return binary


def test_unique_actual_running_app_beats_incompatible_PATH_without_reading_arguments(
    desktop, monkeypatch
):
    seen = []

    def ps(args, **kwargs):
        seen.append((args, kwargs))
        return SimpleNamespace(
            returncode=0, stdout=f"COMMAND\n{desktop}\n{desktop}\n/bin/shell\n"
        )

    monkeypatch.setattr(d.subprocess, "run", ps)
    result = d.resolve_codex_cli()
    assert result == {
        "path": str(desktop),
        "source": "running_desktop",
        "path_cli": "/old/PATH/codex",
    }
    assert seen[0][0] == ["ps", "-axo", "comm"]
    assert seen[0][1]["timeout"] == 2


@pytest.mark.parametrize(
    "fault", ["ambiguous", "non_executable", "ps_error", "timeout"]
)
def test_uncertain_desktop_discovery_keeps_explicit_PATH_fallback(
    desktop, monkeypatch, tmp_path, fault
):
    text = str(desktop)
    if fault == "ambiguous":
        other = tmp_path / "Other.app/Contents/MacOS/codex"
        other.parent.mkdir(parents=True)
        other.write_text("x")
        other.chmod(0o755)
        text += "\n" + str(other)
    if fault == "non_executable":
        desktop.chmod(0o644)

    def ps(*args, **kwargs):
        if fault == "timeout":
            raise d.subprocess.TimeoutExpired("ps", 2)
        return SimpleNamespace(returncode=1 if fault == "ps_error" else 0, stdout=text)

    monkeypatch.setattr(d.subprocess, "run", ps)
    assert d.resolve_codex_cli()["path"] == "/old/PATH/codex"


@pytest.mark.parametrize("explicit", [True, False])
def test_explicit_cli_or_non_desktop_caller_does_not_inventory_processes(
    desktop, monkeypatch, explicit
):
    def forbidden(*a, **k):
        raise AssertionError("Unnecessary process inventory")

    monkeypatch.setattr(d.subprocess, "run", forbidden)
    if explicit:
        monkeypatch.setenv("CODEX_CLI_PATH", str(desktop))
    else:
        monkeypatch.setenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", "codex_cli_rs")
    assert d.resolve_codex_cli()["path"] == (
        str(desktop) if explicit else "/old/PATH/codex"
    )
