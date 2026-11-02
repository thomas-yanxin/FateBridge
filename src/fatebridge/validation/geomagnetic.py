"""Compare every frozen NOAA main-field vector at its published precision."""

import math
from decimal import Decimal
from typing import Any, Dict, List

from fatebridge.core.fengshui.geomagnetic import geomagnetic_reference
from fatebridge.core.fengshui.geomagnetic_inputs import GeomagneticReference

KEYS = {
    "x": "north_component_nt",
    "y": "east_component_nt",
    "z": "down_component_nt",
    "h": "horizontal_intensity_nt",
    "f": "total_intensity_nt",
    "i": "inclination_degrees_down",
    "d": "declination_degrees_east",
}


def audit_noaa_vectors(raw: str, *, layout: str) -> Dict[str, Any]:
    if layout not in ("published_12", "coefficient_zip_100"):
        raise ValueError("Unknown independent test-vector layout")
    rows = [
        s.split()
        for s in raw.splitlines()
        if s.strip() and not s.lstrip().startswith("#")
    ]
    expected_rows = 12 if layout == "published_12" else 100
    if len(rows) != expected_rows:
        raise ValueError(f"Expected all {expected_rows} official rows, got {len(rows)}")
    if len({tuple(v[:4]) for v in rows}) != expected_rows:
        raise ValueError(
            "Duplicate input vectors cannot substitute for missing official rows"
        )
    if any(len(row) < 11 for row in rows):
        raise ValueError(
            "Every official row must retain all seven main-field components"
        )
    order = (
        ("x", "y", "z", "h", "f", "i", "d")
        if layout == "published_12"
        else ("d", "i", "h", "x", "y", "z", "f")
    )
    disagreements: List[Dict[str, Any]] = []
    maximum = dict.fromkeys(order, 0.0)
    matched = 0
    for index, row in enumerate(rows, start=1):
        year, height, latitude, original_lon = map(float, row[:4])
        longitude = (original_lon + 180) % 360 - 180
        result = geomagnetic_reference(
            GeomagneticReference(
                latitude=latitude,
                longitude=longitude,
                height_km_wgs84=height,
                decimal_year=year,
                evidence="Official NOAA numeric reference; not a real property survey",
            )
        )["field"]
        for key, token in zip(order, row[4:11]):
            published = Decimal(token)
            exponent = published.as_tuple().exponent
            if not isinstance(exponent, int):
                raise ValueError("Reference field must be a finite decimal")
            tolerance = float(Decimal(5).scaleb(exponent - 1))
            actual = result[KEYS[key]]
            difference = abs(actual - float(published))
            maximum[key] = max(maximum[key], difference)
            if difference <= tolerance + 1e-10:
                matched += 1
            else:
                disagreements.append(
                    {
                        "row": index,
                        "original_input": row[:4],
                        "normalized_longitude": longitude,
                        "component": key,
                        "expected_literal": token,
                        "actual": actual,
                        "absolute_difference": difference,
                        "half_last_published_place": tolerance,
                    }
                )
    return {
        "layout": layout,
        "rows": len(rows),
        "components_per_row": 7,
        "comparisons": len(rows) * 7,
        "matched_at_published_precision": matched,
        "maximum_absolute_difference": maximum,
        "disagreements": disagreements,
        "all_published_precision_checks_passed": not disagreements,
        "scope": "main_field_only_not_secular_rates_grid_variation_or_Feng_Shui_predictive_validity",
    }


def audit_noaa_c_vectors(reference: Dict[str, Any], raw_inputs: str) -> Dict[str, Any]:
    """Frozen outputs of unmodified current NOAA C, with fixed numeric tolerance."""
    inputs = [
        s.split()[:4]
        for s in raw_inputs.splitlines()
        if s.strip() and not s.lstrip().startswith("#")
    ]
    vectors = reference["vectors"]
    if (
        len(inputs) != 100
        or len({tuple(row) for row in inputs}) != 100
        or [v["input_original"] for v in vectors] != inputs
    ):
        raise ValueError(
            "NOAA C reference must retain all 100 original input rows in order"
        )
    maximum = dict.fromkeys(KEYS, 0.0)
    disagreements = []
    for index, vector in enumerate(vectors, start=1):
        year, height, latitude, longitude = map(float, vector["input_original"])
        field = geomagnetic_reference(
            GeomagneticReference(
                latitude=latitude,
                longitude=(longitude + 180) % 360 - 180,
                height_km_wgs84=height,
                decimal_year=year,
                evidence="Official NOAA C implementation reference; not a property survey",
            )
        )["field"]
        if set(vector["field"]) != set(KEYS):
            raise ValueError("All seven field components must be retained")
        for key, actual_key in KEYS.items():
            # Fixed acceptance for double-precision implementation equivalence;
            # separate from both the published table rounding and physical error.
            tolerance = 1e-9 if key in ("d", "i") else 1e-7
            expected = vector["field"][key]
            if (
                isinstance(expected, bool)
                or not isinstance(expected, (int, float))
                or not math.isfinite(expected)
            ):
                raise ValueError("Every reference component must be a finite number")
            difference = abs(field[actual_key] - expected)
            maximum[key] = max(maximum[key], difference)
            if difference > tolerance:
                disagreements.append(
                    {"row": index, "component": key, "absolute_difference": difference}
                )
    return {
        "rows": len(vectors),
        "comparisons": len(vectors) * 7,
        "tolerance": {"nt": 1e-7, "degrees": 1e-9},
        "maximum_absolute_difference": maximum,
        "disagreements": disagreements,
        "official_c_implementation_agreement": not disagreements,
        "scope": "numerical_implementation_equivalence_not_physical_accuracy_or_Feng_Shui_predictive_validity",
    }
