"""Real C-library path precedence, custom identities and orbit-source receipts."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.fictitious_elements import fictitious_element_source
from fatebridge.core.astro.midpoints import _native_factors
from fatebridge.core.astro.sensitivity import (
    enrich_specialty_sensitivity,
    time_sensitivity,
)
from fatebridge.services.astrology import calculate_germany_chart_analysis
from tests.fixtures.hamburg_orbits import ROWS, write_orbits

HAS_SWE = pytest.mark.skipif(e.swe is None, reason="Swiss Ephemeris required")


@pytest.fixture(autouse=True)
def restore_configuration(monkeypatch):
    previous = e.configured_ephemeris_path()
    previous_env = os.environ.get("SE_EPHE_PATH")
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    yield
    if previous_env is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", previous_env)
    e.configure_ephemeris_path(previous if previous is not None else "")


def _birth():
    return build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )


@HAS_SWE
def test_real_library_environment_override_matches_reported_path(
    tmp_path: Path,
) -> None:
    a, b = tmp_path / "env", tmp_path / "explicit"
    write_orbits(a)
    write_orbits(b, cupido_anomaly="210.0000")
    code = """import json,sys
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.fictitious_elements import fictitious_element_source
selected=e.configure_ephemeris_path(sys.argv[1])
x,flag=e.ephemeris_call('calc',2451545.,40,e.swe.FLG_SWIEPH)
print(json.dumps({'path':selected,'longitude':x[0],'source':fictitious_element_source()}))
"""

    def run(envpath, explicit):
        env = dict(os.environ)
        env.pop("SE_EPHE_PATH", None)
        if envpath is not None:
            env["SE_EPHE_PATH"] = str(envpath)
        else:
            pass
        result = subprocess.run(
            [sys.executable, "-c", code, str(explicit)],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    only_a, only_b, conflict = run(a, a), run(None, b), run(a, b)
    assert abs(only_a["longitude"] - only_b["longitude"]) > 40
    assert conflict["longitude"] == only_a["longitude"]
    assert conflict["path"] == str(a)
    assert conflict["source"]["status"] == "external_file"
    assert conflict["source"]["filename"] == "seorbel.txt"
    assert conflict["source"]["search_path_index"] == 0


@HAS_SWE
def test_default_current_directory_and_first_readable_search_entry_are_traced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = tmp_path / "current", tmp_path / "later"
    write_orbits(a)
    write_orbits(b, cupido_anomaly="210.0000")
    monkeypatch.chdir(a)
    e.configure_ephemeris_path("")
    assert fictitious_element_source()["status"] == "external_file"
    assert fictitious_element_source()["filename"] == "seorbel.txt"
    # An empty first search segment denotes the working directory in Swiss.
    e.configure_ephemeris_path(os.pathsep + str(b))
    native = _native_factors(_birth(), False)
    assert native["hypothetical_element_source"]["search_path_index"] == 0
    assert native["hypothetical_element_source"]["status"] == "external_file"
    assert native["hypothetical_element_source"]["filename"] == "seorbel.txt"
    assert str(a) not in json.dumps(native["hypothetical_element_source"])

    # Swiss ends the path at LF. The empty second root searches the cwd.
    e.configure_ephemeris_path("missing;\n" + str(b))
    native = _native_factors(_birth(), False)
    assert native["hypothetical_element_source"]["search_path_index"] == 1
    assert native["hypothetical_element_source"]["status"] == "external_file"
    assert native["hypothetical_element_source"]["filename"] == "seorbel.txt"


@HAS_SWE
@pytest.mark.parametrize("nested", [False, True])
def test_fictitious_source_skips_non_directory_search_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nested: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    write_orbits(tmp_path / "usable", cupido_anomaly="210.0000")
    blocker = "ordinary-file"
    (tmp_path / blocker).touch()
    unusable = f"{blocker}/not-reachable" if nested else blocker
    e.configure_ephemeris_path("missing;usable")
    expected = _native_factors(_birth(), False)
    e.configure_ephemeris_path(f"{unusable};usable")
    actual = _native_factors(_birth(), False)
    assert actual["hypothetical_element_source"]["search_path_index"] == 1
    assert actual["hypothetical_element_source"]["status"] == "external_file"
    assert actual["hypothetical_element_source"]["filename"] == "seorbel.txt"
    assert actual == expected


@HAS_SWE
def test_same_directory_orbit_edits_update_positions_and_receipt_without_cache_reset(
    tmp_path: Path,
) -> None:
    source = write_orbits(tmp_path)
    e.configure_ephemeris_path(str(tmp_path))
    before = _native_factors(_birth(), False)
    stat = source.stat()
    write_orbits(tmp_path, cupido_anomaly="164.7409")
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    after = _native_factors(_birth(), False)
    before_cupido = next(row for row in before["factors"] if row["id"] == "Cupido")
    after_cupido = next(row for row in after["factors"] if row["id"] == "Cupido")
    assert before_cupido["longitude"] != after_cupido["longitude"]
    assert before["hypothetical_element_source"]["status"] == "external_file"
    assert after["hypothetical_element_source"]["status"] == "external_file"


@HAS_SWE
def test_reordered_custom_bodies_are_not_mislabeled_as_hamburg_factors(
    tmp_path: Path,
) -> None:
    source = write_orbits(tmp_path)
    rows = list(ROWS)
    rows[0], rows[1] = rows[1], rows[0]
    source.write_text("\n".join(rows) + "\n")
    e.configure_ephemeris_path(str(tmp_path))
    with pytest.raises(ValueError, match="cannot label an unrelated orbit"):
        _native_factors(_birth(), False)


@HAS_SWE
def test_malformed_first_fictitious_table_is_a_native_calculation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "seorbel.txt").write_text("J1900,J1900\n", encoding="ascii")
    write_orbits(tmp_path / "usable")
    e.configure_ephemeris_path("broken;usable")

    result = calculate_germany_chart_analysis(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=30,
        zodiac_type="Tropic",
    )

    assert result["error_code"] == "ephemeris_calculation_failed"
    assert result["status_code"] == 503
    assert result["retryable"] is False
    assert "seorbel.txt" not in result["error"]


@HAS_SWE
def test_orbit_change_during_one_factor_calculation_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_orbits(tmp_path)
    e.configure_ephemeris_path(str(tmp_path))
    original = e.swe.calc

    def change_after_cupido(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[1] == 40:
            (tmp_path / "seorbel.txt").unlink()
        else:
            pass
        return result

    monkeypatch.setattr(e.swe, "calc", change_after_cupido)
    with pytest.raises(ValueError, match="source changed during"):
        _native_factors(_birth(), False)


@HAS_SWE
def test_orbit_change_between_birth_time_samples_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fatebridge.core.astro.sensitivity as sensitivity

    write_orbits(tmp_path)
    e.configure_ephemeris_path(str(tmp_path))
    calls = []

    def change_after_first(*args, **kwargs):
        result = _native_factors(*args, **kwargs)
        calls.append(result)
        if len(calls) == 1:
            (tmp_path / "seorbel.txt").unlink()
        else:
            pass
        return result

    monkeypatch.setattr(sensitivity, "_native_factors", change_after_first)
    with pytest.raises(ValueError, match="source changed across"):
        time_sensitivity(_birth(), sidereal=False, uncertainty_minutes=1)


@HAS_SWE
def test_changed_environment_is_applied_to_an_existing_direct_call_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    write_orbits(a)
    write_orbits(b, cupido_anomaly="210.0000")
    e.configure_ephemeris_path(str(a))
    first = e.ephemeris_call("calc", 2451545.0, 40, e.swe.FLG_SWIEPH)[0][0]
    monkeypatch.setenv("SE_EPHE_PATH", str(b))
    second = e.ephemeris_call("calc", 2451545.0, 40, e.swe.FLG_SWIEPH)[0][0]
    assert abs(second - first) > 40
    assert e.configured_ephemeris_path() == str(b)


@pytest.mark.parametrize("path", ["x" * 243, "界" * 81, "bad\0path"])
@HAS_SWE
def test_silent_library_path_fallbacks_are_rejected(path) -> None:
    with pytest.raises(ValueError, match="encoded bytes"):
        e.configure_ephemeris_path(path)


@HAS_SWE
def test_real_long_directory_would_silently_select_different_orbits(
    tmp_path: Path,
) -> None:
    short = tmp_path / "short"
    write_orbits(short, cupido_anomaly="210.0000")
    suffix = "x" * (243 - len(os.fsencode(str(tmp_path))) - 1)
    long = tmp_path / suffix
    write_orbits(long, cupido_anomaly="210.0000")
    assert len(os.fsencode(str(long))) == 243
    e.swe.set_ephe_path("")
    builtin = e.swe.calc(2451545.0, 40, e.swe.FLG_SWIEPH)[0][0]
    e.swe.set_ephe_path(str(short))
    custom = e.swe.calc(2451545.0, 40, e.swe.FLG_SWIEPH)[0][0]
    e.swe.set_ephe_path(str(long))
    silently_selected = e.swe.calc(2451545.0, 40, e.swe.FLG_SWIEPH)[0][0]
    assert abs(custom - builtin) > 40
    assert silently_selected == builtin
    with pytest.raises(ValueError):
        e.configure_ephemeris_path(str(long))


@HAS_SWE
def test_nominal_chart_and_birth_interval_cannot_use_different_orbit_files(
    tmp_path: Path,
) -> None:
    write_orbits(tmp_path)
    e.configure_ephemeris_path(str(tmp_path))
    payload = calculate_germany_chart_analysis(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    (tmp_path / "seorbel.txt").unlink()
    with pytest.raises(ValueError, match="differs between nominal chart"):
        enrich_specialty_sensitivity(
            payload, _birth(), kind="germany", uncertainty_minutes=1
        )


@HAS_SWE
def test_equal13_time_samples_do_not_depend_on_unrelated_fictitious_orbits(
    tmp_path: Path,
) -> None:
    from fatebridge.services.astrology import calculate_core_chart_analysis

    source = write_orbits(tmp_path)
    # Valid Swiss custom bodies, but no longer a Hamburg catalogue. German
    # charts must reject these labels; equal13 physical geometry does not use it.
    source.write_text(source.read_text().replace("Cupido", "DifferentBody"))
    e.configure_ephemeris_path(str(tmp_path))
    result = calculate_core_chart_analysis(
        chart_variant="chart13",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=1,
    )
    sampled = result["time_sensitivity"]
    assert sampled["status"] == "sampled"
    assert sampled["factor_scope"] == "physical_reference"
    assert sampled["factor_count"] == 14
    assert sampled["hypothetical_element_source"]["status"] == "not_used"
    assert "Cupido" not in sampled["samples"][0]["factor_longitudes"]
    assert sampled["sector_assignments"]
    with pytest.raises(ValueError, match="cannot label an unrelated orbit"):
        _native_factors(_birth(), False)
