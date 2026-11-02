"""Offline frozen-source replay, with failures preserved as expected evidence."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_astrodice_de441_restore import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-de441-restore-v1"
MANIFEST_SHA = "c7fde5108aaef3d51191a1340b0d4beae30c4ce7aa98796d96ed1ca6a701f4ec"


def test_frozen_material_identity_and_independent_raw_reference_replay(tmp_path):
    manifest = FIXTURE / "manifest.json"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == MANIFEST_SHA
    files = json.loads(manifest.read_text())["files"]
    assert len(files) == 66
    for name, sha in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    root = (FIXTURE / "frozen-reference-code").resolve()
    env = {**os.environ, "PYTHONPATH": str(root)}
    output = tmp_path / "reference-quality.json"
    args = [sys.executable, "-m", "scripts.audit_astrodice_horizons_wide_reference"]
    for key, path in {
        "protocol": FIXTURE / "protocol-before-queries.json",
        "reference": FIXTURE / "reference-first.json",
        "material": FIXTURE / "reference-first-raw",
        "seal": FIXTURE / "reference-first-seal.json",
        "output": output,
    }.items():
        args.extend(["--" + key, str(path.resolve())])
    result = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    quality = json.loads(output.read_text())
    assert quality["position_probes"] == 266
    assert quality["cases"] == quality["complete_cases"] == 14
    assert (
        quality["first_tlist_epoch_guard"]["batches_with_validated_auxiliary_epoch"]
        == 15
    )
    assert quality["candidate_compared"] is False


def test_independent_arithmetic_replay_retains_compressed_failure():
    result = verify(FIXTURE)
    assert result["exit_code"] == 0
    assert result["counts"]["swieph"]["rate_fail"] == 1
    assert result["counts"]["jpl"]["rate_pass"] == 14
    assert result["old_overall_exit_code"] == 1
    assert result["full_kernel_and_all_excerpt_bytes_verified"] is False
    assert result["full_objective_complete"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "erase_failure",
        "rate",
        "radius",
        "drop_frame",
        "drop_case",
        "excerpt",
        "overall",
    ],
)
def test_independent_replay_rejects_false_grades_missing_rows_and_changed_data(
    tmp_path, mutation
):
    target = tmp_path / "copy"
    shutil.copytree(FIXTURE, target)
    if mutation == "excerpt":
        path = next((target / "jpl-excerpts").rglob("*.441"))
        path.write_bytes(path.read_bytes()[:-1])
    elif mutation == "overall":
        path = target / "original-overall-gate.json"
        data = json.loads(path.read_text())
        data["overall_numeric_gate_exit_code"] = 0
        path.write_text(json.dumps(data))
    else:
        path = target / "swieph-candidate-first.json"
        data = json.loads(path.read_text())
        if mutation == "drop_case":
            data["rows"].pop()
        elif mutation == "drop_frame":
            data["rows"][0]["layers"]["rate"]["frames"].pop("lahiri")
        elif mutation == "erase_failure":
            data["rows"][0]["layers"]["rate"][
                "status"
            ] = "declared_lines_satisfied_under_reference_model"
        else:
            frame = data["rows"][0]["layers"]["rate"]["frames"]["tropical"]
            if mutation == "rate":
                frame["candidate_state"]["longitude_speed"] += 0.001
            else:
                frame["reference"]["rounding_and_frame_check_radius_arcsec_per_day"] = 0
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(target)
