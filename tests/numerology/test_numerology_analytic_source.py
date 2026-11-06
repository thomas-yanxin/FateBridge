"""A named ERFA source cannot silently acquire different calendar mathematics."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import almanac, analytic_solar, de440_solar
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import SPECS
from tests.support.transports import rest as shared_rest
from tests.support.transports import run_three

rest = shared_rest
F = Path(__file__).parents[1] / "fixtures/numerology_analytic_source_v1"
RESOURCE = "data/astronomy/analytic-solar-v1.json"
REVIEWED = "138972a929da1ef7ac41921ec80f69149b36cda6fae364e90d3bd21b44625873"
FAULTS = [
    "orientation",
    "earth_amplitude",
    "nutation",
    "source_commit",
    "author_scope",
    "license",
    "missing_key",
    "extra_key",
    "model_id",
    "nonfinite",
    "duplicate_key",
    "nonobject",
    "malformed",
    "missing",
]


@pytest.fixture(autouse=True)
def isolated_source(monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    analytic_solar.profile.cache_clear()
    almanac.get_solar_terms_for_year.cache_clear()
    yield
    analytic_solar.profile.cache_clear()
    almanac.get_solar_terms_for_year.cache_clear()


def fault_resource(monkeypatch, tmp_path, fault):
    raw = analytic_solar.files("fatebridge").joinpath(RESOURCE).read_bytes()
    data = json.loads(raw)
    if fault == "orientation":
        data["orientation"]["am12"] += 0.01
    elif fault == "earth_amplitude":
        data["epv00"]["e0x"][0][0] += 0.001
    elif fault == "nutation":
        data["nut00b"][0][5] += 1e7
    elif fault == "source_commit":
        data["source"]["commit"] = "0" * 40
    elif fault == "author_scope":
        data["author_validated_years"] = [1, 9999]
    elif fault == "license":
        data["license"] = "unreviewed"
    elif fault == "missing_key":
        del data["epv00"]["e0x"]
    elif fault == "extra_key":
        data["calibration"] = "unreviewed"
    elif fault == "model_id":
        data["model_id"] = "another_model"
    elif fault == "nonfinite":
        data["orientation"]["am12"] = float("nan")
    content = json.dumps(data).encode()
    if fault == "duplicate_key":
        content = b'{"model_id":"fatebridge_analytic_solar_v1",' + raw[1:]
    elif fault == "nonobject":
        content = b"[]"
    elif fault == "malformed":
        content = b"["
    package = tmp_path / "selected-source"
    target = package / RESOURCE
    target.parent.mkdir(parents=True)
    if fault != "missing":
        target.write_bytes(content)
    monkeypatch.setattr(analytic_solar, "files", lambda _: package)
    analytic_solar.profile.cache_clear()


def test_reviewed_identity_is_bound_to_independently_read_primary_tables():
    reference = json.loads((F / "primary-reference.json").read_bytes())
    assert reference["reviewed_profile_canonical_sha256"] == REVIEWED
    assert reference["harmonic_rows"] == 1951
    assert reference["nutation_rows"] == 77
    assert reference["orientation_constants"] == 7
    assert reference["independent_physical_observations"] == 0
    data = analytic_solar.profile()
    del data["loaded_sha256"]
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == REVIEWED
    before = json.loads((F / "scalar-before.json").read_bytes())
    assert any(
        row["before_longitudes"] != row["after_longitudes"]
        and row["same_loaded_sha256"]
        for row in before
    )


@pytest.mark.parametrize("fault", FAULTS)
@pytest.mark.parametrize("consumer", ["profile", "analytic", "de440_frame"])
def test_actual_selected_resource_fault_is_a_source_failure(
    fault, consumer, monkeypatch, tmp_path
):
    fault_resource(monkeypatch, tmp_path, fault)
    with pytest.raises(EphemerisSourceError) as caught:
        if consumer == "profile":
            analytic_solar.profile()
        elif consumer == "analytic":
            analytic_solar.solar_longitude(2461075.0)
        else:
            de440_solar.solar_longitude(2461075.0)
    assert caught.value.reason == "solar_analytic_invalid"
    assert caught.value.__cause__ is not None
    result = caught.value.as_result()
    assert result["status_code"] == 503 and result["retryable"] is False
    assert str(tmp_path) not in json.dumps(result)


@pytest.mark.parametrize(
    "fault",
    ["orientation", "earth_amplitude", "nutation", "source_commit", "loaded_sha256"],
)
def test_public_return_cannot_poison_loaded_math_or_source_receipts(fault):
    public = analytic_solar.profile()
    healthy = copy.deepcopy(public)
    epochs = [2433282.5, 2451545.0, 2461075.0]
    before = [
        (analytic_solar.solar_longitude(t), de440_solar.solar_longitude(t))
        for t in epochs
    ]
    receipt = de440_solar.source_receipt()
    key = de440_solar.cache_key()
    if fault == "orientation":
        public["orientation"]["am12"] += 0.01
    elif fault == "earth_amplitude":
        public["epv00"]["e0x"][0][0] += 0.001
    elif fault == "nutation":
        public["nut00b"][0][5] += 1e7
    elif fault == "source_commit":
        public["source"]["commit"] = "0" * 40
    else:
        public["loaded_sha256"] = "0" * 64
    after = [
        (analytic_solar.solar_longitude(t), de440_solar.solar_longitude(t))
        for t in epochs
    ]
    assert before == after
    assert analytic_solar.profile() == healthy
    assert analytic_solar.profile() is not public
    assert de440_solar.source_receipt() == receipt
    assert de440_solar.cache_key() == key
    assert analytic_solar.profile.cache_info().misses == 1


def test_reviewed_reformatting_keeps_math_and_reports_actual_loaded_bytes(
    monkeypatch, tmp_path
):
    healthy = analytic_solar.profile()
    expected = analytic_solar.solar_longitude(2461075.0)
    del healthy["loaded_sha256"]
    raw = json.dumps(healthy, sort_keys=True, separators=(",", ":")).encode()
    package = tmp_path / "reformatted"
    target = package / RESOURCE
    target.parent.mkdir(parents=True)
    target.write_bytes(raw)
    monkeypatch.setattr(analytic_solar, "files", lambda _: package)
    analytic_solar.profile.cache_clear()
    assert analytic_solar.solar_longitude(2461075.0) == expected
    assert analytic_solar.profile()["loaded_sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("tool", ["heluo", "canping"])
@pytest.mark.parametrize("mode", ["analytic", "de440"])
@pytest.mark.parametrize("fault", ["nutation", "missing", "malformed"])
def test_real_source_failure_is_consistent_across_three_adapters(
    tool, mode, fault, monkeypatch, tmp_path, rest, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    fault_resource(monkeypatch, tmp_path, fault)
    payload = dict(
        date="2000-05-15",
        time="09:00",
        zone="UTC",
        gender="男",
        use_true_solar_time=False,
    )
    response, code, cli, mcp = run_three(
        SPECS[tool], payload, ["analysis_type"], rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code != 0 and mcp.is_error
    results = [response.json(), cli, mcp.structured_content]
    common = {
        key: results[0][key] for key in ["error", "error_code", "retryable", "issues"]
    }
    # REST carries the status on HTTP; CLI and MCP retain status_code, and
    # MCP also names its operation. Compare each established wire envelope.
    assert results[0] == common
    assert results[1] == {**common, "status_code": 503}
    assert results[2] == {
        **common,
        "status_code": 503,
        "operation": SPECS[tool].operation_label_zh,
    }
    assert results[0]["error_code"] == "ephemeris_source_inconsistent"
    assert results[0]["retryable"] is False
    assert results[0]["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "solar_analytic_invalid"}
    ]
