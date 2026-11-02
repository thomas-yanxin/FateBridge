"""Source-collation and non-adoption guards, not a classical accuracy score."""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIRST = script("audit_bazi_clash_season")
SECOND = script("audit_bazi_clash_season_v2")
THIRD = script("audit_bazi_clash_power_v3")


def frozen(path):
    data = path.read_bytes()
    assert (
        hashlib.sha256(data).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(data)


@pytest.fixture(scope="module")
def historical_v5(tmp_path_factory):
    """Replay historical studies under their own source, never downgrade production."""
    folder = ROOT / "tests/fixtures/bazi_strength_snapshot_v5"
    manifest = frozen(folder / "manifest.json")
    archive = folder / "source.tar.gz"
    assert (
        hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archive_sha256"]
    )
    destination = tmp_path_factory.mktemp("historical-v5")
    with tarfile.open(archive) as handle:
        handle.extractall(destination, filter="data")
    for relative, expected in manifest["files"].items():
        assert (
            hashlib.sha256((destination / relative).read_bytes()).hexdigest()
            == expected
        )
    for name in ("bazi_clash_season_v1", "bazi_clash_season_v2", "bazi_clash_power_v3"):
        source = ROOT / "tests/fixtures" / name
        shutil.copytree(source, destination / "tests/fixtures" / name)
        for relative, expected in frozen(source / "pre-first-run.json")[
            "frozen_files"
        ].items():
            target = destination / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            # Only the two archived runner versions have an exact fallback.
            # Numeric/data files must retain their actual frozen bytes.
            if relative not in FIRST.RUNNER_ARCHIVES:
                assert hashlib.sha256(target.read_bytes()).hexdigest() == expected
    return destination


def historical_run(runner, historical_v5, output, candidate_root=None):
    return subprocess.run(
        [
            sys.executable,
            str(historical_v5 / "scripts" / (runner.__name__ + ".py")),
            "--candidate-root",
            str(candidate_root or historical_v5),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_full_source_units_keep_unknowns_and_cross_page_hour_without_a_biography_label():
    first = frozen(ROOT / "tests/fixtures/bazi_clash_season_v1/reference.json")
    second = frozen(ROOT / "tests/fixtures/bazi_clash_season_v2/reference.json")
    assert first["source"]["selected_pdf_pages"] == list(range(77, 92))
    assert second["source"]["selected_pdf_pages"] == list(range(92, 121))
    assert (len(first["cases"]), len(second["cases"])) == (13, 30)
    assert sum(c["expected_strength"] is None for c in first["cases"]) == 12
    assert sum(c["expected_strength"] is None for c in second["cases"]) == 27
    wrapped = next(c for c in first["cases"] if c["id"] == "DZ-11")
    assert wrapped["source_pdf_pages"] == [88, 89]
    assert wrapped["pillars"] == ["庚寅", "辛巳", "丙寅", "辛卯"]
    assert wrapped["expected_strength"] is None
    high = next(c for c in second["cases"] if c["id"] == "GH-26")
    assert high["pillars"] == ["乙丑", "己卯", "乙亥", "壬午"]
    assert high["expected_strength"] is None  # 似乎 is not the author's verdict.
    balance = next(c for c in second["cases"] if c["id"] == "GH-27")
    assert balance["expected_strength"] is None  # 身杀两停 is not global 中和.
    assert (
        second["source_relative_force_statements"][0]["relation"]
        == "body_killer_balanced"
    )
    negative = next(c for c in second["cases"] if c["id"] == "GH-07")
    assert negative["expected_strength"] is None
    assert second["body_constraints"][0]["forbidden_strengths"] == ["强"]


def test_equal_active_decision_is_a_directional_failure_but_unresolved_input_is_unknown():
    source = {"positions": ["year", "day"], "weaker_position": "day"}
    equal = {
        "relations": [
            {
                "kind": "六冲",
                "positions": ["year", "day"],
                "status": "active",
                "root_multipliers": {"year": 0.75, "day": 0.75},
            }
        ]
    }
    result = SECOND.compare_direction(equal, source)
    assert result["model_direction"] == "tied" and result["matches"] is False
    resolved = {
        "relations": [
            {
                "kind": "六冲",
                "positions": ["year", "day"],
                "status": "resolved_by_combination",
            }
        ]
    }
    assert SECOND.compare_direction(resolved, source)["matches"] is None
    assert SECOND.compare_direction({"relations": []}, source)["matches"] is None


@pytest.mark.parametrize("version,runner", [(1, FIRST), (2, SECOND)])
def test_original_first_results_replay_without_replacing_any_labels_or_unknowns(
    version, runner, historical_v5, tmp_path
):
    report = frozen(ROOT / f"docs/validation/bazi-clash-season-first-v{version}.json")
    path = tmp_path / "replay.json"
    process = historical_run(runner, historical_v5, path)
    assert process.returncode == 1, process.stderr
    current = json.loads(path.read_text())
    # Same code/data, explicitly different checkout path; no other value removed.
    current["candidate_root"] = report["candidate_root"]
    if version == 2:
        for field, source, archive in [
            ("runner_sha256", "audit_bazi_clash_season_v2.py", "bazi_clash_season_v2"),
            (
                "core_runner_sha256",
                "audit_bazi_clash_season.py",
                "bazi_clash_season_v1",
            ),
        ]:
            assert (
                current[field]
                == hashlib.sha256((ROOT / "scripts" / source).read_bytes()).hexdigest()
            )
            assert (
                report[field]
                == hashlib.sha256(
                    (
                        ROOT / "tests/fixtures" / archive / "first-runner.py.txt"
                    ).read_bytes()
                ).hexdigest()
            )
            # Identified runner typing repair is metadata; every calculated
            # value, label, unknown and adoption gate must stay identical.
            current[field] = report[field]
    assert current == report
    assert not report["numerical_gates_passed"]
    assert report["production_default_changed"] is False
    assert report["classical_acceptance_passed"] is False
    assert report["overall_score"] is None


def test_local_improvement_cannot_hide_two_regressions_from_the_same_other_chart():
    report = frozen(ROOT / "docs/validation/bazi-clash-season-first-v2.json")
    local = report["new_local_clash_comparisons"]
    assert {r["source_annotation"]["case_id"] for r in local if r["resolved"]} == {
        "GH-18"
    }
    assert {r["source_annotation"]["case_id"] for r in local if r["regressed"]} == {
        "GH-17"
    }
    assert sum(r["resolved"] for r in local) == sum(r["regressed"] for r in local) == 2
    assert report["adoption_gates"]["new_nonoverlap_body_or_local_clash_improvement"]
    assert not report["adoption_gates"]["no_new_local_clash_regression"]


@pytest.mark.parametrize("runner", [FIRST, SECOND, THIRD])
def test_changed_numerical_dependencies_fail_before_import_or_comparison(
    runner, tmp_path, historical_v5
):
    protocol = frozen(runner.FIXTURE / "protocol.json")
    for relative in protocol["candidate_dependencies"]:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((historical_v5 / relative).read_bytes())
    target = tmp_path / "src/fatebridge/core/strength.py"
    target.write_bytes(target.read_bytes() + b"\n# drift\n")
    output = tmp_path / "forbidden.json"
    process = historical_run(runner, historical_v5, output, candidate_root=tmp_path)
    assert process.returncode == 1
    assert "Numerical dependencies differ" in process.stderr
    assert not output.exists()


def test_historical_runner_resolution_is_exact_and_never_applies_to_numeric_files(
    tmp_path,
):
    relative = "scripts/audit_bazi_clash_season.py"
    path = tmp_path / relative
    path.parent.mkdir()
    path.write_text("current harness")
    archive = tmp_path / FIRST.RUNNER_ARCHIVES[relative]
    archive.parent.mkdir(parents=True)
    archive.write_text("original first harness")
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    FIRST.verify_frozen_input(tmp_path, relative, expected)
    archive.write_text("changed archive")
    with pytest.raises(ValueError, match="First-run contract changed"):
        FIRST.verify_frozen_input(tmp_path, relative, expected)
    numeric = tmp_path / "src/fatebridge/core/strength.py"
    numeric.parent.mkdir(parents=True)
    numeric.write_text("changed numerical model")
    with pytest.raises(ValueError, match="First-run contract changed"):
        FIRST.verify_frozen_input(tmp_path, "src/fatebridge/core/strength.py", expected)


@pytest.mark.parametrize("runner", [FIRST, SECOND, THIRD])
def test_existing_first_result_is_never_overwritten(runner, tmp_path, monkeypatch):
    result = tmp_path / "first.json"
    result.write_text("keep first bytes")
    monkeypatch.setattr(
        sys, "argv", ["audit", "--candidate-root", str(ROOT), "--output", str(result)]
    )
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2 and result.read_text() == "keep first bytes"


def test_next_hypothesis_is_separately_frozen_before_any_new_source_comparison():
    folder = ROOT / "tests/fixtures/bazi_clash_power_v3"
    protocol = frozen(folder / "protocol.json")
    assert (
        hashlib.sha256((folder / "candidate-core.py.txt").read_bytes()).hexdigest()
        == protocol["candidate_sha256"]
    )
    assert (
        protocol["study_status"]
        == "candidate_frozen_new_source_not_yet_collected_or_compared"
    )
    assert protocol["production_default_changed"] is False
    assert protocol["source_plan"]["selected_pdf_pages"] == list(range(121, 150))
    if (folder / "reference.json").exists():
        reference = frozen(folder / "reference.json")
        assert (
            reference["protocol_sha256"]
            == hashlib.sha256((folder / "protocol.json").read_bytes()).hexdigest()
        )


def test_shape_bureau_complete_source_keeps_tail_separate_and_repairs_before_comparison():
    reference = frozen(ROOT / "tests/fixtures/bazi_clash_power_v3/reference.json")
    assert reference["source"]["selected_pdf_pages"] == list(range(121, 150))
    cases = {c["id"]: c for c in reference["cases"]}
    assert len(cases) == 31
    assert sum(c["fresh_gate_eligible"] for c in cases.values()) == 30
    assert sum(c["expected_strength"] is not None for c in cases.values()) == 8
    assert reference["local_clash_labels"] == []
    assert cases["GH-31-TAIL"]["fresh_gate_eligible"] is False
    assert cases["GH-31-TAIL"]["source_unit"] == "干支总论尾例"
    assert cases["XX-08"]["pillars"] == ["戊寅", "乙卯", "甲辰", "辛未"]
    assert cases["FJ-06"]["pillars"] == ["丁卯", "甲辰", "甲寅", "乙亥"]
    assert cases["FJ-09"]["source_pdf_pages"] == [148, 149]
    assert cases["FJ-09"]["printed_pages"] == [
        {"volume": 2, "page": 6},
        {"volume": 2, "page": 7},
    ]
    assert cases["FJ-01"]["expected_strength"] is None  # 身杀两停.
    assert cases["FJ-04"]["expected_strength"] is None  # 非从强格.
    assert all(all(c["input_consistency"].values()) for c in cases.values())


def test_whole_energy_first_result_replays_and_cannot_count_exposed_improvement_as_fresh(
    historical_v5, tmp_path
):
    first = frozen(ROOT / "docs/validation/bazi-clash-power-first-v3.json")
    path = tmp_path / "replay.json"
    process = historical_run(THIRD, historical_v5, path)
    assert process.returncode == 1, process.stderr
    replay = json.loads(path.read_text())
    replay["candidate_root"] = first["candidate_root"]
    assert replay == first
    assert first["fresh_source_summary"] == {
        "new_cases": 30,
        "previous_chapter_boundary_addendum_cases": 1,
        "adjudicated": 8,
        "unknown": 22,
        "resolved": [],
        "regressions": [],
        "local_clash_labels": 0,
    }
    assert sum(r["resolved"] for r in first["previous_local_clash_comparisons"]) == 2
    assert not any(r["regressed"] for r in first["previous_local_clash_comparisons"])
    assert not first["adoption_gates"]["new_nonoverlap_body_or_local_clash_improvement"]
    assert first["production_default_changed"] is False
    assert first["classical_acceptance_passed"] is False
    assert first["overall_score"] is None


def test_next_seasonal_bureau_hypothesis_keeps_the_failed_clash_candidate_separate():
    folder = ROOT / "tests/fixtures/bazi_seasonal_bureau_v2"
    protocol = frozen(folder / "protocol.json")
    assert (
        hashlib.sha256((folder / "candidate-core.py.txt").read_bytes()).hexdigest()
        == protocol["candidate_sha256"]
    )
    snapshot = frozen(ROOT / "tests/fixtures/bazi_strength_snapshot_v5/manifest.json")
    assert protocol["candidate_dependencies"] == snapshot["numerical_dependencies"]
    assert protocol["source_plan"]["selected_pdf_pages"] == list(range(150, 161))
    assert protocol["source_plan"]["next_native_bookmark"] == {
        "title": "体用",
        "pdf_page": 160,
    }
    assert (
        protocol["study_status"]
        == "candidate_frozen_new_source_not_yet_collected_or_compared"
    )
    assert protocol["production_default_changed"] is False
    assert protocol["overall_score"] is None


def test_next_candidate_has_exactly_one_predeclared_change_and_keeps_bad_first_freeze(
    historical_v5,
):
    folder = ROOT / "tests/fixtures/bazi_seasonal_bureau_v2"
    baseline = (historical_v5 / "src/fatebridge/core/strength.py").read_text()
    needle = '        season_supports = phases[target.value] == "旺"\n'
    replacement = '        season_supports = phases[target.value] == "旺" or (\n            kind == "三会" and "month" in members\n        )\n'
    assert baseline.count(needle) == 1
    assert (folder / "candidate-core.py.txt").read_text() == baseline.replace(
        needle, replacement
    )
    first_folder = ROOT / "tests/fixtures/bazi_seasonal_bureau_v1"
    rejection = frozen(first_folder / "precomparison-rejection.json")
    assert rejection["status"] == "invalid_baseline_provenance_not_run"
    assert rejection["first_model_comparison_occurred"] is False
    assert (
        rejection["original_candidate_sha256"]
        == hashlib.sha256(
            (first_folder / "candidate-core.py.txt").read_bytes()
        ).hexdigest()
    )
