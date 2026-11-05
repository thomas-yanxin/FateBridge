"""Refuse missing populations, narrowed source data and promoted receipts."""

import copy
import json
from pathlib import Path

import pytest

from scripts.astrodice.verify_astrodice_lunar_split import verify

ROOT = Path(__file__).parents[2]
RUN = ROOT / "tests/data/astrodice/reference_sets/study-lunar-split"


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
