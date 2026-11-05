"""Same exact TT labels, with the first calendar-input budget failure retained."""

import csv
import io
import json
import re
from fractions import Fraction as F
from pathlib import Path

import pytest

from scripts.astrodice.audit_astrodice_horizons_wide_reference import DAY_US, input_tick
from scripts.astrodice.gen_astrodice_horizons_wide import julian_input_label

FIXTURE = (
    Path(__file__).parents[1]
    / "data/astrodice/reference_sets/fixture-local-interval-development-v1"
)


@pytest.mark.parametrize(
    "label",
    [
        "1bc-Dec-31 23:59:59.123456",
        "7750ad-Jan-22 12:01:34.000000",
        "10000ad-Jan-01 00:00:00.999999",
    ],
)
def test_jd_wire_label_preserves_exact_microsecond_without_a_float_epoch(label):
    tick = input_tick(label)
    recovered = (F(julian_input_label(tick)) - F(3442849, 2)) * DAY_US
    assert abs(recovered - tick) <= F(1, 10**30)


def table(path):
    text = json.loads(path.read_text())["result"]
    return [
        row
        for row in csv.reader(io.StringIO(text.split("$$SOE")[1].split("$$EOE")[0]))
        if row
    ]


def test_real_cal_input_failure_and_jd_repair_keep_the_same_1e9_day_line():
    request = json.loads((FIXTURE / "jd-input-probe-request.json").read_text())
    ticks = request["exact_same_TT_ticks"]
    jd_labels = re.findall("'([^']+)'", request["parameters"]["TLIST"])
    assert all(
        abs((F(label) - F(3442849, 2)) * DAY_US - t) <= F(1, 10**30)
        for label, t in zip(jd_labels, ticks)
    )
    original = table(FIXTURE / "calendar-input-epoch-mismatch-raw.json")
    revised = table(FIXTURE / "jd-input-probe-raw.json")
    budget = F(1, 10**9)
    old = [F(r[1]) - F(t, DAY_US) - F(3442849, 2) for r, t in zip(original, ticks)]
    new = [F(r[1]) - F(t, DAY_US) - F(3442849, 2) for r, t in zip(revised, ticks)]
    assert len(old) == len(new) == 19
    assert max(abs(v) for v in old) > budget
    assert max(abs(v) for v in new) <= budget
    assert any(v * DAY_US == F("89.6") for v in old)
