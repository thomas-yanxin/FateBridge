"""Freeze isolated PyJHora4.8.7 mean/Cheshta outputs, preserving disagreements."""

import hashlib
import importlib.metadata
import json
from pathlib import Path


def main():
    import swisseph as swe
    from jhora import const, utils
    from jhora.horoscope.chart import strength
    from jhora.panchanga import drik

    assert importlib.metadata.version("PyJHora") == "4.8.7"
    const.get_place_elevation_from_internet = False
    drik.set_ayanamsa_mode("LAHIRI")
    drik.PLANET_FLAGS = utils.set_flags_for_planet_positions(
        true_positions=False, use_nutation=True, use_gravitational_deflection=True
    )
    swe.set_ephe_path("/tmp/fatebridge-jyotish-empty-ephemeris")
    place = drik.Place("Source mean-clock76E reference", 0, 76, 0)
    names = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    examples = []
    for date, time in [
        ((1895, 4, 2), (0, 0, 0)),
        ((1900, 1, 1), (0, 0, 0)),
        ((1900, 1, 9), (6, 0, 0)),
        ((1918, 10, 16), (13, 59, 56)),
        ((1990, 4, 6), (9, 33, 0)),
        ((2000, 2, 29), (18, 15, 0)),
        ((2026, 10, 22), (0, 0, 0)),
    ]:
        jd = utils.julian_day_number(date, time)
        methods = {}
        for key, fn in (
            ("linear_mean", strength.get_planet_mean_longitude),
            ("table_mean", strength.get_planet_mean_longitude_using_epoch_table),
        ):
            values = {}
            for index, name in enumerate(names):
                try:
                    values[name] = fn(jd, place, index)
                except Exception as exc:
                    values[name] = {"error": type(exc).__name__, "message": str(exc)}
            methods[key] = values
        raw_cheshta = {}
        for use_table in (False, True):
            try:
                raw_cheshta[str(use_table)] = strength._cheshta_bala_new(
                    jd, place, use_epoch_table=use_table
                )
            except Exception as exc:
                raw_cheshta[str(use_table)] = {
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
        examples.append(
            {
                "date": date,
                "source_mean_clock": time,
                "jd_local": jd,
                "interval_reported_by_oracle": strength._DAYS_FROM_EPOCH(jd, place),
                "mean_outputs_by_internal_index": methods,
                "raw_cheshta_lists": raw_cheshta,
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
                for m in (strength, drik, const)
            },
            "flags": drik.PLANET_FLAGS,
        },
        "scope": "No FateBridge imports. Source mean-clock76E input aligns the mean interval only; physical dhasavarga calls use the oracle's unmodified timezone0 convention and are retained as counterevidence, not native-Lahiri physical references. No monkeypatches. Raw Cheshta lists are not relabelled across the upstream internal/SWE-ID mappings.",
        "internal_names": names,
        "upstream_swe_id_to_internal_index": {
            str(k): drik.planet_list[k] for k in range(7)
        },
        "upstream_literal_tables": strength.ujjain_epoch_table_for_planets,
        "examples": examples,
    }
    target = (
        Path(__file__).resolve().parents[2]
        / "tests/fixtures/jyotish-motion-reference.json"
    )
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
