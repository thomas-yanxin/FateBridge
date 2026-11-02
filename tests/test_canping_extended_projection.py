"""Full declared horizon after the shared public DE440 range expansion."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import almanac
from fatebridge.core import canping_solar as solar
from fatebridge.core import de440_solar as de440
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.utils.errors import EphemerisSourceError
from tests.canping_scope_fixture_compat import rewind_scope_receipt_checked
from tests.canping_witness_fixture_compat import rewind_reviewed_witness_summary
from tests.numerology_clock_input_fixture_compat import rewind_prior_clock_input

ROOT = Path(__file__).parent / "fixtures/canping_extended_projection_v1"
P = json.loads((ROOT / "protocol.json").read_bytes())
NEW = P["model_id"]
EXTENDED = "fatebridge_de440_solar_extended_v1"
DATA = Path(de440.__file__).parents[1] / "data/astronomy"
CONTROLS = json.loads(gzip.decompress((ROOT / "legacy-controls.json.gz").read_bytes()))


@pytest.fixture(autouse=True)
def controlled_model(monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty"))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    caches = [
        de440._profile,
        solar._root,
        solar._extended_root,
        almanac.get_solar_terms_for_year,
    ]
    for cache in caches:
        cache.cache_clear()
    yield
    for cache in caches:
        cache.cache_clear()


def event(year):
    return solar.projection_boundary(
        year,
        "UTC",
        origin_civil_year=1700 if year == 1699 else 2300,
        origin_bazi_year=1699 if year == 1699 else 2300,
        horizon=120,
    )


def test_frozen_original_references_and_all_preexisting_profile_bytes_preserved():
    freeze = json.loads((ROOT / "freeze.json").read_bytes())
    for name, expected in freeze["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    for name, expected in P["preserve_existing_profiles"].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == expected
    assert de440.CANPING_EXTENDED_MODEL_ID == NEW
    assert (
        de440.source_receipt(NEW)["source_kernel_sha256"]
        == P["source_kernel"]["sha256"]
    )
    assert de440.source_receipt(NEW)["reference_event_table_used"] is False
    assert de440.source_receipt(NEW)["accuracy_certified"] is False


def test_every_predeclared_root_and_original_state_matches_independent_reader():
    reference = json.loads((ROOT / "reference.json").read_bytes())
    states = json.loads((ROOT / "states.json").read_bytes())
    assert reference["production_imports"] is states["production_imports"] is False
    assert [r["year"] for r in reference["rows"]] == P["reference_years"]
    assert len(reference["rows"]) == 121 and len(states["rows"]) == 1452
    failures = []
    for expected in reference["rows"]:
        row = event(expected["year"])
        details = row["record"]["solar_model_details"]
        error = abs(details["selected_crossing_jd_tt"] - expected["jd_tt"]) * 86400
        if error > P["reference_evaluator"]["root_tolerance_seconds"]:
            failures.append((expected["year"], error))
        assert details["numerical_epoch_representation"] == "explicit_two_part_tt"
        assert details["selection_policy"] == P["new_policy_id"]
        assert details["historical_ut1_convention"] is (expected["year"] == 1699)
        assert details["future_leap_seconds_assumed_unchanged"] is (
            expected["year"] != 1699
        )
    assert not failures, failures
    for row in states["rows"]:
        profile = EXTENDED if row["tdb_jd"] < 2400000 else NEW
        pos, vel = de440.state(
            tuple(row[k] for k in ["center", "target"]),
            row["tdb_jd"] - 2451545.0,
            profile_id=profile,
        )
        assert max(abs(a - b) for a, b in zip(pos, row["position_km"])) <= 0.0001
        assert (
            max(abs(a - b) for a, b in zip(vel, row["velocity_km_per_day"])) <= 0.00001
        )


@pytest.mark.parametrize(
    "control", CONTROLS, ids=lambda r: r["mode"] + r["kind"] + str(r["identity"])
)
def test_predeclared_old_range_controls_keep_every_business_value(control, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", control["mode"])
    if control["kind"] == "birth":
        actual = build_canping_result(**control["identity"])
        actual = rewind_prior_clock_input(actual, control["identity"]["time"])
        actual = rewind_scope_receipt_checked(actual, require_present=True)
        actual = rewind_reviewed_witness_summary(actual)
    else:
        q = control["identity"]
        actual = solar.projection_boundary(
            q["year"],
            "UTC",
            origin_civil_year=q["origin"],
            origin_bazi_year=q["bazi"],
            horizon=120,
        )
    assert actual == control["output"]


@pytest.mark.parametrize("mode", ["auto", "de440"])
@pytest.mark.parametrize("method", ["bazi_appendix_v1", "bazi_continuous_v1"])
@pytest.mark.parametrize("date", ["1700-01-03", "2201-05-15", "2300-05-15"])
def test_complete120_years_without_native_substitution(mode, method, date, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    out = build_canping_result(
        date=date,
        time="09:00",
        zone="UTC",
        gender="男",
        use_true_solar_time=False,
        dayun_method=method,
    )
    timing, series = out["canping_timing"], out["liunian_series"]
    ctx = timing["solar_year_context"]
    assert len(series["rows"]) == 120 and len(series["year_boundaries"]) == 121
    assert ctx["boundary_count"] == 121 and ctx["horizon_years"] == 120
    assert "moshier" not in ctx["observed_models"]
    assert ctx["policy_id"] == P["new_policy_id"]
    assert ctx["registered_public_input_years"] == [1700, 2300]
    assert ctx["public_model_years_extended"] is False
    assert timing["selected"] is None and timing["first_period"] == timing["first_row"]
    assert all(row["end_at"] for row in series["rows"])


@pytest.mark.parametrize(
    "year,origin,bazi,horizon",
    [
        (1698, 1700, 1699, 120),
        (2421, 2300, 2300, 120),
        (2420, 2300, 2300, 119),
        (2420, 2300, 2300, True),
        (2420, 2301, 2301, 120),
    ],
)
def test_private_event_permission_never_authorizes_an_unrelated_origin_or_horizon(
    year, origin, bazi, horizon, monkeypatch
):
    def refuse(*args, **kwargs):
        pytest.fail("An invalid caller must not load the additional data")

    monkeypatch.setattr(solar, "_extended_root", refuse)
    with pytest.raises(ValueError):
        solar.projection_boundary(
            year,
            "UTC",
            origin_civil_year=origin,
            origin_bazi_year=bazi,
            horizon=horizon,
        )


@pytest.mark.parametrize("year", [1699, 2420])
def test_warm_private_roots_do_not_expand_standalone_year_api(year):
    event(year)
    with pytest.raises(ValueError, match="1700..2300"):
        almanac.get_solar_terms_for_year(year, "UTC")


@pytest.mark.parametrize("mode", ["native", "analytic", "aa1996"])
def test_explicit_other_modes_do_not_select_additional_de440_events(mode, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    assert solar._extended_event_profile(2420, 2300, mode, None) is None


def test_strict_native_jpl_override_does_not_select_additional_de440(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    assert (
        solar._extended_event_profile(2420, 2300, "auto", "required-native.eph") is None
    )


@pytest.mark.parametrize("fault", ["missing", "crc", "frame", "scope", "rehash"])
def test_selected_corrupt_profile_fails_without_native_fallback(
    fault, tmp_path, monkeypatch
):
    folder = tmp_path / "data/astronomy"
    folder.mkdir(parents=True)
    for name in [
        "de440-solar-canping-extended-v1.json",
        "de440-solar-canping-extended-v1.bin.gz",
        "geocentric-tdb-v1.json",
    ]:
        (folder / name).write_bytes((DATA / name).read_bytes())
    metadata = folder / "de440-solar-canping-extended-v1.json"
    binary = folder / "de440-solar-canping-extended-v1.bin.gz"
    manifest = json.loads(metadata.read_bytes())
    if fault == "missing":
        binary.unlink()
    elif fault == "crc":
        raw = bytearray(binary.read_bytes())
        raw[-1] ^= 1
        binary.write_bytes(raw)
    elif fault == "frame":
        manifest["segments"][0]["frame"] = 2
    elif fault == "scope":
        manifest["projection_origin_civil_years"] = [1, 9999]
    else:
        data = bytearray(gzip.decompress(binary.read_bytes()))
        data[40] ^= 1
        packed = gzip.compress(data, mtime=0)
        binary.write_bytes(packed)
        manifest["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        manifest["uncompressed_sha256"] = hashlib.sha256(data).hexdigest()
        for s in manifest["segments"]:
            manifest_hash = hashlib.sha256(
                data[s["offset_bytes"] : s["offset_bytes"] + s["bytes"]]
            ).hexdigest()
            s["sha256"] = manifest_hash
    metadata.write_text(json.dumps(manifest))
    monkeypatch.setattr(de440, "files", lambda *_: tmp_path)
    with pytest.raises(EphemerisSourceError) as error:
        event(2420)
    assert error.value.reason == "solar_de440_invalid"


def test_unused_new_data_are_not_a_dependency_of_old_inputs(monkeypatch):
    original = de440._profile

    def load(profile=de440.MODEL_ID):
        if profile == NEW:
            raise EphemerisSourceError("solar_de440_invalid")
        return original(profile)

    monkeypatch.setattr(de440, "_profile", load)
    row = solar.projection_boundary(
        2320, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
    )
    assert row["record"]["ephemeris_model"] == "fatebridge_de440_solar_canping_v1"


def test_source_environment_change_is_not_misreported_as_an_input_error(monkeypatch):
    original = solar._extended_root

    def mutate(*args):
        out = original(*args)
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "invalid-after-root")
        return out

    monkeypatch.setattr(solar, "_extended_root", mutate)
    with pytest.raises(EphemerisSourceError) as error:
        event(2420)
    assert error.value.reason == "solar_configuration_changed"
