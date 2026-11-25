"""Independent position references and the actual owned Moon source window."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.source_session import source_session
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.compressed_ephemeris import (
    audit_compressed_endpoints,
    coordinate_context_evidence,
)
from fatebridge.core.jyotish.jyotish import positions
from scripts.astrodice.diagnose_astrodice_lunar_order import angle_arcsec
from tests.unit_test.fixtures.jyotish_sources import restore_runtime  # noqa: F401

FIXTURES = Path(__file__).parents[1] / "fixtures"
PROTOCOL = FIXTURES / "jyotish-lunar-owned-window-protocol.json"
REFERENCE = FIXTURES / "jyotish-lunar-owned-window-reference.json"
Q = json.loads(PROTOCOL.read_text())
REF = json.loads(REFERENCE.read_text())


# Swiss Ephemeris 2.10.03 apparent geocentric source, then SOFA (2023-10-11)
# target equator. Remote epochs carry the Swiss variation from the modern triad.
EQUATORIAL_REFERENCE = {
    1800: (
        (350.8341147081722, -7.915338092265471),
        (350.8341150748156, -7.915337803857556),
    ),
    3000: (
        (314.7379721506916, -11.72259614078774),
        (314.73797238368064, -11.722596070863235),
    ),
    6600: (
        (239.07691510153614, -17.946140848719157),
        (239.07691534950035, -17.946140871988323),
    ),
    9600: (
        (175.60710377750323, 4.7707730078887955),
        (175.60710398458212, 4.770772890130647),
    ),
}


def require_window(receipt, epoch):
    assert receipt["physical_instant_shifted"] is False
    assert receipt["physical_jd_tt"] == epoch
    path = receipt["lunar_light_path"]
    assert path["status"] in {"already_covered", "reselected_common_window"}
    assert path["reception_jd_tt"] == epoch
    assert receipt["selected_windows"] == path["selected_windows"]
    assert all(
        w["start_jd_tt"] <= path["retarded_jd_tt"] <= epoch <= w["end_jd_tt"]
        for w in receipt["selected_windows"]
    )


def test_raw_reference_identity_and_all_frozen_epochs_remain() -> None:
    assert REF["protocol_sha256"] == hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    assert REF["candidate_imported"] is False
    assert REF["candidate_compared"] is False
    assert len(REF["rows"]) == len(Q["dates"]) == 64
    assert [r["date_tt"] for r in REF["rows"]] == [r["date_tt"] for r in Q["dates"]]
    for batch in REF["batches"]:
        assert (
            hashlib.sha256(batch["raw_response_utf8"].encode()).hexdigest()
            == batch["raw_response_sha256"]
        )


@pytest.mark.parametrize("row", REF["rows"], ids=lambda r: r["date_tt"])
def test_owned_icrf_position_meets_original_line_without_shifting_tt(row) -> None:
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    flags = (
        e.swe.FLG_SWIEPH
        | e.swe.FLG_SPEED
        | e.swe.FLG_XYZ
        | e.swe.FLG_EQUATORIAL
        | e.swe.FLG_ICRS
        | e.swe.FLG_J2000
    )
    with audit_compressed_endpoints(), source_session():
        state, returned = e.ephemeris_call("calc", row["jd_tt"], e.swe.MOON, flags)
        assert e.ephemeris_model_from_retflag(returned) == "swieph"
        require_window(coordinate_context_evidence(), row["jd_tt"])
        assert angle_arcsec(state[:3], row["icrf_unit_direction"]) <= 0.02


@pytest.mark.parametrize("year", [1800, 3000, 6600, 9600])
def test_actual_dispatcher_retains_both_chart_frame_receipts(year: int) -> None:
    row = next(
        r for r in REF["rows"] if r["date_tt"].startswith(f"{year}-01-01T00:00:00.375")
    )
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    moment = datetime_from_tt(row["jd_tt"])
    birth = AstroBirthInfo(
        "Engineering synthetic source boundary",
        "",
        "UTC",
        0,
        0,
        moment,
        moment,
        recorded_datetime=moment,
    )
    raw = positions(birth, ephemeris_policy="require_data_files")
    assert raw["julian_day_tt"] == row["jd_tt"]
    century = year // 100
    files = [f"sepl_{century - 6:02d}.se1", f"semo_{century:02d}.se1"]
    for frame in ["ecliptic", "equatorial"]:
        context = raw["native_coordinate_contexts"][f"{frame}_Moon"]
        assert context["input_julian_day"] == row["jd_tt"]
        require_window(context, row["jd_tt"])
        assert context["lunar_light_path"]["status"] == "reselected_common_window"
        assert [w["filename"] for w in context["selected_windows"]] == files
    ec = raw["native_coordinate_contexts"]["ecliptic_Moon"]
    assert raw["longitudes"]["Moon"] == ec["selected_native_state"][0]
    eq = raw["native_coordinate_contexts"]["equatorial_Moon"]
    native, target = EQUATORIAL_REFERENCE[year]
    assert eq["selected_native_state"][:2] == pytest.approx(native, abs=1e-10, rel=0)
    moon = raw["equatorial"]["Moon"]
    assert (moon["right_ascension"], moon["declination"]) == pytest.approx(
        target, abs=1e-10, rel=0
    )
