"""Refuse missing populations, narrowed source data and promoted receipts."""

import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.astrodice_lunar_split import load_plan
from scripts.verify_astrodice_lunar_split import verify

ROOT = Path(__file__).parents[1]
RUN = ROOT / "docs/validation/astrodice-lunar-split-run-2026-10-28"


@pytest.fixture(scope="module")
def development():
    return json.loads((RUN / "development-first.json").read_text())


@pytest.mark.parametrize(
    "kind", ["row", "profile", "epoch", "direction", "time", "grade", "credit", "gate"]
)
def test_independent_reader_rejects_changed_evidence_before_blessing_it(
    kind, development, tmp_path
):
    data = copy.deepcopy(development)
    if kind == "row":
        data["rows"].pop()
    elif kind == "profile":
        data["rows"][0]["profiles"].pop("rounded_emitter_only")
    elif kind == "epoch":
        data["rows"][0]["epoch_source_jd"] = "2451545"
    elif kind == "direction":
        first = next(iter(data["points"]))
        data["points"][first]["direction"] = [["0", "0"]] * 3
    elif kind == "time":
        data["physical_TT_TDB_model_certified"] = True
    elif kind == "grade":
        data["original_failure_records_regraded"] = True
    elif kind == "credit":
        data["new_external_observations"] = 20
    else:
        data["old_gate_codes"] = [0, 0]
    path = tmp_path / "mutant.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(RUN, path)


@pytest.mark.parametrize(
    "name",
    [
        "header.bin",
        "record-responses/case-00.bin",
        "before-change/tests/fixtures/astrodice-lunar-endpoint-v2-protocol.json",
    ],
)
def test_raw_source_and_original_protocol_changes_are_refused(name, tmp_path):
    shutil.copyfile(
        RUN / "plan-before-analysis.json", tmp_path / "plan-before-analysis.json"
    )
    shutil.copyfile(
        RUN / "source-inputs-before-evaluation.json",
        tmp_path / "source-inputs-before-evaluation.json",
    )
    for p in json.loads((RUN / "source-inputs-before-evaluation.json").read_text()):
        target = tmp_path / p
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RUN / p, target)
    p = tmp_path / name
    p.write_bytes(p.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="raw source input changed"):
        verify(tmp_path, RUN / "development-first.json")


def test_original_early_failure_templates_and_error_lines_remain_bound():
    plan = json.loads((RUN / "plan-before-analysis.json").read_text())
    assert plan["fixed_position_arcsec"] == "0.02"
    assert plan["fixed_rate_arcsec_per_day"] == "0.002"
    for p in [
        "tests/fixtures/astrodice-lunar-endpoint-reference.json",
        "tests/fixtures/astrodice-lunar-endpoint-v2-reference.json",
    ]:
        h = hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
        assert h == plan["source_files_before"][p]
        assert hashlib.sha256((RUN / "before-change" / p).read_bytes()).hexdigest() == h


def test_coordinated_source_and_manifest_replacement_is_refused(tmp_path):
    shutil.copyfile(
        RUN / "plan-before-analysis.json", tmp_path / "plan-before-analysis.json"
    )
    manifest = json.loads((RUN / "source-inputs-before-evaluation.json").read_text())
    manifest["header.bin"] = hashlib.sha256(b"replacement").hexdigest()
    (tmp_path / "header.bin").write_bytes(b"replacement")
    (tmp_path / "source-inputs-before-evaluation.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest changed"):
        verify(tmp_path, RUN / "development-first.json")
    with pytest.raises(ValueError, match="manifest changed"):
        load_plan(tmp_path)
