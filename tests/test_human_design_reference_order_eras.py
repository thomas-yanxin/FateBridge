"""Civil ordering cannot replace the explicitly selected historical time axis."""

from pathlib import Path

import pytest

from fatebridge.core.requests.human_design import HumanDesignRequest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize(
    "year,month,reference",
    [
        (1960, 1, "1959-12-31T23:59:59.999999Z"),
        (1961, 8, "1961-07-31T23:59:59.999999Z"),
    ],
)
def test_reference_with_earlier_civil_label_can_follow_birth_on_declared_tt(
    monkeypatch, tmp_path, empty_files, year, month, reference
):
    # The first crosses the UT1/UTC convention boundary. The second crosses
    # the source's negative 50 ms UTC adjustment. Neither is civil-string order.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    request = HumanDesignRequest(
        birth_year=year,
        birth_month=month,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        cycle_reference_datetime=reference,
    )
    assert request.cycle_reference_datetime == reference
