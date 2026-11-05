"""Point-intent repair must retain old gates and refuse impossible UTC labels."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import almanac, analytic_solar, spk_solar

ROOT = Path(__file__).resolve().parents[1]


def sealed(path):
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    raw = (
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )
    return json.loads(raw)


@pytest.mark.parametrize("spk", [False, True])
def test_entire_known_oracle_through_each_scalar_model_caller(spk, monkeypatch):
    oracle = sealed(ROOT / "tests/data/bazi_tt_utc_exact_v1/oracle.json.gz")
    provider = spk_solar if spk else analytic_solar
    seen = 0
    for row in oracle["rows"]:
        if row["status"] == "pre_atomic_policy_unadjudicated":
            continue
        jd = row["jd_tt"]

        def solver(*args, **kwargs):
            return {
                "jd_tt": jd,
                "bracket_tt": [jd, jd],
                "bracket_seconds": 0,
                "model": {"model_id": "synthetic_point_control"},
            }

        monkeypatch.setattr(provider, "longitude_crossing_tt", solver)
        if row["status"] == "normal":
            civil, receipt = almanac._solar_term_utc_via_analytic(2000, 0, {}, spk=spk)
            assert civil.isoformat() == row["expected_datetime_utc"], row["id"]
            details = receipt["solar_model_details"]
            assert details["selected_crossing_jd_tt"] == jd
            assert (
                details["numerical_epoch_representation"]
                == "explicit_ieee_float_tt_point"
            )
        else:
            with pytest.raises(ValueError, match="UTC leap second not representable"):
                almanac._solar_term_utc_via_analytic(2000, 0, {}, spk=spk)
        seen += 1
    assert seen == 4173


def test_explicit_root_conversion_error_cannot_publish_a_linear_year(
    monkeypatch, tmp_path
):
    oracle = sealed(ROOT / "tests/data/bazi_tt_utc_exact_v1/oracle.json.gz")
    bad = next(r for r in oracle["rows"] if r["status"] == "unrepresentable_utc_label")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))

    def native(year, target, anchor, provenance):
        provenance.update(ephemeris_model="moshier")
        return anchor

    def root(*args, **kwargs):
        return {
            "jd_tt": bad["jd_tt"],
            "bracket_tt": [bad["jd_tt"]] * 2,
            "bracket_seconds": 0,
            "model": {"model_id": "synthetic_unrepresentable"},
        }

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", native)
    monkeypatch.setattr(analytic_solar, "longitude_crossing_tt", root)
    with pytest.raises(ValueError, match="UTC leap second not representable"):
        almanac._calculate_solar_terms_for_year(2000, "UTC")
