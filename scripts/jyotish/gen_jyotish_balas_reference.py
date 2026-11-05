"""Optional isolated PyJHora4.8.7 oracle; never imports production FateBridge."""

import hashlib
import importlib.metadata
import json
from pathlib import Path


def main():
    import swisseph as swe
    from jhora import const, utils
    from jhora.horoscope.chart import charts, strength
    from jhora.panchanga import drik

    assert importlib.metadata.version("PyJHora") == "4.8.7"
    names = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    drik.set_ayanamsa_mode("LAHIRI")
    const.get_place_elevation_from_internet = False
    drik.PLANET_FLAGS = utils.set_flags_for_planet_positions(
        true_positions=False, use_nutation=True, use_gravitational_deflection=True
    )
    swe.set_ephe_path("/tmp/fatebridge-jyotish-empty-ephemeris")
    root = Path(__file__).resolve().parents[2]
    cases = json.loads((root / "tests/fixtures/jyotish-reference.json").read_text())[
        "examples"
    ]
    examples = []
    for case in cases:
        jd = case["oracle_input_local_jd"]
        place = drik.Place(
            "Fictional numerical reference",
            case["latitude"],
            case["longitude"],
            case["timezone_offset"],
        )
        drik.set_planet_list(set_rahu_ketu_as_true_nodes=case["node_mode"] == "true")
        positions = charts.rasi_chart(jd, place)
        table = strength.planet_aspect_relationship_table(positions)
        examples.append(
            {
                **{
                    key: case[key]
                    for key in (
                        "date",
                        "time",
                        "latitude",
                        "longitude",
                        "timezone_offset",
                        "node_mode",
                    )
                },
                "oracle_house_method": const.bhaava_madhya_method,
                "dig_bala_shortest_arc_method2": dict(
                    zip(names, strength._dig_bala(jd, place, method=2))
                ),
                "dig_bala_legacy_method1": dict(
                    zip(names, strength._dig_bala(jd, place, method=1))
                ),
                "naisargika_bala_rounded": dict(
                    zip(names, strength._naisargika_bala())
                ),
                "aspect_matrix": {
                    p: {q: table[i][j] for j, q in enumerate(names)}
                    for i, p in enumerate(names)
                },
            }
        )
    result = {
        "provenance": {
            "software": "PyJHora",
            "version": "4.8.7",
            "swisseph_version": swe.version,
            "source_sha256": {
                Path(m.__file__)
                .name: hashlib.sha256(Path(m.__file__).read_bytes())
                .hexdigest()
                for m in (charts, strength, drik)
            },
            "configuration": {
                "ayanamsha": "LAHIRI",
                "planet_flags": drik.PLANET_FLAGS,
                "ephemeris": "Moshier",
                "aspect_table": "planet_aspect_relationship_table (additive, uncapped)",
                "directional": "method2 folds shortest arc; retain method1 known missing-fold output",
            },
            "scope": "Independent implementation of rules; shared Swiss astronomy. No empirical outcomes. Nature classification is deliberately not accepted from the oracle; production keeps explicit branches.",
        },
        "examples": examples,
    }
    target = root / "tests/fixtures/jyotish-balas-reference.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
