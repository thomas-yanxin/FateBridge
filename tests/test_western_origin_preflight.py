"""An auxiliary observer must not replace the requested coordinate origin."""

import json
import os
import shutil
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.compressed_ephemeris import (
    audit_compressed_endpoints,
    coordinate_context_evidence,
)
from fatebridge.utils.errors import EphemerisSourceError
from tests.reference_data import verify_source_files

FIXTURE = Path(__file__).parent / "data/astro/origin_preflight"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
FRAMES = [
    ("tropical", 0),
    ("lahiri", 65536),
    ("equatorial", 2048),
    ("icrf", 4096 | 2048 | 32 | 131072),
]


def test_pre_candidate_reference_preserves_all_native_frames_and_failures():
    verify_source_files(FIXTURE)
    assert (
        len(REFERENCE["cohorts"]) == 44
        and sum(len(c["rows"]) for c in REFERENCE["cohorts"]) == 882
    )
    assert all(not c["fatebridge_imported"] for c in REFERENCE["cohorts"])


@pytest.fixture(scope="module")
def directories(tmp_path_factory):
    source = Path(runtime.default_ephe_dir() or "")
    assert (source / "sepl_24.se1").is_file() and (
        source / "semo_24.se1"
    ).is_file(), (
        "Install the pinned complete native fixture profile; no analytical substitution"
    )
    base = tmp_path_factory.mktemp("origin-native-data")
    roots = {}
    for name in ["full", "planet_only", "empty"]:
        p = base / name
        p.mkdir()
        roots[name] = p
        for f in source.glob("*.se1"):
            if (
                name == "empty"
                or name == "planet_only"
                and not f.name.startswith("sepl_")
            ):
                continue
            shutil.copy2(f, p / f.name)
    return roots


@pytest.fixture
def selected(directories, monkeypatch):
    previous = runtime.configured_ephemeris_path()
    with monkeypatch.context() as patch:

        def select(name):
            patch.setenv("SE_EPHE_PATH", str(directories[name]))
            runtime.configure_ephemeris_path(str(directories[name]))
            runtime.ephemeris_call("set_sid_mode", runtime.swe.SIDM_LAHIRI)
            runtime.ephemeris_call("set_topo", 0.0, 0.0, 0.0)

        yield select
    runtime.configure_ephemeris_path(previous)


def calculate(selected, mode, operation, epoch, body, flags, owned=True):
    selected(mode)
    with audit_compressed_endpoints() if owned else nullcontext():
        value = runtime.ephemeris_call(operation, epoch, body, flags)
        receipt = coordinate_context_evidence() if owned else None
    return value, receipt


@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize("frame,extra", FRAMES)
@pytest.mark.parametrize("origin", [8, 16384])
@pytest.mark.parametrize("owned", [False, True])
def test_missing_unused_moon_does_not_change_owned_values_or_file_endpoints(
    selected, operation, frame, extra, origin, owned
):
    flags = 258 | extra | origin
    for epoch in REFERENCE["epochs"]:
        for body in [0, *range(2, 10)]:
            full, basis = calculate(
                selected, "full", operation, epoch, body, flags, owned
            )
            partial, receipt = calculate(
                selected, "planet_only", operation, epoch, body, flags, owned
            )
            assert partial == full
            if not owned:
                assert receipt is None
                if body == 0 and origin == 8:
                    assert set(partial[0]) == {0}
                else:
                    _, start, end, _ = runtime.swe.get_current_file_data(0)
                    tt = (
                        epoch
                        if operation == "calc"
                        else epoch + runtime.swe.deltat_ex(epoch, partial[1] & 7)
                    )
                    assert start <= tt <= end
                continue
            assert receipt["selected_native_state"] == list(partial[0])
            assert (
                receipt["input_julian_day"] == epoch
                and receipt["operation"] == operation
            )
            assert receipt["physical_instant_shifted"] is False
            assert receipt["preflight_establishes_geocentric_observer"] is False
            assert receipt["preflight_reference_origin"] == (
                "heliocentric" if body == 0 and origin == 8 else "barycentric"
            )
            assert receipt["coordinate_reference_origin"] == (
                "heliocentric" if origin == 8 else "barycentric"
            )
            if origin == 8 and body != 0:
                assert receipt["preflight_model_probe"]["coordinates_discarded"] is True
                assert (
                    receipt["preflight_model_probe"]["native_context_reset_after_probe"]
                    is True
                )
                assert (
                    receipt["preflight_model_probe"]["physical_source_certified"]
                    is False
                )
            windows = receipt["selected_windows"]
            if body == 0 and origin == 8:
                assert set(partial[0]) == {0} and windows == []
            else:
                assert [w["slot"] for w in windows] == [0]
                assert all(
                    w["start_jd_tt"] <= receipt["physical_jd_tt"] <= w["end_jd_tt"]
                    for w in windows
                )


@pytest.mark.parametrize("owned", [False, True])
@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize(
    "flags", [258 | 8 | 32768, 258 | 16384 | 32768, 258 | 8 | 16384 | 32768]
)
@pytest.mark.parametrize("body", [0, 4])
def test_native_normalized_topocentric_origin_still_requires_real_observer(
    selected, owned, operation, flags, body
):
    with pytest.raises(EphemerisSourceError) as error:
        calculate(selected, "planet_only", operation, 2451545.0, body, flags, owned)
    assert error.value.reason == "swiss_dependency_unavailable"


@pytest.mark.parametrize("mode", ["full", "planet_only", "empty"])
@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize(
    "body,flags",
    [
        (14, 258),
        (14, 258 | 32768),
        (14, 258 | 8 | 32768),
        (14, 258 | 16384 | 32768),
        (0, 266),
        (0, 266 | 65536),
    ],
)
def test_reference_identities_do_not_require_unused_physical_data(
    selected, mode, operation, body, flags
):
    value, basis = calculate(selected, mode, operation, 2451545.0, body, flags)
    assert set(value[0]) == {0} and basis["selected_windows"] == []
    assert basis["preflight_solar_vector_is_defined_zero"] is True
    assert basis["coordinate_is_defined_zero"] is True
    assert basis["coordinate_represents_physical_body_vector"] is False


@pytest.mark.parametrize("year", [1, 600, 3001, 4000, 9000, 9999])
@pytest.mark.parametrize("mode", ["full", "planet_only", "empty"])
@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
def test_wide_native_reference_identities_are_not_limited_by_unused_moon_range(
    selected, year, mode, operation
):
    epoch = runtime.swe.julday(year, 1, 1, 12.0)
    for body, flags in [(0, 266), (14, 258)]:
        value, basis = calculate(selected, mode, operation, epoch, body, flags)
        assert set(value[0]) == {0} and basis["selected_windows"] == []
        assert basis["coordinate_is_defined_zero"] is True


@pytest.mark.parametrize("year", [4000, 9000, 9999])
def test_native_nonzero_range_failures_are_not_replaced_by_reference_zero(
    selected, year
):
    epoch = runtime.swe.julday(year, 1, 1, 12.0)
    for body, flags in [(0, 258 | 16384), (4, 266), (4, 258 | 16384)]:
        with pytest.raises(runtime.swe.Error) as error:
            calculate(selected, "planet_only", "calc", epoch, body, flags)
        # Native serr has a fixed byte budget; a long sandbox path can truncate
        # the later range wording. The typed failure and missing lunar file
        # remain the contract, rather than a successful zero/fallback result.
        assert "semo_" in str(error.value) and "not found" in str(error.value)


@pytest.mark.parametrize("owned", [False, True])
@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize("body", [1, 14])
@pytest.mark.parametrize("origin", [8, 16384])
def test_actual_lunar_and_earth_vectors_still_require_lunar_data(
    selected, owned, operation, body, origin
):
    with pytest.raises(EphemerisSourceError) as error:
        calculate(
            selected, "planet_only", operation, 2451545.0, body, 258 | origin, owned
        )
    assert error.value.reason == "swiss_dependency_unavailable"


@pytest.fixture(scope="module")
def cold_native_controls(directories):
    code = """import json,sys,swisseph as s,platform,hashlib
from pathlib import Path
s.set_ephe_path(sys.argv[1]);s.set_sid_mode(s.SIDM_LAHIRI);out=[]
for op in ['calc','calc_ut']:
 for extra in [0,65536,2048,4096|2048|32|131072]:
  for origin in json.loads(sys.argv[2]):
   for body in json.loads(sys.argv[3]):
    s.set_ephe_path(sys.argv[1]);p,f=getattr(s,op)(2451545.,body,258|extra|origin);out.append(dict(op=op,extra=extra,origin=origin,body=body,position=list(p),retflag=f))
print(json.dumps(dict(rows=out,native=s.version,python=sys.version,platform=platform.platform(),binary_sha256=hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest(),fatebridge_imported=any(n=='fatebridge' or n.startswith('fatebridge.') for n in sys.modules))))"""
    controls = {}
    for mode, origins, bodies in [
        ("planet_only", [8, 16384], [0, *range(2, 10)]),
        ("empty", [8], [*range(10), 14]),
    ]:
        root = str(directories[mode])
        p = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                code,
                root,
                json.dumps(origins),
                json.dumps(bodies),
            ],
            env={**os.environ, "SE_EPHE_PATH": root},
            capture_output=True,
            text=True,
            check=True,
        )
        v = json.loads(p.stdout)
        assert not v["fatebridge_imported"]
        (directories[mode].parent / ("native-controls-" + mode + ".json")).write_text(
            p.stdout
        )
        controls[mode] = v["rows"]
    return controls


def test_ordinary_owned_coordinates_match_fresh_same_runtime_native_exactly(
    selected, cold_native_controls
):
    assert len(cold_native_controls["planet_only"]) == 144
    for row in cold_native_controls["planet_only"]:
        value, _ = calculate(
            selected,
            "planet_only",
            row["op"],
            2451545.0,
            row["body"],
            258 | row["extra"] | row["origin"],
        )
        assert value == (tuple(row["position"]), row["retflag"])


def test_heliocentric_analytical_fallback_retains_same_runtime_native_values(
    selected, cold_native_controls
):
    assert len(cold_native_controls["empty"]) == 88
    for row in cold_native_controls["empty"]:
        value, basis = calculate(
            selected,
            "empty",
            row["op"],
            2451545.0,
            row["body"],
            258 | row["extra"] | row["origin"],
        )
        assert value == (tuple(row["position"]), row["retflag"])
        assert basis["preflight_reference_origin"] == "heliocentric"
        if row["body"] not in {0, 14}:
            assert basis["preflight_model_probe"]["returned_flags"] & 7 == 4
