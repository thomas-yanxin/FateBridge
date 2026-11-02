"""Pinned isolated PyJHora war probes; retain every raw counterexample.

No FateBridge imports. Controlled upstream values isolate the rule under test;
these are not astronomical or real-world event observations.
"""

import hashlib
import importlib.metadata
import json
from pathlib import Path
from unittest.mock import patch


def main():
    from jhora import const
    from jhora.horoscope.chart import strength

    assert importlib.metadata.version("PyJHora") == "4.8.7"
    names = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
    cases = [
        {
            "id": "single_pair_zero_calendar",
            "longitudes": [10, 60, 120, 120.5, 200, 260, 300],
            "sthana": [0, 0, 200, 100, 0, 0, 0],
        },
        {
            "id": "no_pair_within_one_degree",
            "longitudes": [10, 60, 120, 125, 200, 260, 300],
            "sthana": [0, 0, 200, 100, 0, 0, 0],
        },
        {
            "id": "sun_moon_hide_real_star_pair",
            "longitudes": [10, 10.1, 120, 120.5, 200, 260, 300],
            "sthana": [0, 0, 200, 100, 0, 0, 0],
        },
        {
            "id": "calendar_lords_omitted",
            "longitudes": [10, 60, 120, 120.5, 200, 260, 300],
            "sthana": [0, 0, 200, 100, 0, 0, 0],
            "abda": [0, 0, 15, 0, 0, 0, 0],
            "masa": [0, 0, 30, 0, 0, 0, 0],
            "dina": [0, 0, 45, 0, 0, 0, 0],
        },
        {
            "id": "three_planet_group",
            "longitudes": [10, 60, 120, 120.2, 120.4, 260, 300],
            "sthana": [0, 0, 200, 100, 50, 0, 0],
        },
    ]
    rows = []
    for case in cases:
        zero = [0.0] * 7
        pp = [
            [i, [int(lon // 30), lon % 30]] for i, lon in enumerate(case["longitudes"])
        ]
        with (
            patch.object(strength.drik, "dhasavarga", return_value=pp),
            patch.object(strength, "_sthana_bala", return_value=case["sthana"]),
            patch.object(strength, "_dig_bala", return_value=zero),
            patch.object(strength, "_nathonnath_bala", return_value=zero),
            patch.object(strength, "_paksha_bala", return_value=zero),
            patch.object(strength, "_tribhaga_bala", return_value=zero),
            patch.object(strength, "_hora_bala", return_value=zero),
            patch.object(
                strength, "_abdadhipathi", return_value=case.get("abda", zero)
            ),
            patch.object(
                strength, "_masadhipathi", return_value=case.get("masa", zero)
            ),
            patch.object(
                strength, "_vaaradhipathi", return_value=case.get("dina", zero)
            ),
        ):
            actual = strength._yuddha_bala(2451545.0, None)
        rows.append({**case, "raw_pyjhora_yuddha": dict(zip(names, actual))})
    result = {
        "provenance": {
            "package": "PyJHora",
            "version": "4.8.7",
            "strength_py_sha256": hashlib.sha256(
                Path(strength.__file__).read_bytes()
            ).hexdigest(),
            "const_py_sha256": hashlib.sha256(
                Path(const.__file__).read_bytes()
            ).hexdigest(),
            "generator_has_no_FateBridge_imports": True,
            "scope": "Controlled inputs, not astronomy or empirical events; preserve mismatches without correcting third-party outputs",
        },
        "raw_fixed_disc_coefficients": const.planets_disc_diameters,
        "rows": rows,
        "independent_real_event_cases": 0,
    }
    target = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/jyotish-war-pyjhora-reference.json"
    )
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
