"""Installed Human Design data readiness, distinct from accuracy acceptance."""

from datetime import datetime, timedelta

import pytest

from fatebridge import fetch_ephe
from fatebridge.core import ephemeris_installation as install
from fatebridge.core import ephemeris_runtime
from fatebridge.core.human_design_cycles import HORIZON_DAYS
from fatebridge.core.requests.human_design import HumanDesignRequest
from tests.fixtures.ephemeris_manifest import manifest_for_payloads


@pytest.fixture(autouse=True)
def preserve_operator_ephemeris_configuration():
    # The empty operator path is an intentional case, not the configuration
    # of later tests. Autouse teardown follows monkeypatch's environment
    # restoration; restore the managed path before restoring native C state.
    previous = ephemeris_runtime._configured_path
    with ephemeris_runtime.preserve_ephemeris_path():
        try:
            yield
        finally:
            ephemeris_runtime._configured_path = previous


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.setattr(ephemeris_runtime, "_PROJECT_ROOT", tmp_path / "checkout")
    payloads = {
        name: b"SW-test-human-design-" + name.encode()
        for name in install.HUMAN_DESIGN_FILES
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


def test_profile_covers_public_birth_extrema_design_and_optional_cycle_horizon():
    schema = HumanDesignRequest.model_json_schema()["properties"]
    # Account conservatively for any legal civil UTC offset, the uncertainty
    # interval, and the actual existing Design search bracket/horizon.
    margin = timedelta(
        days=1, minutes=schema["birth_time_uncertainty_minutes"]["maximum"]
    )
    first = (
        datetime(schema["birth_year"]["minimum"], 1, 1) - margin - timedelta(days=110)
    )
    last = (
        datetime(schema["birth_year"]["maximum"], 12, 31, 23, 59, 59)
        + margin
        + timedelta(days=HORIZON_DAYS)
    )
    assert install.HUMAN_DESIGN_FIRST_YEAR <= first.year
    assert last.year <= install.HUMAN_DESIGN_LAST_YEAR
    assert set(install.HUMAN_DESIGN_FILES) == {
        "sepl_12.se1",
        "semo_12.se1",
        "seas_12.se1",
        "sepl_18.se1",
        "semo_18.se1",
        "seas_18.se1",
        "sepl_24.se1",
        "semo_24.se1",
        "seas_24.se1",
    }
    assert len(install.HUMAN_DESIGN_FILES) == 9


def test_profile_acquires_all_nine_files_and_cache_is_discovered(profile, capsys):
    _, calls = profile
    directory = install.user_ephemeris_dir()
    assert not directory.exists()
    assert fetch_ephe.main(["--profile", "human_design"]) == 0
    assert len(calls) == 9
    status = install.human_design_file_status(directory)
    assert status["all_files_verified"]
    assert status["computation_years_inclusive"] == [1799, 2465]
    assert (
        status["scope"]
        == "file_content_identity_not_loaded_model_or_astronomical_acceptance"
    )
    assert ephemeris_runtime.default_ephe_dir() == str(directory)
    assert "auto-discovers" in capsys.readouterr().out
    assert fetch_ephe.main(["--profile", "human_design", "--verify-only"]) == 0
    assert len(calls) == 9


@pytest.mark.parametrize("missing", install.HUMAN_DESIGN_FILES)
def test_each_missing_file_keeps_full_human_design_profile_incomplete(profile, missing):
    payloads, _ = profile
    directory = install.user_ephemeris_dir()
    directory.mkdir(parents=True)
    for name, data in payloads.items():
        if name != missing:
            (directory / name).write_bytes(data)
    status = install.human_design_file_status(directory)
    assert not status["all_files_verified"]
    assert not status["files"][missing]["verified"]
    assert sum(row["verified"] for row in status["files"].values()) == 8
    # A complete older Feng Shui cache may still be discovered. Discovery must
    # never be interpreted as a complete Human Design data/accuracy certificate.
    assert (install.verified_user_ephemeris_dir() is not None) == (
        missing not in install.FENGSHUI_FILES
    )


def test_existing_partial_checkout_is_completed_in_place(profile):
    payloads, calls = profile
    directory = fetch_ephe.default_dest()
    directory.mkdir(parents=True)
    for name in ("sepl_18.se1", "semo_18.se1"):
        (directory / name).write_bytes(payloads[name])
    assert fetch_ephe.main(["--profile", "human_design"]) == 0
    assert len(calls) == 7
    assert install.human_design_file_status(directory)["all_files_verified"]
    assert ephemeris_runtime.default_ephe_dir() == str(directory)
    assert not install.user_ephemeris_dir().exists()


def test_other_profile_does_not_claim_human_design_ready(profile):
    assert fetch_ephe.main(["--profile", "fengshui_calendar"]) == 0
    directory = install.user_ephemeris_dir()
    assert install.fengshui_file_status(directory)["all_files_verified"]
    assert not install.human_design_file_status(directory)["all_files_verified"]
    assert len(profile[1]) == 4
    assert fetch_ephe.main(["--profile", "human_design"]) == 0
    assert len(profile[1]) == 9


def test_explicit_environment_and_project_precedence_are_preserved(
    profile, monkeypatch, tmp_path, capsys
):
    assert fetch_ephe.main(["--profile", "human_design"]) == 0
    capsys.readouterr()
    explicit = tmp_path / "empty-operator-path"
    explicit.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(explicit))
    assert fetch_ephe.main(["--profile", "human_design", "--verify-only"]) == 0
    assert "selects another directory" in capsys.readouterr().out
    assert ephemeris_runtime.configure_ephemeris_path() == str(explicit)


def test_doctor_is_read_only_reports_profile_and_does_not_certify_accuracy(
    profile, monkeypatch
):
    from fatebridge.core.astro import runtime
    from fatebridge.diagnostics import diagnose

    def forbidden(*args, **kwargs):
        raise AssertionError("Readiness inspection must not acquire or calculate")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    before = diagnose()["human_design"]
    assert not before["user_cache"]["all_files_verified"]
    assert before["setup_argv"][-2:] == ["--profile", "human_design"]
    assert profile[1] == [] and not install.user_ephemeris_dir().exists()
    assert fetch_ephe.main(["--profile", "human_design"]) == 0
    after = diagnose()["human_design"]
    assert after["user_cache"]["all_files_verified"]
    assert after["astronomical_acceptance"].startswith("not_run_by_doctor")
    assert len(profile[1]) == 9


def test_bad_download_and_offline_verification_leave_failure_visible(
    profile, monkeypatch, capsys
):
    monkeypatch.setattr(
        fetch_ephe, "_download", lambda *args, **kwargs: b"<html>error</html>"
    )
    assert fetch_ephe.main(["--profile", "human_design"]) == 1
    assert "not Swiss" in capsys.readouterr().err
    assert not install.human_design_file_status(install.user_ephemeris_dir())[
        "all_files_verified"
    ]
    assert fetch_ephe.main(["--profile", "human_design", "--verify-only"]) == 1
    assert not install.user_ephemeris_dir().exists()


def test_profile_modes_remain_mutually_exclusive(profile):
    for option, values in [
        ("--years", ["2000"]),
        ("--year-range", ["1800", "2399"]),
        ("--files", ["sepl_18.se1"]),
    ]:
        with pytest.raises(SystemExit):
            fetch_ephe.main(["--profile", "human_design", option, *values])
    assert profile[1] == []
