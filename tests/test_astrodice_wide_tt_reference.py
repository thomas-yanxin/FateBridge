"""Raw BC/JD witnesses, independent stencil proof and anti-tampering guards."""

import csv
import hashlib
import io
import json
import math
import shutil
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.audit_astrodice_horizons_wide_reference import (
    input_tick,
    interpolation_weights,
    validate,
)
from scripts.audit_astrodice_v6_wide import frame_rotation, rotate
from scripts.gen_astrodice_horizons_wide import calendar_label, julian_day

FIXTURE = Path(__file__).parent / "fixtures/astrodice-v6-wide-tt-v1"


def test_frozen_reference_preserves_both_unresolved_cases_without_platform_trig(
    monkeypatch,
):
    def forbidden(*args):
        raise AssertionError(
            "Independent mathematical replay must not use libm sin/cos"
        )

    monkeypatch.setattr(math, "sin", forbidden)
    monkeypatch.setattr(math, "cos", forbidden)
    assert (
        hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest()
        == "2e4f020ed36a40db2303b9e6525a9c4d8348d1412b28211b2304c1bdb8e2c350"
    )
    result = validate(
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "raw",
        FIXTURE / "reference-seal.json",
    )
    assert result["exit_code"] == 2
    assert result["cases"] == 166 and result["complete_cases"] == 165
    assert result["BC_position_probes"] == 64
    assert {row["id"] for row in result["failures"]} == {
        "fresh-3000-1-Mercury",
        "old-upper-Moon",
    }


def test_actual_horizons_bc_calendar_column_requires_the_jd_identity():
    response = json.loads((FIXTURE / "bc-calendar-witness.json").read_text())
    table = list(
        csv.reader(
            io.StringIO(response["result"].split("$$SOE", 1)[1].split("$$EOE", 1)[0])
        )
    )
    table = [row for row in table if row]
    # Actual CSV material prints0001 without a BC marker. Treating this row
    # as AD1 changes the epoch by365days; its explicit returned JD resolves it.
    assert table[0][0].strip().startswith("0001-Dec-31")
    assert Fraction(table[0][1]) == Fraction("1721425.25")
    bc = input_tick("1bc-Dec-31 18:00:00.000000")
    ad = input_tick("1ad-Dec-31 18:00:00.000000")
    assert julian_day(bc) == Fraction(table[0][1])
    assert julian_day(ad) - julian_day(bc) == 365


@pytest.mark.parametrize(
    "label",
    [
        "1bc-Dec-29 00:00:00.000000",
        "1bc-Feb-29 23:59:59.999999",
        "1ad-Jan-01 00:00:00.000000",
        "10000ad-Jan-01 00:00:00.000000",
    ],
)
def test_extended_reference_clock_round_trips_without_python_utc_limits(label):
    assert calendar_label(input_tick(label)) == label


@pytest.mark.parametrize(
    "label",
    [
        "0bc-Jan-01 00:00:00.000000",
        "0ad-Jan-01 00:00:00.000000",
        "1-Jan-01 00:00:00.000000",
        "1ad-Feb-29 00:00:00.000000",
    ],
)
def test_invalid_or_era_ambiguous_reference_clocks_are_rejected(label):
    with pytest.raises(ValueError):
        input_tick(label)


def test_independent_rational_weights_differentiate_a_degree_twelve_polynomial():
    weights = interpolation_weights()
    polynomial = lambda x: 5 - 7 * x + 11 * x**4 - 3 * x**7 + 13 * x**12
    assert sum(w * polynomial(x) for x, w in weights.items()) == -7
    assert all(weights[-x] == -weights[x] for x in range(1, 7))


@pytest.mark.parametrize(
    "kind", ["direction", "drop_point", "JD", "case", "nan", "dimension"]
)
def test_structural_raw_replay_rejects_tampering_even_with_a_resealed_json(
    tmp_path, kind
):
    reference = json.loads((FIXTURE / "reference.json").read_text())
    row = reference["rows"][0]
    if kind == "direction":
        row["samples"]["0"]["unit_direction"][0] += 1e-9
    elif kind == "drop_point":
        row["samples"]["0"] = None
        row["missing_offsets_seconds"] = ["0"]
    elif kind == "JD":
        row["samples"]["0"]["returned_jd_tt_string"] = "2451545.000000000"
    elif kind == "nan":
        row["samples"]["0"]["unit_direction"][0] = math.nan
    elif kind == "dimension":
        row["samples"]["0"]["unit_direction"].append(0.0)
    else:
        row["body"] = "Pluto"
    changed = tmp_path / "reference.json"
    changed.write_text(json.dumps(reference))
    seal = json.loads((FIXTURE / "reference-seal.json").read_text())
    seal["reference_sha256"] = hashlib.sha256(changed.read_bytes()).hexdigest()
    seal_path = tmp_path / "seal.json"
    seal_path.write_text(json.dumps(seal))
    with pytest.raises(ValueError):
        validate(FIXTURE / "protocol.json", changed, FIXTURE / "raw", seal_path)


def mock_frame_native(monkeypatch, bad_flags=False):
    from fatebridge.core.astro import runtime

    swe = runtime.swe
    vectors = {
        swe.EARTH: [1.0, 0.0, 0.0],
        swe.MERCURY: [0.0, 1.0, 0.0],
        swe.MARS: [0.3, 0.4, 0.5],
    }

    def call(operation, epoch, body, flags):
        if operation == "set_sid_mode":
            return None
        value = vectors[body]
        if not flags & swe.FLG_J2000:
            value = [-value[1], value[0], value[2]]
        returned = flags | swe.FLG_NOABERR | swe.FLG_NOGDEFL
        if flags & (swe.FLG_J2000 | swe.FLG_SIDEREAL):
            returned |= swe.FLG_NONUT
        if bad_flags:
            returned ^= swe.FLG_XYZ
        return (*value, 0.0, 0.0, 0.0), returned

    monkeypatch.setattr(runtime, "ephemeris_call", call)
    return SimpleNamespace(observe=lambda *args, **kwargs: None)


def test_frame_reduction_uses_geometry_and_replays_an_independent_third_vector(
    monkeypatch,
):
    trace = mock_frame_native(monkeypatch)
    matrix, receipt = frame_rotation(2451545.0, False, "swieph", trace)
    assert rotate(matrix, [0.2, 0.3, 0.4]) == pytest.approx([-0.3, 0.2, 0.4], abs=1e-15)
    assert receipt["geometric_witness_replay_maximum"] < 1e-15


def test_frame_reduction_cannot_accept_a_wrong_coordinate_flag(monkeypatch):
    trace = mock_frame_native(monkeypatch, bad_flags=True)
    with pytest.raises(ValueError, match="coordinate contract changed"):
        frame_rotation(2451545.0, False, "swieph", trace)


def test_raw_provenance_cannot_be_forged_by_rehashing_only_the_request_journal(
    tmp_path,
):
    raw = tmp_path / "raw"
    shutil.copytree(FIXTURE / "raw", raw)
    journal = [
        json.loads(line) for line in (raw / "requests.jsonl").read_text().splitlines()
    ]
    entry = next(row for row in journal if row.get("http_status") == 200)
    file = raw / entry["raw_file"]
    response = json.loads(file.read_text())
    response["signature"]["source"] = "fabricated provenance"
    file.write_text(json.dumps(response))
    entry["raw_sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
    (raw / "requests.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in journal)
    )
    with pytest.raises(ValueError, match="immutable reference batch"):
        validate(
            FIXTURE / "protocol.json",
            FIXTURE / "reference.json",
            raw,
            FIXTURE / "reference-seal.json",
        )
