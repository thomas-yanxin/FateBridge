"""Frozen outputs from an independently installed PyJHora implementation."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, vimshottari

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/jyotish-reference.json").read_text()
)


@pytest.mark.parametrize("case", REFERENCE["examples"])
def test_d1_d9_d10_and_all_81_antardasha_starts_against_pyjhora(
    case, monkeypatch, tmp_path
):
    # The frozen oracle used Moshier; an operator's nonempty path must not win.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    year, month, day = case["date"]
    hour, minute, _ = case["time"]
    birth = build_astro_birth_info(
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=hour,
        birth_minute=minute,
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        birth_timezone=str(case["timezone_offset"]),
        name="Explicitly fictional reference case",
    )
    india = build_india(birth, node_mode=case["node_mode"])
    assert india["profile"]["ephemeris_models"] == ["moshier"]
    for name, varga in india["charts"].items():
        for planet in [varga["ascendant"], *varga["planets"]]:
            sign, degree = case["vargas"][name][planet["id"]]
            # Oracle subtracts the zone offset from local double JD; our UTC
            # conversion precedes JD construction. One JD ULP (~40us) affects
            # the ascendant, and a varga amplifies its degree difference.
            tolerance = 2e-7
            if case["node_mode"] == "true" and planet["id"] in {"Rahu", "Ketu"}:
                # Identical TT JD/flags on macOS arm64 vs Linux x86_64 differ
                # by up to 6.72e-7 degrees in Swiss's true-node calculation.
                # One adjacent double JD also produces a similar difference.
                # Bound this separately (0.0036 arcsec in D1); do not loosen
                # physical-planet or dasha tolerances to hide node noise.
                tolerance = 1e-6
            assert planet["longitude"] == pytest.approx(
                sign * 30 + degree, abs=tolerance * varga["division"], rel=0
            )
    moon = next(p for p in india["charts"]["D1"]["planets"] if p["id"] == "Moon")
    output = vimshottari(
        birth.utc_datetime,
        moon["longitude"],
        datetime(2026, 10, 22, tzinfo=timezone.utc),
        year_basis=case["year_basis"],
    )

    def elapsed_days(text):
        return (
            datetime.fromisoformat(text) - birth.utc_datetime
        ).total_seconds() / 86400

    assert [p["lord"] for p in output["timeline"]] == list(
        case["major_starts_local_jd"]
    )
    for major in output["timeline"]:
        expected = (
            case["major_starts_local_jd"][major["lord"]] - case["oracle_input_local_jd"]
        )
        # A ~40us JD offset perturbs Moon longitude; multiplying its mansion
        # fraction by a whole multi-year dasha amplifies that to <1 second.
        assert elapsed_days(major["start"]) == pytest.approx(
            expected, abs=1 / 86400, rel=0
        )
        for sub in major["antardashas"]:
            expected_sub = (
                case["sub_starts_local_jd"][major["lord"]][sub["lord"]]
                - case["oracle_input_local_jd"]
            )
            assert elapsed_days(sub["start"]) == pytest.approx(
                expected_sub, abs=1 / 86400, rel=0
            )
