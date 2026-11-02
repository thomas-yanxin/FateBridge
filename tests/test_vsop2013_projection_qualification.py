"""Nonempty source-profile changes must be rejected before native execution."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge import fetch_vsop2013 as builder
from fatebridge.core import vsop2013_solar as solar
from fatebridge.utils.errors import EphemerisSourceError

F = Path(__file__).parent / "fixtures/vsop2013_projection_v1"
BASE = json.loads((F / "proposed-profile.json").read_bytes())


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


def test_profile_extension_preserves_every_other_source_or_input_scope():
    import hashlib

    old = json.loads((F / "before-profile.json").read_bytes())
    new, _ = builder.source_profile()
    changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
    assert changed == {
        "version",
        "working_jd_tt",
        "derived_lichun_scope",
        "qualification_reference",
        "calculation_files_sha256",
        "calculation_source_sha256",
    }
    assert new == BASE and new["version"] == "1.1.0"
    assert new["software_input_years"] == old["software_input_years"] == [1700, 2300]
    assert (
        new["qualified_solar_term_years"]
        == old["qualified_solar_term_years"]
        == [1684, 2304]
    )
    assert (
        new["sources"] == old["sources"]
        and new["embedded_series_sha256"] == old["embedded_series_sha256"]
    )
    assert [
        k
        for k in old["calculation_files_sha256"]
        if old["calculation_files_sha256"][k] != new["calculation_files_sha256"][k]
    ] == ["native_api.c"]
    old_api = (F / "native-api-before.c").read_text()
    template = Path(builder.__file__).parent / "data/astronomy/vsop2013/native_api.c.in"
    new_api = template.read_text()
    for key, value in zip(("@WORKING_LOW@", "@WORKING_HIGH@"), new["working_jd_tt"]):
        new_api = new_api.replace(key, repr(float(value)))
    assert (
        old_api.replace(
            repr(float(old["working_jd_tt"][1])), repr(float(new["working_jd_tt"][1]))
        )
        == new_api
    )
    assert (
        hashlib.sha256(new_api.encode()).hexdigest()
        == new["calculation_files_sha256"]["native_api.c"]
    )


def test_old_build_manifest_is_rejected_before_an_old_image_can_load(
    monkeypatch, tmp_path
):
    p = tmp_path / "manifest.json"
    p.write_bytes((F / "old-build-manifest.json").read_bytes())
    monkeypatch.setattr(
        solar.ctypes, "CDLL", lambda *_: pytest.fail("old model reached loader")
    )
    with pytest.raises(EphemerisSourceError) as caught:
        solar._Source(p, solar._signature(p))
    assert caught.value.reason == "solar_vsop2013_invalid"
