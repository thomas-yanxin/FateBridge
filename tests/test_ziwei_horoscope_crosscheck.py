import json
from pathlib import Path

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.services.metaphysics import _build_analysis_seed, _build_person_seed
from fatebridge.utils.birth_input import create_person_info

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "ziwei_horoscope_reference.json"
)

# Frozen software-reference differences are asserted, never skipped or edited
# into source agreement. These three rows use a six-year bureau and precede
# its formal start; the old software substituted childhood palaces and 四化.
PRE_DECADE_REFERENCE_ROWS = {
    "childhood_one": {"branch": "寅", "mutagen": ["天同", "天机", "文昌", "廉贞"]},
    "childhood_three": {"branch": "酉", "mutagen": ["破军", "巨门", "太阴", "贪狼"]},
    "childhood_two": {"branch": "戌", "mutagen": ["廉贞", "破军", "武曲", "太阳"]},
}

# py-iztro time index (子=0 .. 亥=11; 12=晚子) -> representative hour
_TIME_INDEX_TO_HOUR = {
    0: 0,
    1: 2,
    2: 4,
    3: 6,
    4: 8,
    5: 10,
    6: 12,
    7: 14,
    8: 16,
    9: 18,
    10: 20,
    11: 22,
    12: 23,
}


def _our_horoscope(case: dict) -> dict:
    by, bm, bd = (int(x) for x in case["birth"]["date"].split("-"))
    bh = _TIME_INDEX_TO_HOUR[case["birth"]["time_index"]]
    person = create_person_info(
        birth_year=by,
        birth_month=bm,
        birth_day=bd,
        birth_hour=bh,
        gender=case["birth"]["gender"],
    )
    natal_seed = _build_person_seed(person)
    chart = build_ziwei_chart(natal_seed, person.gender or "未知")
    ty, tm, td = (int(x) for x in case["target"]["date"].split("-"))
    th = _TIME_INDEX_TO_HOUR[case["target"]["time_index"]]
    target_seed = _build_analysis_seed(
        analysis_year=ty, analysis_month=tm, analysis_day=td, analysis_hour=th
    )
    h = build_ziwei_horoscope(
        nominal_age_basis="legacy_mixed_clock",
        chart=chart,
        gender=person.gender or "未知",
        target_seed=target_seed,
    )
    return h


def test_horoscope_matches_iztro_oracle():
    reference = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert reference, "fixture must not be empty"
    mismatches = []
    unavailable_rows = set()
    compared_scope_records = 0
    for label, case in reference.items():
        h = _our_horoscope(case)
        assert h["nominal_age"] == case["nominal_age"], label
        ours = {s["scope"]: s for s in h["scopes"]}
        for scope, ref in case["scopes"].items():
            got = ours[scope]
            if scope == "大限" and label in PRE_DECADE_REFERENCE_ROWS:
                assert ref == PRE_DECADE_REFERENCE_ROWS[label]
                assert h["nominal_age"] < got["first_age"] == 6
                assert got["status"] == "not_started"
                assert got["branch"] is None and got["mutagen"] is None
                assert got["natal_palace_name"] is None and got["stem"] is None
                assert got["palace_map"] == got["mutagen_natal_links"] == []
                assert got["is_childhood_limit"] is False
                unavailable_rows.add(label)
                continue
            compared_scope_records += 1
            if got["branch"] != ref["branch"]:
                mismatches.append(
                    f"{label}/{scope} branch: ours={got['branch']} ref={ref['branch']}"
                )
            # ordered [化禄, 化权, 化科, 化忌]; the fixture mutagen list is in the
            # same order, so compare as a tuple to also catch role swaps.
            if list(got["mutagen"].values()) != list(ref["mutagen"]):
                mismatches.append(
                    f"{label}/{scope} 四化: ours={list(got['mutagen'].values())} ref={list(ref['mutagen'])}"
                )
    assert unavailable_rows == set(PRE_DECADE_REFERENCE_ROWS)
    assert compared_scope_records == 105
    assert not mismatches, "horoscope mismatches vs iztro oracle:\n" + "\n".join(
        mismatches
    )
