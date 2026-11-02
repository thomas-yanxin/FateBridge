"""Isolated PyJHora4.8.7, retaining non-aligned algorithm outputs as evidence."""

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
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "tests/fixtures/jyotish-reference.json").read_text())[
        "examples"
    ]
    examples = []
    for case in cases:
        jd = case["oracle_input_local_jd"]
        place = drik.Place(
            "Fictional arithmetic reference",
            case["latitude"],
            case["longitude"],
            case["timezone_offset"],
        )
        drik.set_planet_list(set_rahu_ketu_as_true_nodes=case["node_mode"] == "true")
        y, m, d, _ = utils.jd_to_gregorian(jd)
        midnight = utils.gregorian_to_jd(drik.Date(y, m, d))
        rise, set_ = drik.sunrise(jd, place), drik.sunset(jd, place)
        functions = {
            "nathonnatha": strength._nathonnath_bala,
            "paksha": strength._paksha_bala,
            "tribhaga": strength._tribhaga_bala,
            "abda": strength._abdadhipathi,
            "masa": strength._masadhipathi,
            "dina": strength._vaaradhipathi,
            "hora": strength._hora_bala,
            "ayana": strength._ayana_bala,
        }
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
                "solar_events_ut1": {
                    "rise": midnight + rise[0] / 24 - case["timezone_offset"] / 24,
                    "set": midnight + set_[0] / 24 - case["timezone_offset"] / 24,
                },
                "outputs": {
                    key: dict(zip(names, fn(jd, place)))
                    for key, fn in functions.items()
                },
            }
        )
    result = {
        "provenance": {
            "software": "PyJHora",
            "version": "4.8.7",
            "swisseph_version": swe.version,
            "source_sha256": {
                Path(module.__file__)
                .name: hashlib.sha256(Path(module.__file__).read_bytes())
                .hexdigest()
                for module in (charts, strength, drik)
            },
            "configuration": {
                "ayanamsha": "LAHIRI",
                "flags": drik.PLANET_FLAGS,
                "sunrise_rsmi": drik.RISE_FLAGS,
            },
            "comparison_scope": "SolarHINDU events and applicable third segments align. Natha midpoint, unfolded Paksha, Hora order and Ayana coefficient/sign/model differences retained, not forced into pass/fail equality. Shared Swiss is not independent astronomy or empirical outcomes.",
        },
        "examples": examples,
    }
    target = root / "tests/fixtures/jyotish-kala-reference.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
