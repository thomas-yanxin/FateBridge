"""Freeze isolated PyJHora results, without importing FateBridge.

Run with the optional PyJHora 4.8.7 reference interpreter. Shared Swiss
astronomy does not constitute an independent astronomical or empirical test.
"""

import hashlib
import importlib.metadata
import json
from pathlib import Path


def main():
    import swisseph as swe
    from jhora import const, utils
    from jhora.horoscope.chart import charts, house, strength
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
    const.use_saravali_formula_for_uccha_bala = True  # 60-virupa scale
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
            "Fictional reference",
            case["latitude"],
            case["longitude"],
            case["timezone_offset"],
        )
        drik.set_planet_list(set_rahu_ketu_as_true_nodes=case["node_mode"] == "true")
        vargas = {}
        for division in [1, 2, 3, 7, 9, 10, 12, 30]:
            rows = charts.divisional_chart(
                jd,
                place,
                divisional_chart_factor=division,
                chart_method=2 if division == 2 else 1,
            )
            vargas[f"D{division}"] = {
                "Ascendant" if key == "L" else names[key]: list(pos)
                for key, pos in rows
                if key == "L" or key < 9
            }
        rasi = charts.rasi_chart(jd, place)[: const._pp_count_upto_ketu]
        navamsa = charts.divisional_chart(
            jd, place, divisional_chart_factor=9, chart_method=1
        )
        arrays = {
            "uchcha_bala": strength._uchcha_bala(rasi),
            "saptavargaja_bala": strength._sapthavargaja_bala1(jd, place)[:7],
            "ojayugma_bala": strength._ojayugama_bala(rasi, navamsa),
            "kendradi_bala": strength._kendra_bala(rasi),
            "drekkana_bala": strength._dreshkon_bala(rasi),
            "total_virupa": strength._sthana_bala(jd, place),
        }
        examples.append(
            {
                **{
                    k: case[k]
                    for k in (
                        "date",
                        "time",
                        "latitude",
                        "longitude",
                        "timezone_offset",
                        "node_mode",
                        "oracle_input_local_jd",
                    )
                },
                "vargas": vargas,
                "strength": {
                    name: {key: values[i] for key, values in arrays.items()}
                    for i, name in enumerate(names[:7])
                },
            }
        )
    result = {
        "provenance": {
            "software": "PyJHora",
            "version": "4.8.7",
            "swisseph_version": swe.version,
            "url": "https://github.com/naturalstupid/PyJHora",
            "source_sha256": {
                Path(m.__file__)
                .name: hashlib.sha256(Path(m.__file__).read_bytes())
                .hexdigest()
                for m in (charts, house, strength)
            },
            "configuration": {
                "ayanamsha": "LAHIRI",
                "flags": drik.PLANET_FLAGS,
                "ephemeris": "Moshier",
                "D2_chart_method": 2,
                "other_chart_methods": 1,
                "uchcha_scale": "60 virupa",
                "saptavargaja_profile": "raman_30",
                "drekkana_profile": "Raman section36; differs from Santhanam 27.6",
                "drekkana_categories": const.dreshkon_bala_list,
            },
            "limitations": "Independent rule implementation; shared Swiss astronomy. D30 sign only is compared; oracle synthetic degrees are not accepted as source evidence. No empirical prediction test.",
        },
        "examples": examples,
    }
    target = root / "tests/fixtures/jyotish-sthana-reference.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
