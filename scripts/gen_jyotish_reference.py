"""Generate numerical fixtures with isolated PyJHora 4.8.7, NOT FateBridge.

Run with the reference interpreter described in docs/jyotish.md. This optional
script is not imported by the application or ordinary tests. It stores numeric
results and provenance, not third-party implementation code.
"""

import hashlib
import importlib.metadata
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main():
    import swisseph as swe
    from jhora import const, utils
    from jhora.horoscope.chart import charts
    from jhora.horoscope.dhasa.graha import vimsottari
    from jhora.panchanga import drik

    assert importlib.metadata.version("PyJHora") == "4.8.7"
    names = [
        "Sun",
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
        "Rahu",
        "Ketu",
    ]
    drik.set_ayanamsa_mode("LAHIRI")
    const.get_place_elevation_from_internet = False
    drik.PLANET_FLAGS = utils.set_flags_for_planet_positions(
        true_positions=False, use_nutation=True, use_gravitational_deflection=True
    )
    swe.set_ephe_path("/tmp/fatebridge-jyotish-empty-ephemeris")
    inputs = [
        ((1990, 4, 6), (9, 33, 0), 31.2167, 121.4667, 8),
        ((2000, 2, 29), (23, 45, 0), 28.6139, 77.2090, 5.5),
        ((1985, 12, 31), (0, 15, 0), 40.7128, -74.0060, -5),
    ]
    bases = [
        ("sidereal_365_25636", 365.25636),
        ("tropical_365_2425", 365.2425),
        ("savana_360", 360.0),
    ]
    examples = []
    for index, (date, time, latitude, longitude, offset) in enumerate(inputs):
        # PyJHora interprets its local JD as UT1 + zone offset. Convert the
        # civil UTC instant explicitly, independently of FateBridge.
        utc = datetime(
            *date, *time, tzinfo=timezone(timedelta(hours=offset))
        ).astimezone(timezone.utc)
        _, jd_ut1 = swe.utc_to_jd(
            utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second, swe.GREG_CAL
        )
        jd = jd_ut1 + offset / 24
        place = drik.Place(
            "Explicitly fictional reference location", latitude, longitude, offset
        )
        for node_mode in ["mean", "true"]:
            drik.set_planet_list(set_rahu_ketu_as_true_nodes=node_mode == "true")
            basis, days = bases[index]
            vimsottari.year_duration = days
            vargas = {}
            for division in [1, 9, 10]:
                rows = charts.divisional_chart(
                    jd, place, divisional_chart_factor=division, chart_method=1
                )
                vargas[f"D{division}"] = {
                    "Ascendant" if key == "L" else names[key]: position
                    for key, position in rows
                    if key == "L" or key < 9
                }
            majors = vimsottari.vimsottari_mahadasa(jd, place)
            subs = {
                names[lord]: {
                    names[sub]: start
                    for sub, start in vimsottari._vimsottari_bhukti(lord, start).items()
                }
                for lord, start in majors.items()
            }
            examples.append(
                {
                    "date": date,
                    "time": time,
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone_offset": offset,
                    "node_mode": node_mode,
                    "year_basis": basis,
                    "year_days": days,
                    "oracle_input_local_jd": jd,
                    "oracle_input_ut1_jd": jd_ut1,
                    "vargas": vargas,
                    "major_starts_local_jd": {
                        names[lord]: start for lord, start in majors.items()
                    },
                    "sub_starts_local_jd": subs,
                }
            )
    result = {
        "provenance": {
            "software": "PyJHora",
            "version": "4.8.7",
            "swisseph_version": swe.version,
            "repository": "https://github.com/naturalstupid/PyJHora",
            "source_sha256": {
                Path(module.__file__)
                .name: hashlib.sha256(Path(module.__file__).read_bytes())
                .hexdigest()
                for module in [charts, vimsottari]
            },
            "configuration": {
                "ayanamsha": "LAHIRI",
                "planet_flags": drik.PLANET_FLAGS,
                "ephemeris": "Moshier, no external .se1 files",
                "varga_method": 1,
                "year_duration": "explicit per fixture; overrides oracle default 365.256364",
                "time_format": "local UT1 JD = swe_utc_to_jd(civil UTC)[1] + zone/24; dasha boundaries compared as elapsed days relative to this birth JD, not UT1 labels misread as UTC",
            },
            "scope": "Independent software implementation comparison using the same Swiss astronomy library. Does not validate predictions.",
        },
        "examples": examples,
    }
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/jyotish-reference.json"
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(examples)} independent reference cases to {path}")


if __name__ == "__main__":
    main()
