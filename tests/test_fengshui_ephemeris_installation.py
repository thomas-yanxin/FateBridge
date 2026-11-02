"""Verified profile acquisition and cache discovery, independent of cwd."""

from pathlib import Path

import pytest

from fatebridge import fetch_ephe
from fatebridge.core import ephemeris_installation as install
from fatebridge.core import ephemeris_runtime
from fatebridge.core.fengshui.models import HousePeriod
from tests.fixtures.ephemeris_manifest import manifest_for_payloads


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.setattr(ephemeris_runtime, "_PROJECT_ROOT", tmp_path / "checkout")
    monkeypatch.setattr(
        ephemeris_runtime, "_configured_path", ephemeris_runtime._configured_path
    )
    payloads = {
        name: b"SW-test-profile-" + name.encode() for name in install.FENGSHUI_FILES
    }
    manifest = manifest_for_payloads(payloads)
    manifest.update(id="test-edition", source_commit="fixture-only")
    monkeypatch.setattr(install, "load_ephemeris_manifest", lambda: manifest)
    monkeypatch.setattr(
        fetch_ephe, "load_ephemeris_manifest", lambda path=None: manifest
    )
    monkeypatch.setattr(fetch_ephe, "default_dest", lambda: tmp_path / "checkout/ephe")
    calls = []
    monkeypatch.setattr(
        fetch_ephe,
        "_download",
        lambda url, timeout=60: calls.append(url) or payloads[url.rsplit("/", 1)[-1]],
    )
    return payloads, calls


def test_profile_covers_actual_supported_house_period_extrema():
    schema = HousePeriod.model_json_schema()["properties"]["effective_event_year"]
    integer = next(row for row in schema["anyOf"] if row["type"] == "integer")
    minimum, maximum = integer["minimum"], integer["maximum"]
    assert 1864 + (minimum - 1864) // 20 * 20 == install.FENGSHUI_FIRST_BOUNDARY_YEAR
    assert (
        1864 + (maximum - 1864) // 20 * 20 + 20 == install.FENGSHUI_LAST_BOUNDARY_YEAR
    )
    assert set(install.FENGSHUI_FILES) == {
        "sepl_12.se1",
        "semo_12.se1",
        "sepl_18.se1",
        "semo_18.se1",
    }


def test_empty_installation_acquires_into_cache_and_discovers_all_four_files(
    profile, capsys
):
    _, calls = profile
    assert install.verified_user_ephemeris_dir() is None
    assert ephemeris_runtime.default_ephe_dir() is None
    assert fetch_ephe.main(["--profile", "fengshui_calendar"]) == 0
    directory = install.user_ephemeris_dir()
    assert len(calls) == 4
    assert install.fengshui_file_status(directory)["all_files_verified"]
    assert install.verified_user_ephemeris_dir() == str(directory)
    assert ephemeris_runtime.default_ephe_dir() == str(directory)
    assert "auto-discovers" in capsys.readouterr().out
    # Read-only verification does not perform a second acquisition.
    assert fetch_ephe.main(["--profile", "fengshui_calendar", "--verify-only"]) == 0
    assert len(calls) == 4


@pytest.mark.parametrize("fault", ["partial", "bad_bytes", "wrong_edition"])
def test_partial_or_unverified_cache_is_never_selected(profile, fault):
    payloads, _ = profile
    directory = install.user_ephemeris_dir()
    directory.mkdir(parents=True)
    for name, data in payloads.items():
        (directory / name).write_bytes(data)
    first = directory / install.FENGSHUI_FILES[0]
    if fault == "partial":
        first.unlink()
    else:
        first.write_bytes(
            b"HTML-error" if fault == "bad_bytes" else b"SW-other-edition"
        )
    assert not install.fengshui_file_status(directory)["all_files_verified"]
    assert install.verified_user_ephemeris_dir() is None
    assert ephemeris_runtime.default_ephe_dir() is None


def test_existing_checkout_is_preserved_and_completed(profile):
    payloads, calls = profile
    project = fetch_ephe.default_dest()
    project.mkdir(parents=True)
    (project / "sepl_18.se1").write_bytes(payloads["sepl_18.se1"])
    assert fetch_ephe.main(["--profile", "fengshui_calendar"]) == 0
    assert len(calls) == 3
    assert ephemeris_runtime.default_ephe_dir() == str(project)
    assert install.fengshui_file_status(project)["all_files_verified"]
    assert not install.user_ephemeris_dir().exists()


def test_explicit_destination_and_explicit_runtime_path_remain_authoritative(
    profile, tmp_path, monkeypatch, capsys
):
    directory = tmp_path / "explicit"
    assert (
        fetch_ephe.main(["--profile", "fengshui_calendar", "--dest", str(directory)])
        == 0
    )
    assert ephemeris_runtime.default_ephe_dir() is None
    assert "Set SE_EPHE_PATH" in capsys.readouterr().out
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    assert ephemeris_runtime.configure_ephemeris_path() == str(directory)


def test_cache_does_not_override_existing_project_or_environment(profile, monkeypatch):
    payloads, _ = profile
    directory = install.user_ephemeris_dir()
    directory.mkdir(parents=True)
    for name, data in payloads.items():
        (directory / name).write_bytes(data)
    project = fetch_ephe.default_dest()
    project.mkdir(parents=True)
    (project / "custom.se1").write_bytes(b"SW-user-managed-edition")
    assert ephemeris_runtime.default_ephe_dir() == str(project)
    monkeypatch.setenv("SE_EPHE_PATH", "/explicit/operator/path")
    assert ephemeris_runtime.configure_ephemeris_path() == "/explicit/operator/path"


def test_profile_selection_rejects_conflicting_modes_and_bad_download(
    profile, monkeypatch, capsys
):
    with pytest.raises(SystemExit):
        fetch_ephe.main(["--profile", "fengshui_calendar", "--years", "2026"])
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda *a, **k: b"<html>not data</html>"
    )
    assert fetch_ephe.main(["--profile", "fengshui_calendar"]) == 1
    assert install.verified_user_ephemeris_dir() is None
    assert "not Swiss" in capsys.readouterr().err


@pytest.mark.parametrize(
    "system,suffix",
    [
        ("Darwin", "Library/Caches/fatebridge/ephe"),
        ("Linux", ".cache/fatebridge/ephe"),
        ("Windows", "AppData/Local/fatebridge/ephe"),
    ],
)
def test_platform_cache_location_and_relative_xdg_rejection(
    monkeypatch, tmp_path, system, suffix
):
    monkeypatch.setenv("XDG_CACHE_HOME", "relative-and-not-usable")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(install.platform, "system", lambda: system)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert install.user_ephemeris_dir() == tmp_path / suffix


def test_unsupported_cache_path_cannot_claim_ready_or_download(
    profile, monkeypatch, tmp_path, capsys
):
    directory = tmp_path / ("长" * 100)
    monkeypatch.setattr(install, "user_ephemeris_dir", lambda: directory)
    monkeypatch.setattr(fetch_ephe, "user_ephemeris_dir", lambda: directory)
    assert install.verified_user_ephemeris_dir() is None
    assert fetch_ephe.main(["--profile", "fengshui_calendar"]) == 1
    assert "shorter --dest" in capsys.readouterr().err
    assert profile[1] == []


def test_partial_explicit_cache_does_not_claim_automatic_discovery(profile, capsys):
    assert (
        fetch_ephe.main(
            ["--files", "sepl_18.se1", "--dest", str(install.user_ephemeris_dir())]
        )
        == 0
    )
    assert "Set SE_EPHE_PATH" in capsys.readouterr().out


def test_doctor_reports_identity_and_setup_without_acquisition(profile):
    from fatebridge.diagnostics import diagnose

    before = diagnose(family="fengshui")["fengshui_calendar"]
    assert not before["user_cache"]["all_files_verified"]
    assert before["setup_argv"][-2:] == ["--profile", "fengshui_calendar"]
    assert profile[1] == [] and not install.user_ephemeris_dir().exists()
    assert fetch_ephe.main(["--profile", "fengshui_calendar"]) == 0
    after = diagnose(family="fengshui")["fengshui_calendar"]
    assert after["user_cache"]["all_files_verified"]
    assert after["astronomical_acceptance"].startswith("not_run_by_doctor")
    assert len(profile[1]) == 4


def test_explicit_cache_behind_project_precedence_requires_explicit_path(
    profile, capsys
):
    project = fetch_ephe.default_dest()
    project.mkdir(parents=True)
    (project / "user-managed.se1").write_bytes(b"SW-custom-unchanged")
    assert (
        fetch_ephe.main(
            [
                "--profile",
                "fengshui_calendar",
                "--dest",
                str(install.user_ephemeris_dir()),
            ]
        )
        == 0
    )
    assert install.verified_user_ephemeris_dir() is not None
    assert ephemeris_runtime.default_ephe_dir() == str(project)
    assert "Set SE_EPHE_PATH" in capsys.readouterr().out


@pytest.mark.parametrize("same", [True, False])
def test_existing_environment_path_is_not_misreported_as_auto_discovery(
    profile, monkeypatch, tmp_path, capsys, same
):
    destination = install.user_ephemeris_dir()
    monkeypatch.setenv(
        "SE_EPHE_PATH", str(destination if same else tmp_path / "operator-selected")
    )
    assert fetch_ephe.main(["--profile", "fengshui_calendar"]) == 0
    output = capsys.readouterr().out
    assert "auto-discovers" not in output
    assert ("already includes" if same else "selects another") in output
