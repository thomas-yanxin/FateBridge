"""Complete schedule, actual selected source and no silent source substitution."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import almanac, de440_solar
from fatebridge.core.canping_solar import projection_boundary
from fatebridge.core.canping_timing import APPENDIX, CONTINUOUS
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.output_chinese import CanpingSeries, CanpingTiming
from fatebridge.utils.errors import EphemerisSourceError

INPUT = dict(
    date="2200-05-15", time="09:00", zone="UTC", gender="男", use_true_solar_time=False
)
FOLDER = Path(__file__).parent / "fixtures/canping_projection_v1"


@pytest.mark.parametrize("mode", ["de440", "analytic"])
@pytest.mark.parametrize("year", [1799, 2320])
def test_derived_clock_flags_and_frozen_endpoint_roots(monkeypatch, mode, year):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    if year == 1799:
        reference = json.loads(
            (FOLDER.parent / "ren_calendar_guard_v1/reference.json").read_bytes()
        )
        expected = next(
            r for r in reference["rows"] if r["year"] == year and r["index"] == 2
        )
        civil, pillar = 1800, 1799
    else:
        reference = json.loads((FOLDER / "reference.json").read_bytes())
        expected = next(r for r in reference["rows"] if r["year"] == year)
        civil = pillar = 2200
    row = projection_boundary(
        year, "UTC", origin_civil_year=civil, origin_bazi_year=pillar, horizon=120
    )
    details = row["record"]["solar_model_details"]
    assert details["historical_ut1_convention"] is (year == 1799)
    assert details["future_leap_seconds_assumed_unchanged"] is (year == 2320)
    assert (details["civil_time_method"] == "pre_1972_swiss_UT1_delta_t") is (
        year == 1799
    )
    assert abs(details["selected_crossing_jd_tt"] - expected["jd_tt"]) * 86400 <= 1.0


@pytest.mark.parametrize("mode", ["de440", "analytic", "auto"])
@pytest.mark.parametrize("method", [APPENDIX, CONTINUOUS])
def test_complete_120_years_and_query_use_same_selected_model(
    monkeypatch, mode, method
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    result = build_canping_result(
        **INPUT, dayun_method=method, analysis_datetime="2319-06-01T12:00:00Z"
    )
    series, timing = result["liunian_series"], result["canping_timing"]
    rows, boundaries, context = (
        series["rows"],
        series["year_boundaries"],
        series["solar_context"],
    )
    assert len(rows) == 120 and len(boundaries) == 121
    assert [r["year"] for r in rows] == list(range(2200, 2320))
    assert [b["year"] for b in boundaries] == list(range(2200, 2321))
    assert context["derived_event_years"] == list(range(2201, 2321))
    assert context == timing["solar_year_context"]
    assert context["public_model_years_extended"] is False
    encoded = json.dumps(
        boundaries,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert hashlib.sha256(encoded).hexdigest() == context["boundary_receipts_sha256"]
    expected = (
        "fatebridge_analytic_solar_v1"
        if mode == "analytic"
        else de440_solar.CANPING_MODEL_ID
    )
    assert {b["record"]["ephemeris_model"] for b in boundaries[1:]} == {expected}
    for i, row in enumerate(rows):
        assert row["segments"][0]["start_at"] == row["start_at"]
        assert row["segments"][-1]["end_at"] == row["end_at"]
        assert row["end_at"] == boundaries[i + 1]["record"]["datetime_with_offset"]
        if i:
            assert rows[i - 1]["end_at"] == row["start_at"]
    selected = timing["selected"]
    assert selected["year"] == 2319 and selected["ganzhi"] == rows[-1]["ganzhi"]
    assert selected["year_start_boundary"] == boundaries[-2]
    assert selected["year_end_boundary"] == boundaries[-1]
    assert selected["dayun_index"] != 0
    assert "[参平年序·实际立春来源]" in result["snapshot_text"]
    assert CanpingSeries.model_validate(series).model_dump(exclude_unset=True) == series
    assert CanpingTiming.model_validate(timing).model_dump(exclude_unset=True) == timing


@pytest.mark.parametrize("mode", ["de440", "analytic"])
@pytest.mark.parametrize(
    "date,zone,origin", [("1800-01-01", "+14:00", 1799), ("2200-01-01", "-12:00", 2199)]
)
def test_january_endpoints_use_local_civil_origin_without_clipping(
    monkeypatch, mode, date, zone, origin
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    result = build_canping_result(**{**INPUT, "date": date, "zone": zone})
    series = result["liunian_series"]
    assert series["birth_pillar_year"] == origin
    assert len(series["rows"]) == 120 and len(series["year_boundaries"]) == 121
    assert series["year_boundaries"][0]["year"] == origin
    assert series["rows"][0]["start_at"].startswith(date)


def test_future_lichun_is_inclusive_and_outside_horizon_is_rejected(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    first = build_canping_result(**INPUT)["liunian_series"]
    at = datetime.fromisoformat(first["year_boundaries"][-2]["instant_utc"])
    before = build_canping_result(
        **INPUT, analysis_datetime=(at - timedelta(microseconds=1)).isoformat()
    )["canping_timing"]["selected"]
    after = build_canping_result(**INPUT, analysis_datetime=at.isoformat())[
        "canping_timing"
    ]["selected"]
    assert (before["year"], after["year"]) == (2318, 2319)
    with pytest.raises(ValueError, match="超出本次年序"):
        build_canping_result(
            **INPUT, analysis_datetime=first["year_boundaries"][-1]["instant_utc"]
        )
    with pytest.raises(ValueError, match="早于出生"):
        build_canping_result(**INPUT, analysis_datetime="2200-01-01T00:00:00Z")


@pytest.mark.parametrize("year,horizon", [(2321, 120), (2320, 119), (2201, True)])
def test_derived_event_permission_remains_bounded(year, horizon):
    with pytest.raises(ValueError):
        projection_boundary(
            year, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=horizon
        )


@pytest.mark.parametrize("mode", ["de440", "analytic"])
def test_public_year_grid_is_not_extended(monkeypatch, mode):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    projection_boundary(
        2320, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
    )
    # The original2320 rejection is retained. Only the explicit DE440
    # contract's reported range changed; R68's old regex failure is archived.
    message = "1700..2300" if mode == "de440" else "1800..2200"
    with pytest.raises(ValueError, match=message):
        almanac.get_solar_terms_for_year(2320, "UTC")


def test_missing_derived_profile_fails_without_switching_model(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.setitem(
        de440_solar._PROFILE_FILES,
        de440_solar.CANPING_MODEL_ID,
        "missing-canping-source",
    )
    de440_solar._profile.cache_clear()
    try:
        with pytest.raises(EphemerisSourceError):
            projection_boundary(
                2201, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
            )
    finally:
        de440_solar._profile.cache_clear()


def test_explicit_analytic_never_loads_de440_projection_profile(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.setitem(
        de440_solar._PROFILE_FILES,
        de440_solar.CANPING_MODEL_ID,
        "missing-canping-source",
    )
    row = projection_boundary(
        2320, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
    )
    assert row["record"]["ephemeris_model"] == "fatebridge_analytic_solar_v1"


def test_unused_projection_profile_is_not_a_birth_year_dependency(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.setitem(
        de440_solar._PROFILE_FILES,
        de440_solar.CANPING_MODEL_ID,
        "missing-canping-source",
    )
    row = projection_boundary(
        2001, "UTC", origin_civil_year=2000, origin_bazi_year=2000, horizon=120
    )
    assert row["selection"] == "ordinary_public_year_grid"
    assert row["record"]["ephemeris_model"] == de440_solar.MODEL_ID


def test_source_configuration_change_is_rejected_and_cached_receipts_are_copied(
    monkeypatch,
):
    from fatebridge.core import canping_solar

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    args = dict(origin_civil_year=2200, origin_bazi_year=2200, horizon=120)
    first = projection_boundary(2201, "UTC", **args)
    first["record"]["solar_model_details"]["model_id"] = "forged"
    second = projection_boundary(2201, "UTC", **args)
    assert (
        second["record"]["solar_model_details"]["model_id"]
        == de440_solar.CANPING_MODEL_ID
    )
    original = canping_solar._root

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        return result

    monkeypatch.setattr(canping_solar, "_root", changed)
    with pytest.raises(EphemerisSourceError, match="configuration changed"):
        projection_boundary(2201, "UTC", **args)


def test_loaded_projection_manifest_identity_rejects_relabelled_scope(monkeypatch):
    original = de440_solar.files

    class Entry:
        def __init__(self, entry):
            self.entry = entry

        def joinpath(self, name):
            return Entry(self.entry.joinpath(name))

        def read_bytes(self):
            raw = self.entry.read_bytes()
            if self.entry.name == "de440-solar-canping-v1.json":
                value = json.loads(raw)
                value["software_event_years"] = [2201, 2400]
                return json.dumps(value).encode()
            return raw

    monkeypatch.setattr(de440_solar, "files", lambda package: Entry(original(package)))
    de440_solar._profile.cache_clear()
    try:
        with pytest.raises(EphemerisSourceError):
            de440_solar.source_receipt(de440_solar.CANPING_MODEL_ID)
    finally:
        de440_solar._profile.cache_clear()


def test_receipt_contract_rejects_changed_instant_and_clipped_count():
    with pytest.raises(ValidationError):
        CanpingSeries.model_validate(
            {"solar_context": {"horizon_years": 120, "boundary_count": 120}}
        )
    with pytest.raises(ValidationError):
        CanpingTiming.model_validate(
            {
                "selected": {
                    "year_start_boundary": {
                        "instant_utc": "2300-02-04T00:00:00Z",
                        "record": {"datetime_with_offset": "2300-02-05T00:00:00Z"},
                    }
                }
            }
        )


def test_frozen_projection_inputs_and_previous_profiles_remain_unchanged():
    freeze = json.loads((FOLDER / "freeze.json").read_bytes())
    protocol = json.loads((FOLDER / "protocol.json").read_bytes())
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest
    for name, digest in protocol["preserve_existing_profiles"].items():
        path = Path(__file__).parents[1] / "src/fatebridge/data/astronomy" / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert freeze["goal_complete"] is False
