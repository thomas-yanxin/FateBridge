"""A frozen omitted-term counterexample and complete text/number fidelity."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.local_techniques.otherbu import _motion_snapshot_line
from scripts.verify_astrodice_motion_text import verify

PATH = Path(__file__).parent / "data/astrodice/tables/motion_term_cases.json"
DATA = json.loads(PATH.read_text())


def rendered(row):
    return {
        "chart": {"chart": {"objects": row["objects"]}},
        "snapshot_text": "[天象瞬时黄经运动]\n"
        + "\n".join(_motion_snapshot_line(obj) for obj in row["objects"]),
    }


@pytest.mark.parametrize(
    "row",
    DATA["rows"],
    ids=lambda r: f"{r['inputs']['date']}:{r['inputs']['zodiacal']}:{r['backend']}",
)
def test_rendered_real_motion_has_every_stored_term_once(row):
    rows = verify(rendered(row))
    assert len(rows) == len(row["objects"])


def test_zero_analytic_term_is_still_evidence():
    motion = {
        "longitude_speed": 1.0,
        "native_longitude_speed": 1.0,
        "analytic_frame_correction": 0.0,
        "unit": "degree_per_day",
        "direction": "direct",
        "basis": "synthetic_rendering_control",
    }
    row = {"objects": [{"id": "Moon", "motion": motion}]}
    assert verify(rendered(row))[0]["represented_terms"] == [
        "native_longitude_speed",
        "analytic_frame_correction",
    ]


@pytest.mark.parametrize(
    "mutation",
    ["omit", "duplicate", "changed_value", "changed_total", "false_sign", "invented"],
)
def test_independent_text_reader_rejects_fidelity_laundering(mutation):
    row = copy.deepcopy(next(r for r in DATA["rows"] if not r["inputs"]["zodiacal"]))
    result = rendered(row)
    moon = next(o for o in row["objects"] if o["id"] == "Moon")
    term = f"日期框架解析导数修正 {moon['motion']['analytic_frame_correction']} 度/日"
    assert term in result["snapshot_text"]
    if mutation == "omit":
        result["snapshot_text"] = result["snapshot_text"].replace("，" + term, "")
    elif mutation == "duplicate":
        result["snapshot_text"] = result["snapshot_text"].replace(
            term, term + "，" + term
        )
    elif mutation == "changed_value":
        moon["motion"]["analytic_frame_correction"] += 1.0
    elif mutation == "changed_total":
        moon["motion"]["longitude_speed"] += 1.0
    elif mutation == "false_sign":
        moon["motion"]["direction"] = (
            "retrograde" if moon["motion"]["longitude_speed"] > 0 else "direct"
        )
    else:
        del moon["motion"]["analytic_frame_correction"]
    with pytest.raises(ValueError):
        verify(result)
