"""Nonempty source-profile changes must be rejected before native execution."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge import fetch_vsop2013 as builder
from fatebridge.core import vsop2013_solar as solar
from fatebridge.utils.errors import EphemerisSourceError

REFERENCE = Path(__file__).parent / "data/solar/vsop2013-projection"
BASE, _ = builder.source_profile()


class Asset:
    def __init__(self, raw):
        self.raw = raw

    def joinpath(self, *_):
        return self

    def read_bytes(self):
        return self.raw


@pytest.mark.parametrize("field", ["range", "series", "upstream", "graph"])
def test_changed_nonempty_profile_cannot_authorize_itself(monkeypatch, field):
    data = copy.deepcopy(BASE)
    if field == "range":
        data["working_jd_tt"][1] -= 365
    elif field == "series":
        data["embedded_series_sha256"] = "0" * 64
    elif field == "upstream":
        data["sources"]["VSOP2013p3.dat"]["sha256"] = "0" * 64
    else:
        data["calculation_source_sha256"] = "0" * 64
    monkeypatch.setattr(builder, "files", lambda *_: Asset(json.dumps(data).encode()))
    with pytest.raises(ValueError):
        builder.source_profile()


def test_duplicate_source_key_cannot_be_silently_reinterpreted(monkeypatch):
    raw = json.dumps(BASE).replace("{", '{"abi_version":1,', 1).encode()
    monkeypatch.setattr(builder, "files", lambda *_: Asset(raw))
    with pytest.raises(ValueError):
        builder.source_profile()


def test_boolean_abi_is_not_a_reviewed_integer_profile(monkeypatch):
    data = copy.deepcopy(BASE)
    data["abi_version"] = True
    monkeypatch.setattr(builder, "files", lambda *_: Asset(json.dumps(data).encode()))
    with pytest.raises(ValueError):
        builder.source_profile()


@pytest.mark.parametrize(
    "error",
    [ValueError("/private/unreviewed-profile"), OSError("/private/missing-profile")],
    ids=["malformed", "missing"],
)
def test_runtime_profile_failure_is_nonretryable_source_fault(
    monkeypatch, tmp_path, error
):
    def fail():
        raise error

    monkeypatch.setattr(solar, "source_profile", fail)
    monkeypatch.setattr(
        solar.ctypes,
        "CDLL",
        lambda *_: pytest.fail("bad profile reached native loader"),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        solar._Source(tmp_path / "manifest.json", (0,))
    result = caught.value.as_result()
    assert caught.value.reason == "solar_vsop2013_invalid"
    assert result["status_code"] == 503 and result["retryable"] is False
    assert "/private/" not in json.dumps(result)


def test_approved_profile_is_a_positive_precondition_for_mutations(monkeypatch):
    monkeypatch.setattr(builder, "files", lambda *_: Asset(json.dumps(BASE).encode()))
    actual, _ = builder.source_profile()
    assert actual == BASE


def test_current_profile_scope_keeps_all_independent_tt_inputs_and_fixed_gates():
    import gzip
    import hashlib

    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    assert (
        BASE["software_input_years"] == manifest["original_input_years"] == [1700, 2300]
    )
    assert (
        BASE["qualified_solar_term_years"]
        == manifest["original_full_term_years"]
        == [1684, 2304]
    )
    assert (
        BASE["derived_lichun_scope"]["years"]
        == manifest["derived_lichun_years"]
        == [2305, 2420]
    )
    assert manifest["gate_seconds_tt"] == 1.0
    assert manifest["maximum_numerical_bracket_seconds"] == 0.0002
    counts = []
    for record in manifest["references"]:
        path = REFERENCE / record["file"]
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["sha256"]
        data = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
        assert data["production_imported"] is False
        rows = data["rows"]
        assert len(rows) == record["rows"]
        keys = {(row["year"], row["index"]) for row in rows}
        assert len(keys) == len(rows)
        if len(rows) == 14904:
            assert keys == {
                (year, index) for year in range(1684, 2305) for index in range(24)
            }
        else:
            assert keys == {(year, 2) for year in range(2305, 2421)}
            assert all(row["longitude"] == 315 for row in rows)
            assert data["kernel_sha256"] == manifest["source_kernel_sha256"]
        assert all(
            0 < row["bracket_seconds"] <= manifest["maximum_numerical_bracket_seconds"]
            for row in rows
        )
        counts.append(len(rows))
    assert counts == [14904, 116]
    assert manifest["new_independent_physical_observations"] == 0
