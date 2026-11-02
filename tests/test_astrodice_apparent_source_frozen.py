"""Independent source replay and preservation of all first measurements."""

import hashlib
import json
import shutil
import subprocess
import sys
from decimal import Decimal as N
from pathlib import Path

import pytest

from scripts.audit_astrodice_apparent_source import collect_frames
from scripts.audit_astrodice_apparent_source_reference import audit
from scripts.gen_astrodice_apparent_source_reference import require_fixed_policy

FIXTURE = Path(__file__).parent / "fixtures/astrodice-apparent-source-v1"


def groups(root):
    return [
        (root, "development-reference-first.json", "development-native-first-", 3),
        (root, "holdout-reference-first.json", "holdout-native-first-", 8),
        (root / "boundary-A", "holdout-reference-first.json", "native-first-", 10),
        (root / "boundary-B", "holdout-reference-first.json", "native-first-", 10),
    ]


def test_all_31_conditions_replay_from_the_named_source_without_new_grades():
    manifest = FIXTURE / "manifest.json"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "4ac6ccc4718569542fbd00f716e99f5526febf40cdb9cea464d00d9487759dfb"
    )
    for name, expected in json.loads(manifest.read_text())["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    seen = set()
    for folder, reference, prefix, count in groups(FIXTURE):
        result = audit(folder, FIXTURE / "source-records", folder / reference)
        assert result["exit_code"] == 0 and result["rows"] == count
        assert N(result["maximum_direction_component_difference"]) < N("1e-45")
        assert result["maximum_scalar_FD_vs_AD_arcsec_per_day"] < 1e-7
        assert not result["full_goal_complete"]
        for i in range(count):
            row = json.loads((folder / (prefix + f"{i:02}.json")).read_text())
            seen.add((row["body"], row["date_tdb"]))
            saved = row["layers"]["rate"]
            frames = saved["frames"]
            collected = collect_frames(
                {
                    "tropical": lambda: frames["tropical"],
                    "lahiri": lambda: frames["lahiri"],
                },
                lambda name, frame: frame,
            )
            assert collected == {"status": saved["status"], "frames": frames}
            assert (
                row["exit_code"] == 0 and not row["original_Horizons_results_regraded"]
            )
    assert len(seen) == 31


def test_a_changed_ad_derivative_cannot_become_its_own_reference_oracle(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "data")
    root = tmp_path / "data"
    path = root / "holdout-reference-first.json"
    data = json.loads(path.read_text())
    values = data["rows"][0]["centers"][-1]["derivative_per_day"]
    values[0] = str(N(values[0]) + N("1e-6"))
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="derivative differs"):
        audit(root, root / "source-records", path)


def test_source_only_geometry_selection_preserves_both_predeclared_cohorts(tmp_path):
    # The selector deliberately rejects a process that imported the candidate.
    output = tmp_path / "selection.json"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.select_astrodice_source_boundaries",
            "--run",
            str(FIXTURE),
            "--fixture",
            str(FIXTURE / "source-records"),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    selected = json.loads(output.read_text())
    assert selected == json.loads(
        (FIXTURE / "boundary-selection-retry.json").read_text()
    )
    assert len(selected["crossings"]) == 4
    assert len(selected["cohorts"]["A"]) == len(selected["cohorts"]["B"]) == 10
    assert not selected["candidate_or_apparent_rate_used_for_selection"]


def test_rebinding_parameter_hashes_does_not_make_a_changed_mass_table_authoritative(
    tmp_path,
):
    shutil.copytree(FIXTURE, tmp_path / "data")
    root = tmp_path / "data"
    profile = root / "source-solar-profile.json"
    data = json.loads(profile.read_text())
    data["radius_mass_pairs"][5][1] = "0.999000"
    profile.write_text(json.dumps(data))
    protocol = root / "protocol-before-development.json"
    p = json.loads(protocol.read_text())
    p["source_artifact_sha256"][profile.name] = hashlib.sha256(
        profile.read_bytes()
    ).hexdigest()
    protocol.write_text(json.dumps(p))
    reference = root / "holdout-reference-first.json"
    r = json.loads(reference.read_text())
    r["protocol_sha256"] = hashlib.sha256(protocol.read_bytes()).hexdigest()
    reference.write_text(json.dumps(r))
    with pytest.raises(ValueError, match="parameters differ from named source"):
        audit(root, root / "source-records", reference)


@pytest.mark.parametrize(
    "name,value",
    [
        ("rate_line_arcsec_per_day", 0.0021),
        ("position_line_arcsec", 0.021),
        ("reference_fd_vs_AD_line_arcsec_per_day", 0.001),
        ("reference_fd_steps_days", ["1/1048576"]),
    ],
)
def test_error_lines_and_probe_plan_cannot_be_relaxed(name, value):
    p = json.loads((FIXTURE / "protocol-before-development.json").read_text())
    p[name] = value
    with pytest.raises(ValueError, match="qualification policy changed"):
        require_fixed_policy(p)
