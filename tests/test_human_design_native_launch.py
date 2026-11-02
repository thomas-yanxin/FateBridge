"""Bind native config without starting a model or changing child outcomes."""

import hashlib
import json
import os
import sys

import pytest

from fatebridge.validation.evaluation_environment import (
    capture_selection,
    selection_bytes,
)
from scripts import preserve_human_design_deliveries as wrapper


def preparation(tmp_path):
    root = tmp_path / "prepared"
    source = root / "source"
    source.mkdir(parents=True)
    raw = selection_bytes(capture_selection({"SE_EPHE_PATH": "/prepared/ephe"}))
    sha = hashlib.sha256(raw).hexdigest()
    (root / "native-environment.json").write_bytes(raw)
    (root / "preparation.json").write_text(
        json.dumps({"native_environment_sha256": sha})
    )
    command = [
        sys.executable,
        str(source / "scripts/evaluate_agent.py"),
        "--native-environment",
        str(root / "native-environment.json"),
        "--native-environment-sha256",
        sha,
    ]
    proposal = {
        "command": command,
        "cwd": str(source),
        "environment": {"PYTHONPATH": str(source / "src")},
    }
    (root / "proposed-execution.json").write_text(json.dumps(proposal))
    return root, raw


@pytest.mark.parametrize("fault", ["file", "flag_hash", "flag_path", "missing_value"])
def test_proposal_tampering_stops_before_any_model_process(
    tmp_path, monkeypatch, fault
):
    root, raw = preparation(tmp_path)
    p = root / "proposed-execution.json"
    proposal = json.loads(p.read_text())
    command = proposal["command"]
    if fault == "file":
        (root / "native-environment.json").write_bytes(raw + b" ")
    elif fault == "flag_hash":
        command[-1] = "0" * 64
    elif fault == "flag_path":
        command[3] = "/some/other/config.json"
    else:
        command.pop()
    p.write_text(json.dumps(proposal))
    monkeypatch.setattr(
        wrapper.subprocess,
        "Popen",
        lambda *a, **kw: pytest.fail("Model must not be launched"),
    )
    with pytest.raises(ValueError):
        wrapper.launch(root)
    assert not (root / "model-process.json").exists()


@pytest.mark.parametrize("child_changes_selection", [False, True])
def test_wrapper_preserves_child_exit_and_rejects_a_different_config(
    tmp_path, monkeypatch, child_changes_selection
):
    root, raw = preparation(tmp_path)
    monkeypatch.setenv("SE_EPHE_PATH", "/later/ambient")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "/later/kernel")
    seen = []

    class FakeProcess:
        pid = 123

        def __init__(self, command, **kwargs):
            seen.append(kwargs["env"])
            run = root / "model-run"
            run.mkdir()
            output = (
                selection_bytes(capture_selection({"SE_EPHE_PATH": "/changed/ephe"}))
                if child_changes_selection
                else raw
            )
            (run / "native-environment.json").write_bytes(output)
            (run / "report.json").write_text(
                json.dumps(
                    {"native_environment_sha256": hashlib.sha256(output).hexdigest()}
                )
            )

        def poll(self):
            return 0

        def wait(self):
            return 0

    monkeypatch.setattr(wrapper.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(wrapper, "collect", lambda *a, **kw: [])
    assert wrapper.launch(root) == int(child_changes_selection)
    assert seen[0]["SE_EPHE_PATH"] == "/prepared/ephe"
    assert "FATEBRIDGE_JPL_FILE" not in seen[0]
    assert os.environ["SE_EPHE_PATH"] == "/later/ambient"
    result = json.loads((root / "model-terminal.json").read_text())
    assert result["exit_code"] == 0
    assert result["helper_exit_code"] == int(child_changes_selection)
    assert result["native_environment_binding"]["stage_equivalence_verified"] is (
        not child_changes_selection
    )
