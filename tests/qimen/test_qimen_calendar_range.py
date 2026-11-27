"""Full-service civil endpoints over proleptic Gregorian day ordinals."""

import pytest

from fatebridge.services.sanshi import calculate_qimen_analysis


@pytest.mark.parametrize(
    "parts,day_ganzhi,fu_tou,yuan,effective_date",
    [
        ((1, 7, 15, 12), "甲午", "甲午", "上元", "00010715"),
        ((1, 1, 1, 0), "己卯", "己卯", "上元", "00010101"),
        ((9999, 7, 15, 12), "戊辰", "甲子", "上元", "99990715"),
        ((9999, 12, 31, 23), "戊午", "甲寅", "中元", "+0100000101"),
    ],
    ids=["lower-end", "lower-jan1-midnight", "upper-end", "upper-dec31-latezi"],
)
def test_zhirun_service_accepts_civil_endpoints_with_independent_day_facts(
    monkeypatch: pytest.MonkeyPatch,
    parts: tuple[int, int, int, int],
    day_ganzhi: str,
    fu_tou: str,
    yuan: str,
    effective_date: str,
) -> None:
    # Isolate the existing default, rather than inherit a deliberately narrow
    # explicit model/JPL selection. Do not replace native paths or source data.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    year, month, day, hour = parts
    result = calculate_qimen_analysis(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_minute=0,
        analysis_timezone="+00:00",
        use_true_solar_time=False,
        qimen_options={"ju_method": "zhirun"},
    )

    assert "error" not in result, result
    qimen = result["qimen"]
    assert qimen["ju_method"] == "zhirun"
    assert qimen["day_ganzhi"] == day_ganzhi
    assert qimen["fu_tou"] == fu_tou
    assert qimen["yuan"] == yuan
    assert qimen["ju_decision"]["effective_date"] == effective_date
    assert qimen["ju_decision"]["day_ganzhi"] == day_ganzhi
    assert qimen["ju_decision"]["yuan"] == yuan

    # Structural completion is not an oracle for the calculated ju/star/door.
    palaces = qimen["palaces"]
    assert len(palaces) == 9
    assert {palace["index"] for palace in palaces} == set(range(1, 10))
    assert all(
        {"name", "trigram", "heaven_stems", "earth_stems", "star", "door", "god"}
        <= palace.keys()
        for palace in palaces
    )
    assert qimen["zhifu"] and qimen["zhishi"]
    assert "rulesets" not in qimen and "rule_trace" not in qimen
    assert qimen["calendar_policy"]["day_boundary"] == "23:00"
    assert qimen["calendar_policy"]["hour_clock"] == "civil"
