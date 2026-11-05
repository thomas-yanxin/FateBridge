"""Published ERFA check values; neither candidate-generated nor celestial truth."""

import hashlib
import json
import math
from pathlib import Path

import pytest

from fatebridge.core import analytic_solar as solar

PRIMARY = Path(__file__).parent / "data/solar/erfa-2.0.1"


def test_pinned_primary_sources_and_complete_harmonic_series():
    source = json.loads((PRIMARY / "source-manifest.json").read_text())
    for name, record in source["files"].items():
        assert (
            hashlib.sha256((PRIMARY / "sources" / name).read_bytes()).hexdigest()
            == record["sha256"]
        )
    data = solar.profile()
    assert data["source"] == source
    assert data["coefficient_fit_to_fatebridge_reference"] is False
    assert len(data["epv00"]) == 18 and len(data["nut00b"]) == 77


def test_published_epv00_two_part_date_expected_vectors():
    # ERFA2.0.1 t_erfa_c.c:t_epv00, unchanged author tolerances.
    helio, bary = solar.earth_state(2400000.5, 53411.52501161)
    expected = [
        [-0.7757238809297706813, 0.5598052241363340596, 0.2426998466481686993],
        [-0.01091891824147313846, -0.01247187268440845008, -0.005407569418065039061],
        [-0.7714104440491111971, 0.5598412061824171323, 0.2425996277722452400],
        [-0.01091874268116823295, -0.01246525461732861538, -0.005404773180966231279],
    ]
    for index, (actual, values) in enumerate(zip([*helio, *bary], expected)):
        assert actual == pytest.approx(
            values, abs=1e-14 if index % 2 == 0 else 1e-15, rel=0
        )


def test_published_nutation_and_precession_angles_keep_radian_units():
    assert solar.nutation(2400000.5, 53736) == pytest.approx(
        [-0.9632552291148362783e-5, 0.4063197106621159367e-4], abs=1e-13, rel=0
    )
    actual = solar.precession_angles(2400000.5, 50123.9999)
    expected = [
        -0.2243387670997995690e-5,
        0.4091014602391312808,
        -0.9501954178013031895e-3,
        0.4091014316587367491,
    ]
    for value, reference, line in zip(actual, expected, [1e-16, 1e-12, 1e-14, 1e-12]):
        assert abs(value - reference) <= line


def test_published_aberration_reference():
    actual = solar.aberration(
        (-0.76321968546737951, -0.60869453983060384, -0.21676408580639883),
        (2.1044018893653786e-5, -8.9108923304429319e-5, -3.8633714797716569e-5),
        0.99980921395708788,
    )
    assert actual == pytest.approx(
        [-0.7631631094219556269, -0.6087553082505590832, -0.2167926269368471279],
        abs=1e-12,
        rel=0,
    )


@pytest.mark.parametrize("epoch", [math.nan, math.inf, -math.inf])
def test_nonfinite_epochs_cannot_produce_a_plausible_solar_longitude(epoch):
    with pytest.raises(ValueError, match="finite"):
        solar.solar_longitude(epoch)


def test_author_warning_uses_actual_hundred_julian_years_boundary():
    edge = 2451545 + 36525
    assert solar.model_details(edge)["outside_author_validation_range"] is False
    assert (
        solar.model_details(math.nextafter(edge, math.inf))[
            "outside_author_validation_range"
        ]
        is True
    )
    # Merely checking year<=2100 would falsely hide the author's warning.
    assert solar.model_details(edge + 30)["outside_author_validation_range"] is True
