"""A Swiss top-level bit cannot certify an analytical lunar dependency."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro.birth_clock import solar_clock_components
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.reference_data import verify_source_files

FIXTURE = Path(__file__).parents[1] / "data/astro/mixed_moon"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def test_raw_reference_is_pre_candidate_and_preserves_counterevidence():
    verify_source_files(FIXTURE)
    assert all(not row["fatebridge_imported"] for row in REFERENCE["results"].values())
    full = REFERENCE["results"]["full"]["rows"][1]
    partial = REFERENCE["results"]["planet_only"]["rows"][1]
    assert partial["retflag"] & 7 == 2
    assert abs(partial["position"][0] - full["position"][0]) * 3600 > 0.02
    order = json.loads((FIXTURE / "order-reference.json").read_text())
    assert len(order["rows"]) == 32
    # A cold Moon still exhibits it: it was not just a Sun-preload cache error.
    cold = next(r for r in order["rows"] if r["id"] == "planet_only-0")
    assert cold["states"][0]["retflag"] & 7 == 2


@pytest.fixture(scope="module")
def directories(tmp_path_factory):
    source = Path(runtime.default_ephe_dir() or "")
    assert (source / "sepl_18.se1").is_file() and (
        source / "semo_18.se1"
    ).is_file(), "Pinned native fixture data must be installed; missing files are not a passing analytical substitute"
    base = tmp_path_factory.mktemp("mixed-native-data")
    roots = {}
    for name, files in [
        ("full", ["sepl_18.se1", "semo_18.se1"]),
        ("planet_only", ["sepl_18.se1"]),
        ("empty", []),
    ]:
        p = base / name
        p.mkdir()
        for filename in files:
            shutil.copy2(source / filename, p / filename)
        roots[name] = p
    return roots


@pytest.fixture
def selected(directories, monkeypatch):
    previous = runtime.configured_ephemeris_path()
    with monkeypatch.context() as patch:

        def select(name):
            patch.setenv("SE_EPHE_PATH", str(directories[name]))
            runtime.configure_ephemeris_path(str(directories[name]))

        yield select
    runtime.configure_ephemeris_path(previous)


@pytest.fixture(scope="module")
def native_controls(directories):
    """Fresh same-runtime native controls; frozen macOS literals stay intact.

    The two original literal-equality tests failed on Linux by tiny native
    floating differences. Their source/XML are retained; this does not turn
    same-runtime preservation into independent astronomical accuracy.
    """
    code = """
import json,sys,swisseph as s,platform,hashlib
from pathlib import Path
s.set_ephe_path(sys.argv[1]); rows=[]
for jd in [2451545.0,2461193.0]:
 for body in range(15):
  p,f=s.calc(jd,body,int(sys.argv[2]));rows.append(dict(jd_tt=jd,body=body,position=list(p),retflag=f))
print(json.dumps(dict(rows=rows,native=s.version,python=sys.version,platform=platform.platform(),binary_sha256=hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest(),fatebridge_imported=any(n=='fatebridge' or n.startswith('fatebridge.') for n in sys.modules))))
"""
    result = {}
    for name, flags in [("full", 258), ("empty", 260)]:
        root = str(directories[name])
        captured = subprocess.run(
            [sys.executable, "-I", "-c", code, root, str(flags)],
            env={**os.environ, "SE_EPHE_PATH": root},
            text=True,
            capture_output=True,
            check=True,
        )
        result[name] = json.loads(captured.stdout)
        assert not result[name]["fatebridge_imported"]
        (directories[name].parent / (name + "-native-control.json")).write_text(
            captured.stdout
        )
    return result


@pytest.mark.parametrize("body", list(range(10)))
@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
def test_geocentric_physical_swiss_flag_cannot_hide_missing_lunar_file(
    selected, body, operation
):
    selected("planet_only")
    with pytest.raises(EphemerisSourceError) as error:
        runtime.ephemeris_call(operation, 2451545.0, body, 258)
    assert error.value.reason == "swiss_dependency_unavailable"


@pytest.mark.parametrize("body", [0, 2, 4, 5, 9])
@pytest.mark.parametrize("origin", [8, 16384])
def test_independent_solar_or_planetary_origins_are_not_emptied(selected, body, origin):
    selected("planet_only")
    pos, flag = runtime.ephemeris_call("calc", 2451545.0, body, 258 | origin)
    assert flag & 7 == 2 and len(pos) == 6


@pytest.mark.parametrize("body,origin", [(1, 8), (1, 16384), (14, 8), (14, 16384)])
def test_lunar_target_and_physical_earth_still_need_the_moon(selected, body, origin):
    selected("planet_only")
    with pytest.raises(EphemerisSourceError, match="Moon file coverage"):
        runtime.ephemeris_call("calc", 2451545.0, body, 258 | origin)


@pytest.mark.parametrize("body", [10, 12, 14])
def test_nonphysical_nodes_apogee_and_zero_geocentric_earth_do_not_claim_vectors(
    selected, body
):
    selected("empty")
    pos, flag = runtime.ephemeris_call("calc", 2451545.0, body, 258)
    assert flag & 7 == 2 and len(pos) == 6
    if body == 14:
        assert set(pos) == {0}


@pytest.mark.parametrize("body", list(range(10)))
def test_explicit_analytical_control_is_preserved(selected, native_controls, body):
    selected("empty")
    actual = runtime.ephemeris_call("calc", 2451545.0, body, 260)
    expected = native_controls["empty"]["rows"][body]
    assert actual == (tuple(expected["position"]), expected["retflag"])


def test_complete_declared_native_sequence_retains_every_value(
    selected, native_controls
):
    selected("full")
    for row in native_controls["full"]["rows"]:
        assert runtime.ephemeris_call("calc", row["jd_tt"], row["body"], 258) == (
            tuple(row["position"]),
            row["retflag"],
        )


def test_solar_clock_source_failure_does_not_become_a_clock_or_astrological_answer(
    selected,
):
    from datetime import datetime, timezone

    selected("planet_only")
    with pytest.raises(EphemerisSourceError) as error:
        solar_clock_components(
            datetime(2000, 1, 1, 12, tzinfo=timezone.utc),
            0,
            "local_apparent_solar",
            ephemeris_policy="require_data_files",
        )
    assert error.value.reason == "swiss_dependency_unavailable"


def test_nonempty_but_stale_moon_slot_does_not_prove_current_coverage(monkeypatch):
    from types import SimpleNamespace

    from fatebridge.core import compressed_ephemeris as context

    monkeypatch.setattr(
        context, "binding_distribution_version", lambda *args: "2.10.3.2"
    )
    native = SimpleNamespace(version="2.10.03")
    with pytest.raises(EphemerisSourceError) as error:
        context._require_observer_windows(
            native,
            0,
            258,
            50.0,
            (("planet", 0.0, 100.0, 441), ("stale_moon", 0.0, 25.0, 441)),
        )
    assert error.value.reason == "swiss_dependency_unavailable"
