"""An HTTP 200 service error is preserved, but never reused as an ephemeris."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.astrodice.gen_astrodice_horizons_wide import (
    calendar_label,
    julian_day,
    julian_input_label,
    ticks,
    wire_epochs,
)

ROOT = Path(__file__).resolve().parents[2]


def isolated_collect(path, previous, valid, output, material):
    # The collector explicitly rejects an imported candidate. Keep that guard
    # meaningful even when the parent pytest process runs domain tests too.
    response = path.parent / "fresh-response.json"
    response.write_bytes(valid)
    receipt = path.parent / "worker-result.json"
    worker = r"""
import json,sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from scripts.astrodice import astrodice_horizons_transport as transport
from scripts.astrodice.gen_astrodice_horizons_wide import collect
protocol,previous,response,output,material,receipt=map(Path,sys.argv[1:])
calls=[]
@contextmanager
def opened(request,**kwargs):
 calls.append({k:v[0] for k,v in parse_qs(urlsplit(request.full_url).query).items()})
 class Response:
  status=200
  def read(self):return response.read_bytes()
 yield Response()
transport.open_horizons=opened
result={'calls':calls}
try:collect(protocol,output,material,reuse_material=previous)
except Exception as error:result.update(error_type=type(error).__name__,message=str(error))
receipt.write_text(json.dumps(result))
"""
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            worker,
            *map(str, [path, previous, response, output, material, receipt]),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(receipt.read_text())


def fixture(tmp_path, raw):
    center = ticks("8103-07-26T18:51:11")
    protocol = {
        "id": "reference-cache-recovery-unit-case",
        "scope": "Synthetic offline transport regression; zero astronomical samples",
        "cases": [
            {
                "id": "known-cache-case",
                "body": "Venus",
                "date_tt": "8103-07-26T18:51:11",
                "role": "synthetic_transport_test",
            }
        ],
        "targets": {"Venus": 299},
        "steps_seconds": {"Venus": []},
        "explicit_offsets_seconds": {"Venus": [0]},
        "maximum_labels_per_batch": 19,
        "maximum_url_bytes": 8000,
        "maximum_transport_attempts": 2,
        "timestamp_printing_tolerance_days": "0.000000001",
        "first_tlist_epoch_guard": {"method_id": "integer_jd_prefix_v1"},
        "retain_rejected_epoch_rows": True,
        "reference_parameters": {
            "format": "json",
            "TIME_TYPE": "'TT'",
            "TLIST_TYPE": "'JD'",
        },
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    wire, _ = wire_epochs(protocol, [center])
    parameters = {
        **protocol["reference_parameters"],
        "COMMAND": "'299'",
        "TLIST": "\n".join(f"'{julian_input_label(t)}'" for t in wire),
    }
    text = "Target body name: Venus (299) {source: DE441}\nCenter body name: Earth (399)\nDate__(TT) ICRF\n$$SOE\n"
    text += "".join(
        f"{calendar_label(t)},{float(julian_day(t)):.9f}, , ,39.363510700,15.461677183,\n"
        for t in wire
    )
    valid = json.dumps({"result": text + "$$EOE\n"}).encode()
    previous = tmp_path / "previous"
    previous.mkdir()
    (previous / "original.json").write_bytes(raw if raw is not None else valid)
    entry = {
        "batch": 1,
        "body": "Venus",
        "parameters": parameters,
        "http_status": 200,
        "raw_file": "original.json",
        "raw_sha256": hashlib.sha256(
            (previous / "original.json").read_bytes()
        ).hexdigest(),
    }
    (previous / "requests.jsonl").write_text(json.dumps(entry) + "\n")
    return path, previous, valid, parameters


@pytest.mark.parametrize(
    "raw",
    [
        b'{"error":"missing required file LTKERNL"}',
        b'{"result":"server diagnostic without ephemeris"}',
        b"<html>temporary service error</html>",
    ],
)
def test_generated_errors_are_not_reused_even_when_http_status_is_200(tmp_path, raw):
    path, previous, valid, parameters = fixture(tmp_path, raw)
    output, material = tmp_path / "new-reference.json", tmp_path / "new-raw"
    result = isolated_collect(path, previous, valid, output, material)
    assert "error_type" not in result, result
    assert result["calls"] == [parameters]
    assert (previous / "original.json").read_bytes() == raw
    assert json.loads(output.read_text())["rows"][0]["samples"]["0"] is not None
    identity = json.loads(output.read_text())["returned_epoch_identity"]
    assert identity["role"] == "returned_label_matching_only"
    assert identity["label_match_budget_days"] == "0.000000001"
    assert identity["numerical_evaluation_epoch_certified"] is False
    assert identity["observer_TT_to_source_TDB_mapping_certified"] is False
    assessment = json.loads((material / "recovery-cache-assessment.json").read_text())
    assert len(assessment) == 1
    assert assessment[0]["status"] == "preserved_unavailable_response_not_reused"
    assert not assessment[0]["source_accuracy_certified"]


def test_a_valid_success_is_reused_without_a_network_request(tmp_path):
    path, previous, valid, _ = fixture(tmp_path, None)
    output, material = tmp_path / "new-reference.json", tmp_path / "new-raw"
    result = isolated_collect(path, previous, valid, output, material)
    assert "error_type" not in result, result
    assert result["calls"] == []
    assert json.loads(output.read_text())["rows"][0]["samples"]["0"] is not None
    entry = json.loads((material / "requests.jsonl").read_text())
    assert entry["network_request_performed"] is False
    assert entry["raw_sha256"] == hashlib.sha256(valid).hexdigest()
    assert json.loads(output.read_text())["returned_epoch_identity"] == {
        "role": "returned_label_matching_only",
        "label_match_budget_days": "0.000000001",
        "numerical_evaluation_epoch_certified": False,
        "observer_TT_to_source_TDB_mapping_certified": False,
    }


def test_recovery_still_rejects_changed_original_bytes(tmp_path):
    path, previous, valid, _ = fixture(tmp_path, None)
    (previous / "original.json").write_bytes(b"changed")
    result = isolated_collect(
        path, previous, valid, tmp_path / "out.json", tmp_path / "raw"
    )
    assert result["calls"] == []
    assert result["error_type"] == "ValueError"
    assert result["message"] == "Recovery raw response identity changed"


@pytest.mark.parametrize("time_type", ["'TDB'", "'UT'", None])
def test_wrong_or_missing_observer_clock_fails_before_cache_or_network(
    tmp_path, time_type
):
    path, previous, valid, _ = fixture(tmp_path, None)
    protocol = json.loads(path.read_text())
    if time_type is None:
        protocol["reference_parameters"].pop("TIME_TYPE")
    else:
        protocol["reference_parameters"]["TIME_TYPE"] = time_type
    path.write_text(json.dumps(protocol))
    output, material = tmp_path / "output.json", tmp_path / "material"
    result = isolated_collect(path, previous, valid, output, material)
    assert result["calls"] == []
    assert result["error_type"] == "ValueError"
    assert (
        result["message"]
        == "Frozen observer collector requires explicit TIME_TYPE='TT'"
    )
    assert not output.exists() and not material.exists()
